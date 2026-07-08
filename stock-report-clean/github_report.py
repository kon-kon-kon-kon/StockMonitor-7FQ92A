from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


JST = ZoneInfo("Asia/Tokyo")
BASE_URL = "https://finance.yahoo.co.jp"
RANKING_URL = (
    "https://finance.yahoo.co.jp/stocks/ranking/"
    "tradingValueHigh?market=all&page={page}"
)
OUTPUT_PATH = Path("docs/data.json")
PAGES_TO_FETCH = 3
MAX_STOCKS = 150
DROP_THRESHOLD = float(os.getenv("DROP_THRESHOLD", "-3.0"))
REQUEST_INTERVAL_SECONDS = 1.0

QUOTE_PATH_PATTERN = re.compile(
    r"^/quote/(?P<code>[0-9A-Z]+)\.T/?(?:\?.*)?$"
)
ROW_VALUE_PATTERN = re.compile(
    r"(?P<price>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<quote_time>\d{1,2}:\d{2})\s*"
    r"(?P<diff>[+-]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<percent>[+-]?\d+(?:\.\d+)?)%\s*"
    r"(?P<trading_value>\d[\d,]*)"
)
SOURCE_TIME_PATTERN = re.compile(
    r"更新日時[：:]\s*(?P<date>\d{4}/\d{1,2}/\d{1,2})\s+"
    r"(?P<time>\d{1,2}:\d{2})"
)


@dataclass(frozen=True)
class ParsedStock:
    rank: int
    code: str
    company: str
    price: float
    diff_yen: float
    diff_percent: float
    trading_value: int
    quote_time: str

    def to_dict(self) -> dict[str, Any]:
        previous_close = self.price - self.diff_yen

        return {
            "rank": self.rank,
            "code": self.code,
            "company": self.company,
            "price": self.price,
            "diff_yen": self.diff_yen,
            "diff_percent": self.diff_percent,
            "trading_value": self.trading_value,
            "quote_time": self.quote_time,
            "previous_close": round(previous_close, 2),
            "price_10": round(previous_close * 0.90, 2),
            "price_12": round(previous_close * 0.88, 2),
            "price_14": round(previous_close * 0.86, 2),
        }


def build_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/149.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.7,en;q=0.6",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
        }
    )
    return session


def parse_number(value: str) -> float:
    return float(value.replace(",", "").replace("+", "").strip())


def find_stock_container(anchor: Tag, code: str) -> Tag | None:
    node: Tag | None = anchor

    for _ in range(9):
        parent = node.parent if node is not None else None
        if not isinstance(parent, Tag):
            return None

        text = " ".join(parent.stripped_strings)
        if code in text and "%" in text and ROW_VALUE_PATTERN.search(text):
            return parent

        node = parent

    return None


def parse_source_updated_at(soup: BeautifulSoup) -> str | None:
    page_text = " ".join(soup.stripped_strings)
    match = SOURCE_TIME_PATTERN.search(page_text)
    if not match:
        return None

    return f"{match.group('date').replace('/', '-')} {match.group('time')}"


