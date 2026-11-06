import pandas as pd

from app.crawler import BitcoinCrawler


def test_clean_removes_duplicates_and_fills_missing_day():
    raw = pd.DataFrame([
        {"time": 1704067200, "open": 42000, "high": 43000, "low": 41000, "close": 42500, "volumefrom": 10, "volumeto": 420000},
        {"time": 1704240000, "open": 43000, "high": 44000, "low": 42000, "close": 43500, "volumefrom": 11, "volumeto": 470000},
        {"time": 1704240000, "open": 43100, "high": 44100, "low": 42100, "close": 43600, "volumefrom": 12, "volumeto": 480000},
    ])

    cleaned = BitcoinCrawler.clean(raw)

    assert len(cleaned) == 3
    assert cleaned["date"].is_monotonic_increasing
    assert cleaned["close"].isna().sum() == 0
    assert cleaned.iloc[-1]["close"] == 43600

