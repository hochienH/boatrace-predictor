"""稅前／稅後 EV 試算：驗證 REVIEW.md §9.1 一時所得對穴狙い策略的衝擊（Phase 0 go/no-go 用）。

日本稅制對舟券払戻金的原則性認定是「一時所得」：
    課稅所得 = max(0, 払戻金總額 − 中獎票購入額 − 特別控除 50 萬) × 1/2
關鍵陷阱：沒中的票不能列為費用，只有「中獎那幾張票」的購入額可扣除。
對照組「雑所得」（需極高頻機械式購入才可能被認定）則外れ券全額可扣，僅供比較，不可預設可用。
"""

from __future__ import annotations

from dataclasses import dataclass

SPECIAL_DEDUCTION = 500_000  # 一時所得特別控除（每年）
MARGINAL_RATE = 0.33  # 所得稅+住民稅的邊際稅率近似值（課稅所得 330~694 萬區間的受薪階級）


@dataclass(frozen=True)
class Scenario:
    label: str
    hit_rate: float  # 命中率
    pretax_roi: float  # 目標稅前 ROI（用來反推平均命中賠率）

    @property
    def avg_odds(self) -> float:
        return (1 + self.pretax_roi) / self.hit_rate


SCENARIOS = (
    Scenario("悲觀（打不贏抽水）", hit_rate=0.05, pretax_roi=-0.10),
    Scenario("打平抽水邊緣", hit_rate=0.05, pretax_roi=0.00),
    Scenario("樂觀（打贏抽水）", hit_rate=0.05, pretax_roi=0.10),
    Scenario("奇蹟等級", hit_rate=0.03, pretax_roi=0.20),
)


def ichiji_shotoku_tax(total_payout: float, winning_cost: float, marginal_rate: float) -> float:
    """一時所得：外れ券不可列費用，是實戰真正適用的稅制。"""
    taxable_income = max(0.0, total_payout - winning_cost - SPECIAL_DEDUCTION) * 0.5
    return taxable_income * marginal_rate


def zatsu_shotoku_tax(total_payout: float, total_bet: float, marginal_rate: float) -> float:
    """雑所得：全部購入額（含外れ）可列費用。認定門檻極高，僅供對照，不可預設適用。"""
    taxable_income = max(0.0, total_payout - total_bet)
    return taxable_income * marginal_rate


def evaluate(stake: int, n_bets: int, scenario: Scenario, marginal_rate: float = MARGINAL_RATE) -> dict:
    total_bet = stake * n_bets
    n_hits = n_bets * scenario.hit_rate
    total_payout = n_hits * stake * scenario.avg_odds
    winning_cost = n_hits * stake

    pretax_profit = total_payout - total_bet

    tax_ichiji = ichiji_shotoku_tax(total_payout, winning_cost, marginal_rate)
    posttax_profit_ichiji = pretax_profit - tax_ichiji

    tax_zatsu = zatsu_shotoku_tax(total_payout, total_bet, marginal_rate)
    posttax_profit_zatsu = pretax_profit - tax_zatsu

    return {
        "total_bet": total_bet,
        "pretax_profit": pretax_profit,
        "pretax_roi": pretax_profit / total_bet,
        "tax_ichiji": tax_ichiji,
        "posttax_profit_ichiji": posttax_profit_ichiji,
        "posttax_roi_ichiji": posttax_profit_ichiji / total_bet,
        "tax_zatsu": tax_zatsu,
        "posttax_profit_zatsu": posttax_profit_zatsu,
        "posttax_roi_zatsu": posttax_profit_zatsu / total_bet,
    }


def fmt_yen(x: float) -> str:
    return f"{x:,.0f}円"


def print_table(stake: int, n_bets_list: tuple[int, ...]) -> None:
    print(f"\n=== 單注 {stake:,}円、邊際稅率 {MARGINAL_RATE:.0%} ===")
    for scenario in SCENARIOS:
        print(f"\n--- {scenario.label}（命中率 {scenario.hit_rate:.0%}、平均賠率 {scenario.avg_odds:.1f} 倍、稅前 ROI {scenario.pretax_roi:+.0%}）---")
        header = f"{'年下注次數':>10} {'總投入':>12} {'稅前損益':>12} {'稅前ROI':>8} | {'一時所得稅':>10} {'稅後損益':>12} {'稅後ROI':>8} | {'雑所得稅(對照)':>14} {'雑所得稅後ROI(對照)':>10}"
        print(header)
        for n_bets in n_bets_list:
            r = evaluate(stake, n_bets, scenario)
            print(
                f"{n_bets:>10,} {fmt_yen(r['total_bet']):>12} {fmt_yen(r['pretax_profit']):>12} "
                f"{r['pretax_roi']:>7.1%} | {fmt_yen(r['tax_ichiji']):>10} {fmt_yen(r['posttax_profit_ichiji']):>12} "
                f"{r['posttax_roi_ichiji']:>7.1%} | {fmt_yen(r['tax_zatsu']):>14} {r['posttax_roi_zatsu']:>9.1%}"
            )


if __name__ == "__main__":
    # 情境一：Phase 6 定調的驗證規模（單注固定 100 円）
    print_table(stake=100, n_bets_list=(1000, 3000, 10000, 30000))

    # 情境二：若未來放大注碼（README/REVIEW 提到的資金規模 20~50 萬日圓量級）
    print_table(stake=1000, n_bets_list=(1000, 3000, 10000))
    print_table(stake=10000, n_bets_list=(1000, 3000))