def parse_ranking_page(
    html: str,
    page_number: int,
) -> tuple[list[ParsedStock], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    source_updated_at = parse_source_updated_at(soup)
    stocks: list[ParsedStock] = []
    seen_codes: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue

        href = str(anchor.get("href", ""))
        path = href
        if href.startswith(BASE_URL):
            path = href.removeprefix(BASE_URL)

        quote_match = QUOTE_PATH_PATTERN.match(path)
        if not quote_match:
            continue

        code = quote_match.group("code")
        if code in seen_codes:
            continue

        company = " ".join(anchor.stripped_strings).strip()
        if not company or company == code:
            continue

        container = find_stock_container(anchor, code)
        if container is None:
            continue

        row_text = " ".join(container.stripped_strings)
        value_match = ROW_VALUE_PATTERN.search(row_text)
        if value_match is None:
            continue

        try:
            price = parse_number(value_match.group("price"))
            diff_yen = parse_number(value_match.group("diff"))
            diff_percent = parse_number(value_match.group("percent"))
            trading_value = int(
                value_match.group("trading_value").replace(",", "")
            )
        except (TypeError, ValueError):
            continue

        rank = ((page_number - 1) * 50) + len(stocks) + 1
        stocks.append(
            ParsedStock(
                rank=rank,
                code=code,
                company=company,
                price=price,
                diff_yen=diff_yen,
                diff_percent=diff_percent,
                trading_value=trading_value,
                quote_time=value_match.group("quote_time"),
            )
        )
        seen_codes.add(code)

        if len(stocks) >= 50:
            break

    return stocks, source_updated_at


def fetch_top_stocks() -> tuple[list[ParsedStock], str | None]:
    session = build_session()
    all_stocks: list[ParsedStock] = []
    source_times: list[str] = []
    seen_codes: set[str] = set()

    for page in range(1, PAGES_TO_FETCH + 1):
        url = RANKING_URL.format(page=page)
        print(f"取得中: {url}")

        response = session.get(url, timeout=(10, 30))
        if response.status_code != 200:
            raise RuntimeError(
                f"ランキングページの取得に失敗しました。"
                f" page={page}, status={response.status_code}"
            )

        page_stocks, source_updated_at = parse_ranking_page(
            response.text,
            page,
        )

        if len(page_stocks) < 40:
            raise RuntimeError(
                f"ページ{page}から{len(page_stocks)}件しか解析できませんでした。"
                " Yahoo!ファイナンスのHTML構造が変わった可能性があります。"
            )

        for stock in page_stocks:
            if stock.code in seen_codes:
                continue
            all_stocks.append(stock)
            seen_codes.add(stock.code)

        if source_updated_at:
            source_times.append(source_updated_at)

        if page < PAGES_TO_FETCH:
            time.sleep(REQUEST_INTERVAL_SECONDS)

    all_stocks = all_stocks[:MAX_STOCKS]

    if len(all_stocks) < MAX_STOCKS:
        raise RuntimeError(
            f"150件の取得を想定していますが、{len(all_stocks)}件でした。"
        )

    latest_source_time = max(source_times) if source_times else None
    return all_stocks, latest_source_time


def create_output(
    all_stocks: list[ParsedStock],
    source_updated_at: str | None,
) -> dict[str, Any]:
    now = datetime.now(JST)

    targets = [
        stock.to_dict()
        for stock in all_stocks
        if stock.diff_percent <= DROP_THRESHOLD
    ]
    targets.sort(key=lambda stock: stock["diff_percent"])

    return {
        "date": now.strftime("%Y-%m-%d"),
        "updated_at": now.strftime("%H:%M:%S"),
        "source_updated_at": source_updated_at,
        "threshold": DROP_THRESHOLD,
        "source_count": len(all_stocks),
        "count": len(targets),
        "stocks": targets,
    }


def write_json_atomic(data: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=output_path.parent,
        prefix="data-",
        suffix=".tmp",
        delete=False,
    ) as temporary_file:
        json.dump(
            data,
            temporary_file,
            ensure_ascii=False,
            indent=2,
        )
        temporary_file.write("\n")
        temporary_path = Path(temporary_file.name)

    temporary_path.replace(output_path)


def main() -> int:
    print(f"抽出条件: 前日比 {DROP_THRESHOLD:.1f}% 以下")

    try:
        all_stocks, source_updated_at = fetch_top_stocks()
        output = create_output(all_stocks, source_updated_at)
        write_json_atomic(output, OUTPUT_PATH)
    except Exception as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1

    print(f"取得件数: {output['source_count']}件")
    print(f"該当件数: {output['count']}件")
    print(f"保存先: {OUTPUT_PATH}")
    print(f"更新時刻: {output['date']} {output['updated_at']} JST")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
