# fin-ratio-cashflow-auditor

A zero-dependency Python 3.10+ CLI for **financial statement ratio analysis, free cash flow checks, and accounting integrity auditing**.

Built to evaluate period-by-period financial records (`JSONL`), compute gross/operating margins, current/quick ratios, debt-to-equity, free cash flow, and OCF-to-net-income conversion, flag balance-sheet or liquidity anomalies, and generate JSON and Markdown reports.

## Checks & Metrics

- **Profitability & Cash Conversion:** Computes Gross Margin %, Operating Margin %, Free Cash Flow (`OCF - CapEx`), and `OCF / Net Income`.
- **Liquidity & Leverage:** Computes Current Ratio, Quick Ratio, and Debt-to-Equity.
- **Integrity & Anomaly Flags (`FIN-001`, `FIN-002`, `FIN-DUP`, `REV-001`, `BS-001`, `FCF-001`, `LIQ-001`):** Detects malformed JSON, duplicate periods, invalid revenue, balance-sheet mismatches, negative free cash flow, and sub-`1.00x` current ratios.
- **Dual Output & CI Exit Codes:** Emits `fin_analysis_report.json` and `fin_analysis_summary.md`, exiting with code `1` on hard `ERROR` issues.

## Quickstart

Requires **Python 3.10+** (standard library only).

```bash
git clone [https://github.com/B5IVE/fin-ratio-cashflow-auditor.git](https://github.com/B5IVE/fin-ratio-cashflow-auditor.git)
cd fin-ratio-cashflow-auditor

python3 analyze_financials.py sample_financials.jsonl
