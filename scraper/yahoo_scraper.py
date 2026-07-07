import re
from playwright.sync_api import sync_playwright
from config import BASE_URL, TARGET_PAGES, HEADLESS


def get_top150():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        for page_num in TARGET_PAGES:
            url = BASE_URL.format(page_num)
            print(f"{page_num}ページ目取得中...")

            page.goto(url, wait_until="networkidle")

            rows = page.locator("#item > table > tbody > tr")

            for i in range(rows.count()):
                row = rows.nth(i)
                tds = row.locator("td")

                try:
                    company_link = tds.nth(0).locator("a").first
                    company = company_link.inner_text().strip()
                    href = company_link.get_attribute("href")

                    match = re.search(r"/quote/([A-Za-z0-9]+)\.T", href)
                    code = match.group(1) if match else ""

                    price = tds.nth(1).locator("span.StyledNumber__value__3rXW").first.inner_text().strip()
                    diff_yen = tds.nth(2).locator("span.StyledNumber__value__3rXW").first.inner_text().strip()
                    diff_percent = tds.nth(2).locator("span.StyledNumber__value__3rXW").nth(1).inner_text().strip()
                    trading_value = tds.nth(3).locator("span.StyledNumber__value__3rXW").first.inner_text().strip()
                except Exception:
                    continue

                results.append({
                    "rank": len(results) + 1,
                    "code": code,
                    "company": company,
                    "price": price,
                    "diff_yen": diff_yen,
                    "diff_percent": diff_percent,
                    "trading_value": trading_value,
                })

        browser.close()

    return results