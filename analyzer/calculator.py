from config import DROP_THRESHOLD


def to_float(value):
    if value is None:
        return None

    value = str(value).replace(",", "").replace("+", "").replace("%", "").strip()

    try:
        return float(value)
    except ValueError:
        return None


def analyze_stocks(stocks):
    results = []

    for stock in stocks:
        price = to_float(stock["price"])
        diff_yen = to_float(stock["diff_yen"])
        diff_percent = to_float(stock["diff_percent"])

        if price is None or diff_yen is None or diff_percent is None:
            continue

        if diff_percent > DROP_THRESHOLD:
            continue

        previous_close = price - diff_yen

        stock["price_num"] = price
        stock["diff_yen_num"] = diff_yen
        stock["diff_percent_num"] = diff_percent
        stock["previous_close"] = previous_close
        stock["price_10"] = previous_close * 0.90
        stock["price_12"] = previous_close * 0.88
        stock["price_14"] = previous_close * 0.86

        results.append(stock)

    return results