"""Optional: fetch daily weather for Tunis area into climate_context.

Requires network and Python urllib. Example coordinates (tune for site):
  lat=36.8, lon=10.18

Usage (after schema exists):
  python scripts/fetch_open_meteo.py --db data/aquamind.sqlite --start 2024-01-01 --end 2025-12-31

See https://open-meteo.com/en/docs/historical-weather-api
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.request
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=Path("data/aquamind.sqlite"))
    p.add_argument("--lat", type=float, default=36.8065)
    p.add_argument("--lon", type=float, default=10.1815)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    args = p.parse_args()

    url = (
        "https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={args.lat}&longitude={args.lon}"
        f"&start_date={args.start}&end_date={args.end}"
        "&daily=temperature_2m_max,precipitation_sum"
        "&timezone=UTC"
    )
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = json.loads(resp.read().decode())

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    precip = daily.get("precipitation_sum", [])

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    for i, d in enumerate(dates):
        tm = tmax[i] if i < len(tmax) else None
        pr = precip[i] if i < len(precip) else None
        hw = 1 if tm is not None and tm >= 38 else 0  # illustrative heatwave threshold
        conn.execute(
            """
            INSERT INTO climate_context (context_date, temp_max_c, precip_mm, heatwave_flag, data_source)
            VALUES (?,?,?,?,?)
            ON CONFLICT(context_date) DO UPDATE SET
              temp_max_c=excluded.temp_max_c,
              precip_mm=excluded.precip_mm,
              heatwave_flag=excluded.heatwave_flag,
              data_source=excluded.data_source
            """,
            (d, tm, pr, hw, "open-meteo-archive"),
        )
    conn.commit()
    conn.close()
    print(f"Inserted/updated {len(dates)} rows in climate_context.")


if __name__ == "__main__":
    main()
