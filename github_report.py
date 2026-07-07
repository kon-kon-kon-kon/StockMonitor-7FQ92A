import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from html import escape

from scraper.yahoo_scraper import get_top150
from analyzer.calculator import analyze_stocks


DOCS_DIR = Path("docs")
DATA_PATH = DOCS_DIR / "data.json"
INDEX_PATH = DOCS_DIR / "index.html"


def now_jst():
    return datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=9))
    )


def load_data(today):
    if not DATA_PATH.exists():
        return {"date": today, "snapshots": []}

    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"date": today, "snapshots": []}

    if data.get("date") != today:
        return {"date": today, "snapshots": []}

    return data


def save_data(data):
    DOCS_DIR.mkdir(exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def merge_targets(snapshots):
    merged = {}

    for snapshot in snapshots:
        for stock in snapshot["targets"]:
            code = stock["code"]

            if code not in merged:
                stock_copy = stock.copy()
                stock_copy["first_detected"] = snapshot["time"]
                stock_copy["detected_times"] = [snapshot["time"]]
                stock_copy["detected_count"] = 1
                merged[code] = stock_copy
            else:
                old = merged[code]
                stock_copy = stock.copy()
                stock_copy["first_detected"] = old["first_detected"]
                stock_copy["detected_times"] = old["detected_times"] + [snapshot["time"]]
                stock_copy["detected_count"] = len(stock_copy["detected_times"])
                merged[code] = stock_copy

    return list(merged.values())


def render_table(targets, merged=False):
    rows = ""

    for index, stock in enumerate(targets):
        row_class = "row-yellow" if index % 2 == 0 else "row-pink"

        first_detected = stock.get("first_detected", "-") if merged else "-"
        detected_count = stock.get("detected_count", "-") if merged else "-"

        rows += f"""
<tr class="{row_class}">
<td>{escape(str(first_detected))}</td>
<td>{escape(str(detected_count))}</td>
<td>{stock["rank"]}</td>
<td>{escape(stock["code"])}</td>
<td class="company">{escape(stock["company"])}</td>
<td>{stock["price_num"]:,.1f}</td>
<td>{stock["previous_close"]:,.1f}</td>
<td>{stock["diff_percent_num"]:.2f}%</td>
<td>{stock["price_10"]:,.1f}</td>
<td>{stock["price_12"]:,.1f}</td>
<td>{stock["price_14"]:,.1f}</td>
<td><a href="https://finance.yahoo.co.jp/quote/{stock["code"]}.T" target="_blank">開く</a></td>
</tr>
"""

    return f"""
<div class="table-wrap pc-only">
<table>
<thead>
<tr>
<th>初検出</th>
<th>出現</th>
<th>順位</th>
<th>コード</th>
<th>会社名</th>
<th>現在値</th>
<th>前日終値</th>
<th>下落率</th>
<th>10%</th>
<th>12%</th>
<th>14%</th>
<th>Yahoo</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
</div>
"""


def render_cards(targets, merged=False):
    cards = ""

    for index, stock in enumerate(targets):
        card_class = "card-yellow" if index % 2 == 0 else "card-pink"

        first_detected = stock.get("first_detected", "-") if merged else "-"
        detected_count = stock.get("detected_count", "-") if merged else "-"

        cards += f"""
<div class="stock-card {card_class}">
    <div class="card-header">
        <div>
            <div class="code">{escape(stock["code"])}</div>
            <div class="company-name">{escape(stock["company"])}</div>
        </div>
        <div class="drop">{stock["diff_percent_num"]:.2f}%</div>
    </div>

    <div class="meta">
        <span>初検出：{escape(str(first_detected))}</span>
        <span>出現：{escape(str(detected_count))}回</span>
        <span>順位：{stock["rank"]}位</span>
    </div>

    <div class="price-grid">
        <div>
            <span class="label">現在値</span>
            <strong>{stock["price_num"]:,.1f}</strong>
        </div>
        <div>
            <span class="label">前日終値</span>
            <strong>{stock["previous_close"]:,.1f}</strong>
        </div>
    </div>

    <div class="target-grid">
        <div>
            <span class="label">10%</span>
            <strong>{stock["price_10"]:,.1f}</strong>
        </div>
        <div>
            <span class="label">12%</span>
            <strong>{stock["price_12"]:,.1f}</strong>
        </div>
        <div>
            <span class="label">14%</span>
            <strong>{stock["price_14"]:,.1f}</strong>
        </div>
    </div>

    <a class="yahoo-button" href="https://finance.yahoo.co.jp/quote/{stock["code"]}.T" target="_blank">
        Yahooで開く
    </a>
</div>
"""

    return f"""
<div class="mobile-only">
{cards}
</div>
"""


def render_result_block(targets, merged=False):
    return render_cards(targets, merged=merged) + render_table(targets, merged=merged)


def create_index(data):
    snapshots = data["snapshots"]
    merged_targets = merge_targets(snapshots)
    updated_at = snapshots[-1]["time"] if snapshots else "-"

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="60">
<meta name="theme-color" content="#333333">
<link rel="manifest" href="./manifest.json">
<title>株分析ツール</title>

<style>
body {{
    font-family: Meiryo, sans-serif;
    background: #f5f6f8;
    margin: 12px;
    color: #222;
}}

h1 {{
    font-size: 22px;
    margin-bottom: 12px;
}}

h2 {{
    font-size: 18px;
    margin-top: 28px;
}}

.info, .section {{
    background: white;
    padding: 12px;
    border-radius: 10px;
    margin-bottom: 16px;
    border: 1px solid #ddd;
}}

.info p, .section p {{
    margin: 5px 0;
}}

.table-wrap {{
    overflow-x: auto;
}}

table {{
    border-collapse: collapse;
    width: 100%;
    background: white;
    margin-bottom: 30px;
    font-size: 14px;
}}

th {{
    background: #333;
    color: white;
    padding: 8px;
    position: sticky;
    top: 0;
    white-space: nowrap;
}}

td {{
    border: 1px solid #ddd;
    padding: 7px;
    text-align: right;
    white-space: nowrap;
}}

td.company {{
    text-align: left;
    min-width: 260px;
}}

tr.row-yellow {{
    background: #fff7d6;
}}

tr.row-pink {{
    background: #ffe3ec;
}}

a {{
    color: #0066cc;
    text-decoration: none;
}}

.mobile-only {{
    display: none;
}}

.stock-card {{
    border-radius: 14px;
    padding: 14px;
    margin-bottom: 14px;
    border: 1px solid #ddd;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
}}

.card-yellow {{
    background: #fff7d6;
}}

.card-pink {{
    background: #ffe3ec;
}}

.card-header {{
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: flex-start;
    margin-bottom: 10px;
}}

.code {{
    font-size: 18px;
    font-weight: bold;
}}

.company-name {{
    font-size: 15px;
    font-weight: bold;
    line-height: 1.4;
}}

.drop {{
    font-size: 20px;
    font-weight: bold;
    color: #b00020;
    white-space: nowrap;
}}

.meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 13px;
    margin-bottom: 12px;
}}

