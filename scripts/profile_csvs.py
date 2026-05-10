"""One-off profile script for data inventory. Run: python scripts/profile_csvs.py"""
import csv
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = [
    (ROOT / "customerA_consumption.csv", ";"),
    (ROOT / "customerB_consumption.csv", ";"),
    (ROOT / "customerC_consumption.csv", ";"),
    (ROOT / "gym_consumption_data.csv", ","),
]


def parse_time(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def main():
    for path, delim in FILES:
        rows = 0
        devices: set[str] = set()
        categories: set[str] = set()
        subcats: set[str] = set()
        tags: set[str] = set()
        clients: set[str] = set()
        min_t = max_t = None
        bad_default = future_2030 = non_positive = overflow_like = 0
        min_cons = max_cons = None
        min_period = max_period = None
        fn = None
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=delim)
            fn = reader.fieldnames
            for row in reader:
                rows += 1
                if row.get("device"):
                    devices.add(row["device"])
                if row.get("main_category_name"):
                    categories.add(row["main_category_name"])
                if row.get("sub_category_name"):
                    subcats.add(row["sub_category_name"])
                if row.get("tag"):
                    tags.add(row["tag"])
                if row.get("client_id"):
                    clients.add(row["client_id"])
                ts = row.get("data_time") or row.get("data.time")
                dt = parse_time(ts) if ts else None
                if dt:
                    if min_t is None or dt < min_t:
                        min_t = dt
                    if max_t is None or dt > max_t:
                        max_t = dt
                    if dt.year in (1970, 2000):
                        bad_default += 1
                    if dt.year >= 2030:
                        future_2030 += 1
                cs = row.get("data_consumption") or row.get("data.consumption")
                try:
                    c = float(cs)
                    if min_cons is None or c < min_cons:
                        min_cons = c
                    if max_cons is None or c > max_cons:
                        max_cons = c
                    if c <= 0:
                        non_positive += 1
                    if c >= 1_000_000:
                        overflow_like += 1
                except Exception:
                    pass
                ps = row.get("data_period") or row.get("data.period")
                try:
                    p = float(ps)
                    if min_period is None or p < min_period:
                        min_period = p
                    if max_period is None or p > max_period:
                        max_period = p
                except Exception:
                    pass
        print("===", path.name, "===")
        print("columns:", fn)
        print("rows:", rows, "devices:", len(devices), "client_ids:", sorted(clients) if clients else "-")
        print("date_range:", min_t, "->", max_t)
        print(
            "categories:",
            sorted(categories) or "-",
            "| sub:",
            sorted(subcats) or "-",
            "| tags:",
            sorted(tags) or "-",
        )
        print("consumption min/max:", min_cons, max_cons, "| period min/max:", min_period, max_period)
        print(
            "quality: default1970_2000:",
            bad_default,
            "future2030+:",
            future_2030,
            "non_positive:",
            non_positive,
            "overflow>=1M:",
            overflow_like,
        )
        print()


if __name__ == "__main__":
    main()
