from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.screener import ScreenResult


def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value:+.1f}%"


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_json(results: Iterable[ScreenResult], output_path: str) -> None:
    rows = [row.to_dict() for row in results]
    Path(output_path).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_report(results: list[ScreenResult], output_path: str, top_n: int = 20) -> None:
    top_rows = results[:top_n]
    cards = "\n".join(
        f"""
        <div class="card">
          <div class="card-header">
            <div>
              <h3>{_escape(row.ticker)} <span>{_escape(row.name)}</span></h3>
              <p>{_escape(row.note)}</p>
            </div>
            <div class="zone {_escape(row.zone)}">{_escape(row.zone)}</div>
          </div>
          <div class="grid">
            <div><label>현재가</label><strong>{_fmt_money(row.price)}</strong></div>
            <div><label>ITP</label><strong>{_fmt_money(row.itp)}</strong></div>
            <div><label>매수상한</label><strong>{_fmt_money(row.buy_max)}</strong></div>
            <div><label>MOS</label><strong>{_fmt_pct(row.mos_itp)}</strong></div>
            <div><label>Signal</label><strong>{row.signal_score:.1f}</strong></div>
            <div><label>TA</label><strong>{row.ta_score:.1f}</strong></div>
            <div><label>FV</label><strong>{_fmt_money(row.fv)}</strong></div>
            <div><label>AP</label><strong>{_fmt_money(row.ap)}</strong></div>
            <div><label>Scenario PT</label><strong>{_fmt_money(row.scenario_pt)}</strong></div>
            <div><label>성장률</label><strong>{row.implied_growth:.3f}</strong></div>
            <div><label>MES</label><strong>{row.mes:.2f}</strong></div>
            <div><label>섹터</label><strong>{_escape(row.sector)}</strong></div>
          </div>
        </div>
        """
        for row in top_rows
    )

    table_rows = "\n".join(
        f"""
        <tr>
          <td>{_escape(row.ticker)}</td>
          <td>{_escape(row.name)}</td>
          <td>{_escape(row.zone)}</td>
          <td>{_fmt_money(row.price)}</td>
          <td>{_fmt_money(row.itp)}</td>
          <td>{_fmt_money(row.buy_max)}</td>
          <td>{_fmt_pct(row.mos_itp)}</td>
          <td>{row.signal_score:.1f}</td>
          <td>{row.ta_score:.1f}</td>
          <td>{_fmt_money(row.fv)}</td>
          <td>{_fmt_money(row.ap)}</td>
          <td>{_fmt_money(row.scenario_pt)}</td>
          <td>{row.implied_growth:.3f}</td>
          <td>{row.mes:.2f}</td>
          <td>{_escape(row.note)}</td>
        </tr>
        """
        for row in results
    )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ITP Ticker Screener</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #0b1020; color: #e6edf3; }}
    .wrap {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; }}
    .muted {{ color: #9fb0c3; margin-bottom: 24px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #131a2b; border: 1px solid #22304a; border-radius: 16px; padding: 16px; }}
    .card-header {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
    .card-header h3 {{ margin: 0; font-size: 20px; }}
    .card-header h3 span {{ display: block; font-size: 13px; color: #9fb0c3; font-weight: normal; margin-top: 4px; }}
    .card-header p {{ color: #c4d2df; font-size: 13px; line-height: 1.45; }}
    .zone {{ padding: 6px 10px; border-radius: 999px; font-size: 12px; font-weight: bold; white-space: nowrap; }}
    .zone.STRONG_BUY {{ background: #113b26; color: #77e0a5; }}
    .zone.BUY {{ background: #17355c; color: #87c3ff; }}
    .zone.WATCH {{ background: #4a3a10; color: #ffd976; }}
    .zone.HOLD {{ background: #46202a; color: #ff9eb1; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }}
    .grid div {{ background: #0f1525; border-radius: 12px; padding: 10px; }}
    .grid label {{ display: block; color: #8ba0b6; font-size: 12px; margin-bottom: 6px; }}
    .grid strong {{ font-size: 15px; }}
    .table-wrap {{ overflow-x: auto; background: #131a2b; border: 1px solid #22304a; border-radius: 16px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1200px; }}
    th, td {{ padding: 12px 10px; border-bottom: 1px solid #22304a; text-align: left; font-size: 13px; }}
    th {{ position: sticky; top: 0; background: #19233a; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>ITP Ticker Screener</h1>
    <div class="muted">ticker.txt 기준 선별 결과. 상위 {top_n}개 카드와 전체 테이블을 함께 제공합니다.</div>
    <div class="cards">{cards}</div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Name</th>
            <th>Zone</th>
            <th>Price</th>
            <th>ITP</th>
            <th>Buy Max</th>
            <th>MOS</th>
            <th>Signal</th>
            <th>TA</th>
            <th>FV</th>
            <th>AP</th>
            <th>Scenario PT</th>
            <th>Growth</th>
            <th>MES</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""
    Path(output_path).write_text(html, encoding="utf-8")
