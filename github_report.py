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
"""


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
}}

h2 {{
    font-size: 18px;
    margin-top: 28px;
}}

.info, .section {{
    background: white;
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 16px;
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

@media (max-width: 600px) {{
    body {{
        margin: 8px;
    }}

    table {{
        font-size: 12px;
    }}

    th, td {{
        padding: 6px;
    }}

    td.company {{
        min-width: 180px;
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

<div class="table-wrap">
{render_table(merged_targets, merged=True)}
</div>
"""

    for snapshot in snapshots:
        html += f"""
<h2>{escape(snapshot["time"])} 取得結果</h2>
<p>ランキング取得：{len(snapshot["stocks"])}件 / 条件該当：{len(snapshot["targets"])}件</p>
<div class="table-wrap">
{render_table(snapshot["targets"], merged=False)}
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