.meta span {{
    background: rgba(255,255,255,0.7);
    padding: 4px 8px;
    border-radius: 999px;
}}

.price-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 10px;
}}

.target-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
    margin-bottom: 12px;
}}

.price-grid div,
.target-grid div {{
    background: rgba(255,255,255,0.75);
    border-radius: 10px;
    padding: 8px;
    text-align: right;
}}

.label {{
    display: block;
    font-size: 12px;
    color: #555;
    margin-bottom: 4px;
    text-align: left;
}}

.yahoo-button {{
    display: block;
    text-align: center;
    background: #333;
    color: white;
    padding: 10px;
    border-radius: 10px;
    font-weight: bold;
}}

@media (max-width: 700px) {{
    body {{
        margin: 8px;
    }}

    .pc-only {{
        display: none;
    }}

    .mobile-only {{
        display: block;
    }}

    .history-section {{
        display: none;
    }}

    h1 {{
        font-size: 21px;
    }}

    h2 {{
        font-size: 17px;
    }}
}}
</style>
</head>

<body>
<h1>株分析ツール</h1>

<div class="info">
<p>日付：{escape(data["date"])}</p>
<p>最新更新：{escape(updated_at)}</p>
<p>対象：売買代金ランキング150位以内</p>
<p>抽出条件：前日比 -6.0% 以下</p>
<p>ページは60秒ごとに自動更新されます。</p>
</div>

<div class="section">
<h2>統合一覧</h2>
<p>重複銘柄は1件だけ表示します。複数回出た場合は最新データを表示します。</p>
<p>該当件数：{len(merged_targets)}件</p>
</div>

{render_result_block(merged_targets, merged=True)}
"""

    for snapshot in snapshots:
        html += f"""
<div class="history-section">
<h2>{escape(snapshot["time"])} 取得結果</h2>
<p>ランキング取得：{len(snapshot["stocks"])}件 / 条件該当：{len(snapshot["targets"])}件</p>
{render_result_block(snapshot["targets"], merged=False)}
</div>
"""

    html += """
<script>
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("./service-worker.js");
}
</script>
</body>
</html>
"""

    INDEX_PATH.write_text(html, encoding="utf-8")


def main():
    now = now_jst()
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    print(f"{current_time} 取得開始")

    data = load_data(today)

    stocks = get_top150()
    targets = analyze_stocks(stocks)

    data["snapshots"] = [
        s for s in data["snapshots"]
        if s["time"] != current_time
    ]

    data["snapshots"].append({
        "time": current_time,
        "stocks": stocks,
        "targets": targets,
    })

    data["snapshots"].sort(key=lambda x: x["time"])

    save_data(data)
    create_index(data)

    print(f"{current_time} 取得完了：{len(stocks)}件 / 該当 {len(targets)}件")


if __name__ == "__main__":
    main()
