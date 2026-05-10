"""Quick sanity checks on data/aquamind.sqlite. Run: python scripts/validate_db.py"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "aquamind.sqlite"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("motif_patterns:")
    for row in conn.execute(
        "SELECT motif_name, pattern_count FROM motif_patterns ORDER BY pattern_count DESC"
    ):
        print(dict(row))
    print("gym_device_inference rows:", conn.execute("SELECT COUNT(*) FROM gym_device_inference").fetchone()[0])
    print(
        "daily_consumption_profile rows:",
        conn.execute("SELECT COUNT(*) FROM daily_consumption_profile").fetchone()[0],
    )
    print(
        "anomaly_candidates:",
        conn.execute("SELECT COUNT(*) FROM anomaly_candidates").fetchone()[0],
    )
    print("hard flags by code:")
    for row in conn.execute(
        """
        SELECT flag_code, COUNT(*) AS n
        FROM data_quality_flags
        WHERE severity = 'hard'
        GROUP BY flag_code
        ORDER BY n DESC
        """
    ):
        print(dict(row))


if __name__ == "__main__":
    main()
