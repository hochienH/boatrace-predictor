"""快照去重的單元測試：python -m unittest tests.test_snapshot_dedup（PYTHONPATH=src）。"""

from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from boatrace_crawler import odds_snapshot, storage
from boatrace_crawler.fetcher import FetchError

PAGE_A = b'<html><head><style>a{}</style></head><body><!-- c --><table class="table1">A  1</table><script>x=1</script></body></html>'
PAGE_A2 = b'<html><head><style>b{}</style></head><body><!-- d --><table class="table1">A\n1</table><script>x=2</script></body></html>'
PAGE_B = b'<html><body><table class="table1">B</table></body></html>'
EMPTY = b"<html><body>no table</body></html>"


def pc_page(nav: bytes, body: bytes, with_markers: bool = True) -> bytes:
    """仿 pcexpect 版面：上方導覽表（會隨時間變 class）＋ 予想本體（title16 到 </main>）。"""
    head = b'<html><body><div class="table1">' + nav + b'</div>'
    if with_markers:
        return head + b'<main><div class="title16__add2020">x</div><div class="table1">' + body + b'</div></main><footer>f</footer></body></html>'
    return head + b'<div class="table1">' + body + b'</div></body></html>'


class FakeFetcher:
    def __init__(self, body):
        self.body = body

    def get(self, url):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class ContentHashTest(unittest.TestCase):
    def test_ignores_script_style_comment_whitespace(self):
        self.assertEqual(storage.content_hash(PAGE_A), storage.content_hash(PAGE_A2))

    def test_detects_real_change(self):
        self.assertNotEqual(storage.content_hash(PAGE_A), storage.content_hash(PAGE_B))


class RegionTest(unittest.TestCase):
    def test_extract_region(self):
        self.assertEqual(storage.extract_region(b"aa<s>mid</e>zz", b"<s>", b"</e>"), (b"<s>mid", True))
        self.assertEqual(storage.extract_region(b"aa<s>mid", b"<s>", b"</e>"), (b"aa<s>mid", False))
        self.assertEqual(storage.extract_region(b"mid</e>", b"<s>", b"</e>"), (b"mid</e>", False))

    def test_pcexpect_hash_ignores_nav_outside_region(self):
        a = odds_snapshot._dedup_hash("pcexpect", pc_page(b'<td class="is-activeColor1">10:54', b"F 1=2"))
        b = odds_snapshot._dedup_hash("pcexpect", pc_page(b'<td class="">10:54', b"F 1=2"))
        c = odds_snapshot._dedup_hash("pcexpect", pc_page(b'<td class="">10:54', b"F 1=3"))
        self.assertEqual(a, b)
        self.assertEqual(a[1], "region")
        self.assertNotEqual(a[0], c[0])

    def test_missing_markers_falls_back_to_full_page(self):
        h, scope = odds_snapshot._dedup_hash("pcexpect", pc_page(b"n", b"F", with_markers=False))
        self.assertEqual(scope, "full")
        self.assertEqual(h, storage.content_hash(pc_page(b"n", b"F", with_markers=False)))


class SnapshotDedupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            mock.patch.object(storage, "RAW_ROOT", root / "raw"),
            mock.patch.object(storage, "MANIFEST_PATH", root / "raw" / "_manifest.jsonl"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def _run(self, prefix, body, ts):
        task = odds_snapshot.SnapshotTask("20261024", "04", 1, prefix, ts)
        return odds_snapshot._fetch_one(FakeFetcher(body), task)

    def _files(self, prefix):
        folder = storage.snapshot_path("20261024", "04", prefix, 1, 0).parent
        return sorted(p.name for p in folder.glob("*.html.gz")) if folder.is_dir() else []

    def _outcomes(self):
        return [json.loads(l)["outcome"] for l in storage.MANIFEST_PATH.read_text().splitlines()]

    def test_pcexpect_writes_only_on_change(self):
        self.assertEqual(self._run("pcexpect", PAGE_A, 100), "ok")
        self.assertEqual(self._run("pcexpect", PAGE_A2, 200), "unchanged")  # 只差 script/空白
        self.assertEqual(self._run("pcexpect", PAGE_B, 300), "ok")
        self.assertEqual(self._run("pcexpect", PAGE_B, 400), "unchanged")
        self.assertEqual(self._files("pcexpect"), ["100.html.gz", "300.html.gz"])
        self.assertEqual(self._outcomes(), ["ok", "unchanged", "ok", "unchanged"])
        last = json.loads(storage.MANIFEST_PATH.read_text().splitlines()[-1])
        self.assertEqual(last["sha256"], storage.content_hash(PAGE_B))
        self.assertEqual(last["ts"], 400)

    def test_odds3t_always_writes(self):
        self.assertEqual(self._run("odds3t", PAGE_A, 100), "ok")
        self.assertEqual(self._run("odds3t", PAGE_A, 200), "ok")
        self.assertEqual(self._files("odds3t"), ["100.html.gz", "200.html.gz"])

    def test_empty_and_failed_do_not_touch_dedup_state(self):
        self.assertEqual(self._run("pcexpect", PAGE_A, 100), "ok")
        self.assertEqual(self._run("pcexpect", EMPTY, 200), "empty")
        self.assertEqual(self._run("pcexpect", FetchError("boom"), 300), "failed")
        self.assertEqual(self._run("pcexpect", PAGE_A, 400), "unchanged")
        self.assertEqual(self._files("pcexpect"), ["100.html.gz"])

    def test_corrupt_latest_file_counts_as_changed(self):
        self.assertEqual(self._run("pcexpect", PAGE_A, 100), "ok")
        bad = storage.snapshot_path("20261024", "04", "pcexpect", 1, 150)
        bad.write_bytes(b"not gzip")
        self.assertEqual(self._run("pcexpect", PAGE_A, 200), "ok")
        self.assertEqual(self._files("pcexpect"), ["100.html.gz", "150.html.gz", "200.html.gz"])

    def test_corrupt_deflate_stream_counts_as_changed(self):
        # gzip header 正確、deflate 區損毀 → zlib.error（不是 OSError/EOFError），也要視同有變動
        self.assertEqual(self._run("pcexpect", PAGE_A, 100), "ok")
        good = gzip.compress(PAGE_A)
        bad = storage.snapshot_path("20261024", "04", "pcexpect", 1, 150)
        bad.write_bytes(good[:10] + b"\xff" * 40 + good[-8:])
        self.assertEqual(self._run("pcexpect", PAGE_A, 200), "ok")
        self.assertEqual(self._outcomes()[-1], "ok")

    def test_nav_churn_does_not_rewrite_pcexpect(self):
        self.assertEqual(self._run("pcexpect", pc_page(b'<td class="is-activeColor1">', b"F 1=2"), 100), "ok")
        self.assertEqual(self._run("pcexpect", pc_page(b'<td class="">', b"F 1=2"), 200), "unchanged")
        self.assertEqual(self._run("pcexpect", pc_page(b'<td class="">', b"F 1=3"), 300), "ok")
        self.assertEqual(self._files("pcexpect"), ["100.html.gz", "300.html.gz"])
        last = json.loads(storage.MANIFEST_PATH.read_text().splitlines()[-1])
        self.assertEqual(last["scope"], "region")

    def test_tmp_file_is_not_latest(self):
        self.assertEqual(self._run("pcexpect", PAGE_A, 100), "ok")
        tmp = storage.snapshot_path("20261024", "04", "pcexpect", 1, 999)
        tmp.with_suffix(".gz.tmp").write_bytes(b"partial")
        self.assertEqual(self._run("pcexpect", PAGE_A, 200), "unchanged")

    def test_latest_is_by_numeric_ts(self):
        folder = storage.snapshot_path("20261024", "04", "pcexpect", 1, 0).parent
        folder.mkdir(parents=True)
        for ts, body in ((999, PAGE_B), (1000, PAGE_A)):
            with gzip.open(folder / f"{ts}.html.gz", "wb") as fh:
                fh.write(body)
        self.assertEqual(storage.latest_snapshot("20261024", "04", "pcexpect", 1).name, "1000.html.gz")
        self.assertEqual(self._run("pcexpect", PAGE_A, 1100), "unchanged")


if __name__ == "__main__":
    unittest.main()
