#!/usr/bin/env python3
"""
fin-ratio-cashflow-auditor: Financial Analysis, Ratio & Cashflow Audit CLI.

Ingests JSONL period financial statements (revenue, COGS, operating expenses,
operating cash flow, capex, total assets, total liabilities, current assets,
current liabilities, inventory, cash, accounts receivable), validates accounting
identities and numeric integrity, computes profitability, liquidity, leverage,
and free cash flow ratios, flags anomalies, and outputs JSON + Markdown reports.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class FinIssue:
    line_number: int
    period: str
    severity: str  # ERROR, WARN
    code: str
    message: str


@dataclass
class PeriodMetrics:
    period: str
    gross_margin_pct: float | None
    operating_margin_pct: float | None
    current_ratio: float | None
    quick_ratio: float | None
    debt_to_equity: float | None
    free_cash_flow: float | None
    ocf_to_net_income: float | None


def _num(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    try:
        x = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def _safe_div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or abs(den) < 1e-12:
        return None
    return num / den


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze period financial statements JSONL for ratios, cash flow, and accounting integrity."
    )
    parser.add_argument("statements_file", type=Path, help="Path to financial periods .jsonl file")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("fin_analysis_report.json"),
        help="Output JSON report path (default: fin_analysis_report.json)",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=Path("fin_analysis_summary.md"),
        help="Output Markdown report path (default: fin_analysis_summary.md)",
    )
    args = parser.parse_args()

    if not args.statements_file.is_file():
        print(f"Error: Statements file not found: {args.statements_file}", file=sys.stderr)
        return 2

    issues: list[FinIssue] = []
    periods_out: list[PeriodMetrics] = []
    seen_periods: set[str] = set()
    total_lines = 0

    with args.statements_file.open("r", encoding="utf-8") as handle:
        for line_num, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            total_lines += 1

            try:
                rec: dict[str, Any] = json.loads(stripped)
            except json.JSONDecodeError as exc:
                issues.append(
                    FinIssue(line_num, f"line-{line_num}", "ERROR", "FIN-001", f"Malformed JSON line: {exc}")
                )
                continue

            if not isinstance(rec, dict):
                issues.append(
                    FinIssue(line_num, f"line-{line_num}", "ERROR", "FIN-002", "Record must be a JSON object.")
                )
                continue

            period = str(rec.get("period", "")).strip() or f"period-{line_num}"
            if period in seen_periods:
                issues.append(
                    FinIssue(line_num, period, "WARN", "FIN-DUP", f"Duplicate period label '{period}'.")
                )
            seen_periods.add(period)

            rev = _num(rec.get("revenue"))
            cogs = _num(rec.get("cogs"))
            opex = _num(rec.get("opex"))
            net_inc = _num(rec.get("net_income"))
            ocf = _num(rec.get("operating_cash_flow"))
            capex = _num(rec.get("capex"))
            cash = _num(rec.get("cash"))
            ar = _num(rec.get("accounts_receivable"))
            inv = _num(rec.get("inventory"))
            curr_assets = _num(rec.get("current_assets"))
            curr_liab = _num(rec.get("current_liabilities"))
            tot_assets = _num(rec.get("total_assets"))
            tot_liab = _num(rec.get("total_liabilities"))
            equity = _num(rec.get("equity"))

            if rev is None or rev < 0:
                issues.append(
                    FinIssue(line_num, period, "ERROR", "REV-001", "Missing or negative revenue.")
                )

            if tot_assets is not None and tot_liab is not None and equity is not None:
                imbalance = abs(tot_assets - (tot_liab + equity))
                tol = max(1.0, abs(tot_assets) * 0.01)
                if imbalance > tol:
                    issues.append(
                        FinIssue(
                            line_num,
                            period,
                            "WARN",
                            "BS-001",
                            f"Balance sheet mismatch: Assets ({tot_assets:,.2f}) vs Liab+Equity ({tot_liab + equity:,.2f}) [diff={imbalance:,.2f}].",
                        )
                    )

            gross_profit = (rev - cogs) if (rev is not None and cogs is not None) else None
            op_income = (gross_profit - opex) if (gross_profit is not None and opex is not None) else None
            fcf = (ocf - capex) if (ocf is not None and capex is not None) else None

            if fcf is not None and fcf < 0:
                issues.append(
                    FinIssue(line_num, period, "WARN", "FCF-001", f"Negative free cash flow ({fcf:,.2f}).")
                )

            quick_assets = None
            if curr_assets is not None:
                quick_assets = curr_assets - (inv if inv is not None else 0.0)
            elif cash is not None and ar is not None:
                quick_assets = cash + ar

            curr_ratio = _safe_div(curr_assets, curr_liab)
            quick_ratio = _safe_div(quick_assets, curr_liab)
            d_to_e = _safe_div(tot_liab, equity)
            gross_margin_pct = (_safe_div(gross_profit, rev) * 100.0) if (_safe_div(gross_profit, rev) is not None) else None
            op_margin_pct = (_safe_div(op_income, rev) * 100.0) if (_safe_div(op_income, rev) is not None) else None
            ocf_to_ni = _safe_div(ocf, net_inc)

            if curr_ratio is not None and curr_ratio < 1.0:
                issues.append(
                    FinIssue(line_num, period, "WARN", "LIQ-001", f"Current ratio below 1.00 ({curr_ratio:.2f}x).")
                )

            periods_out.append(
                PeriodMetrics(
                    period=period,
                    gross_margin_pct=round(gross_margin_pct, 2) if gross_margin_pct is not None else None,
                    operating_margin_pct=round(op_margin_pct, 2) if op_margin_pct is not None else None,
                    current_ratio=round(curr_ratio, 2) if curr_ratio is not None else None,
                    quick_ratio=round(quick_ratio, 2) if quick_ratio is not None else None,
                    debt_to_equity=round(d_to_e, 2) if d_to_e is not None else None,
                    free_cash_flow=round(fcf, 2) if fcf is not None else None,
                    ocf_to_net_income=round(ocf_to_ni, 2) if ocf_to_ni is not None else None,
                )
            )

    err_count = sum(1 for i in issues if i.severity == "ERROR")
    warn_count = sum(1 for i in issues if i.severity == "WARN")

    report_obj = {
        "metadata": {
            "source_file": str(args.statements_file),
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "lines_processed": total_lines,
            "periods_analyzed": len(periods_out),
            "error_count": err_count,
            "warning_count": warn_count,
        },
        "periods": [asdict(p) for p in periods_out],
        "issues": [asdict(i) for i in issues],
    }

    args.json_out.write_text(json.dumps(report_obj, indent=2), encoding="utf-8")

    md_lines = [
        "# Financial Ratio & Cash Flow Analysis Report",
        "",
        f"- **Source File:** `{args.statements_file.name}` | **Generated (UTC):** `{report_obj['metadata']['generated_utc']}`",
        f"- **Periods Analyzed:** `{len(periods_out)}` | **Issues:** `{err_count}` errors, `{warn_count}` warnings",
        "",
        "## Period Ratios & Cash Flow",
        "",
        "| Period | Gross Margin % | Op Margin % | Current Ratio | Quick Ratio | Debt/Equity | Free Cash Flow | OCF / Net Inc |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for p in periods_out:
        gm = f"{p.gross_margin_pct:.2f}%" if p.gross_margin_pct is not None else "-"
        om = f"{p.operating_margin_pct:.2f}%" if p.operating_margin_pct is not None else "-"
        cr = f"{p.current_ratio:.2f}x" if p.current_ratio is not None else "-"
        qr = f"{p.quick_ratio:.2f}x" if p.quick_ratio is not None else "-"
        de = f"{p.debt_to_equity:.2f}x" if p.debt_to_equity is not None else "-"
        fcf_s = f"{p.free_cash_flow:,.2f}" if p.free_cash_flow is not None else "-"
        ocf_ni = f"{p.ocf_to_net_income:.2f}x" if p.ocf_to_net_income is not None else "-"
        md_lines.append(f"| `{p.period}` | {gm} | {om} | {cr} | {qr} | {de} | {fcf_s} | {ocf_ni} |")

    md_lines.extend(["", "## Audit & Integrity Checks", ""])
    if not issues:
        md_lines.append("_All period records passed balance-sheet, liquidity, and cash-flow checks._")
    else:
        md_lines.extend(
            [
                "| Line | Period | Severity | Code | Diagnostic Detail |",
                "| :---: | :--- | :---: | :--- | :--- |",
            ]
        )
        for item in issues:
            md_lines.append(
                f"| {item.line_number} | `{item.period}` | **{item.severity}** | `{item.code}` | {item.message} |"
            )

    args.md_out.write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")

    print(
        f"[+] Financial Analysis: {len(periods_out)} period(s) processed, "
        f"{err_count} errors, {warn_count} warnings."
    )
    print(f"[+] Wrote {args.json_out} and {args.md_out}")

    return 1 if err_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
