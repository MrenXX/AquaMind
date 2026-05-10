"""
Build AquaMind SQLite database from WaterSec CSVs.
Run from repo root:  python scripts/etl/build_database.py
Output: data/aquamind.sqlite
"""
from __future__ import annotations

import csv
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "aquamind.sqlite"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONSUMPTION_OVERFLOW = 1_000_000
KNOWN_OVERFLOW_VALUES = {4294967295.0, float(4294967295)}
MAX_DURATION_SEC = 7 * 24 * 3600  # 7 days
FUTURE_YEAR_CUTOFF = 2030  # flag timestamps with year >= this

SITE_MAP = {
    "customerA": ("customerA", "office", "Offices"),
    "customerB": ("customerB", "sanitary_block", "Bloc sanitaire"),
    "customerC": ("customerC", "residential_bathroom", "Bathroom"),
    "gym": ("gym", "gym", None),
}


def parse_ts(s: str) -> datetime | None:
    if not s or not s.strip():
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def season_for_month(m: int) -> str:
    if m in (12, 1, 2):
        return "winter"
    if m in (3, 4, 5):
        return "spring"
    if m in (6, 7, 8):
        return "summer"
    return "autumn"


def daypart(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def percentile_linear(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    k = (n - 1) * p / 100.0
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return float(d0 + d1)


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 2 or n != len(y):
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    deny = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if denx == 0 or deny == 0:
        return 0.0
    return num / (denx * deny)


# ---------------------------------------------------------------------------
# Load raw CSVs
# ---------------------------------------------------------------------------


def load_raw(conn: sqlite3.Connection) -> None:
    loads = [
        (
            "raw_customer_a_consumption",
            ROOT / "customerA_consumption.csv",
            ";",
            [
                "device",
                "data_consumption",
                "data_time",
                "data_period",
                "tag",
                "main_category_name",
                "type",
                "client_id",
            ],
        ),
        (
            "raw_customer_b_consumption",
            ROOT / "customerB_consumption.csv",
            ";",
            [
                "device",
                "data_consumption",
                "data_time",
                "data_period",
                "tag",
                "main_category_name",
                "type",
                "client_id",
            ],
        ),
        (
            "raw_customer_c_consumption",
            ROOT / "customerC_consumption.csv",
            ";",
            [
                "device",
                "data_consumption",
                "data_time",
                "data_period",
                "tag",
                "main_category_name",
                "sub_category_name",
                "type",
                "client_id",
            ],
        ),
    ]
    for table, path, delim, cols in loads:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=delim)
            ph = ",".join("?" * (len(cols) + 1))
            sql = f"INSERT INTO {table} ({','.join(cols)}, source_file) VALUES ({ph})"
            for row in reader:
                vals = [row.get(c) for c in cols] + [path.name]
                conn.execute(sql, vals)
    # Gym
    gym_path = ROOT / "gym_consumption_data.csv"
    with gym_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        sql = """
        INSERT INTO raw_gym_consumption
        (data_consumption, data_time, data_period, device, source_file)
        VALUES (?,?,?,?,?)
        """
        for row in reader:
            conn.execute(
                sql,
                [
                    row.get("data.consumption"),
                    row.get("data.time"),
                    row.get("data.period"),
                    row.get("device"),
                    gym_path.name,
                ],
            )
    conn.commit()


def insert_normalized_events(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM consumption_events")
    customer_specs: list[tuple[str, str, str, str | None]] = [
        ("raw_customer_a_consumption", "customerA", "customerA_consumption.csv", None),
        ("raw_customer_b_consumption", "customerB", "customerB_consumption.csv", None),
        (
            "raw_customer_c_consumption",
            "customerC",
            "customerC_consumption.csv",
            "sub_category_name",
        ),
    ]
    for raw_table, profile_key, _src_name, sub_col in customer_specs:
        prof, site_type, default_main = SITE_MAP[profile_key]
        if sub_col:
            rows = conn.execute(
                f"SELECT raw_row_id, device, data_consumption, data_time, data_period, tag, "
                f"main_category_name, sub_category_name, type, client_id, source_file "
                f"FROM {raw_table}"
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT raw_row_id, device, data_consumption, data_time, data_period, tag, "
                f"main_category_name, type, client_id, source_file FROM {raw_table}"
            ).fetchall()
        for tup in rows:
            if sub_col:
                rid, device, cons, ts, period, tag, main_cat, sub_cat, typ, client_id, src = tup
            else:
                rid, device, cons, ts, period, tag, main_cat, typ, client_id, src = tup
                sub_cat = None
            dt = parse_ts(ts or "")
            event_date = dt.date().isoformat() if dt else "1970-01-01"
            ts_iso = dt.isoformat().replace("+00:00", "Z") if dt else "1970-01-01T00:00:00Z"
            try:
                cval = float(cons)
            except (TypeError, ValueError):
                cval = 0.0
            try:
                dsec = float(period) if period not in (None, "") else None
            except (TypeError, ValueError):
                dsec = None
            flow = None
            if dsec is not None and dsec > 0:
                flow = cval / dsec
            conn.execute(
                """
                INSERT INTO consumption_events (
                  raw_table, raw_row_id, source_file, customer_profile, site_type,
                  device_id, timestamp_utc, event_date, consumption_raw, duration_seconds,
                  flow_rate_raw, water_type, main_category, sub_category, client_id, sensor_type
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    raw_table,
                    rid,
                    src,
                    prof,
                    site_type,
                    device or "",
                    ts_iso,
                    event_date,
                    cval,
                    dsec,
                    flow,
                    tag,
                    main_cat or default_main,
                    sub_cat,
                    client_id,
                    typ,
                ),
            )
    # Gym from raw_gym
    gym_rows = conn.execute(
        "SELECT raw_row_id, data_consumption, data_time, data_period, device, source_file "
        "FROM raw_gym_consumption"
    ).fetchall()
    prof, site_type, _ = SITE_MAP["gym"]
    for rid, cons, ts, period, device, src in gym_rows:
        dt = parse_ts(ts or "")
        event_date = dt.date().isoformat() if dt else "1970-01-01"
        ts_iso = dt.isoformat().replace("+00:00", "Z") if dt else "1970-01-01T00:00:00Z"
        try:
            cval = float(cons)
        except (TypeError, ValueError):
            cval = 0.0
        try:
            dsec = float(period) if period not in (None, "") else None
        except (TypeError, ValueError):
            dsec = None
        flow = None
        if dsec is not None and dsec > 0:
            flow = cval / dsec
        conn.execute(
            """
            INSERT INTO consumption_events (
              raw_table, raw_row_id, source_file, customer_profile, site_type,
              device_id, timestamp_utc, event_date, consumption_raw, duration_seconds,
              flow_rate_raw, water_type, main_category, sub_category, client_id, sensor_type
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "raw_gym_consumption",
                rid,
                src,
                prof,
                site_type,
                device or "",
                ts_iso,
                event_date,
                cval,
                dsec,
                flow,
                None,
                "",
                "",
                None,
                None,
            ),
        )
    conn.commit()


def apply_quality_flags(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM data_quality_flags")
    rows = conn.execute(
        """
        SELECT event_id, timestamp_utc, consumption_raw, duration_seconds, flow_rate_raw,
               customer_profile, main_category
        FROM consumption_events
        """
    ).fetchall()
    inserts = []
    for eid, ts_s, cons, dur, flow, prof, main_cat in rows:
        dt = parse_ts(ts_s)
        # DEFAULT_TIMESTAMP
        if dt and dt.year in (1970, 2000):
            inserts.append(
                (
                    eid,
                    "DEFAULT_TIMESTAMP",
                    "hard",
                    "Clock reset or default epoch timestamp",
                    "timestamp_utc",
                    ts_s,
                )
            )
        # FUTURE_TIMESTAMP
        if dt and dt.year >= FUTURE_YEAR_CUTOFF:
            inserts.append(
                (
                    eid,
                    "FUTURE_TIMESTAMP",
                    "hard",
                    "Timestamp beyond acceptable observation window",
                    "timestamp_utc",
                    ts_s,
                )
            )
        # NON_POSITIVE_CONSUMPTION
        if cons is None or cons <= 0:
            inserts.append(
                (
                    eid,
                    "NON_POSITIVE_CONSUMPTION",
                    "hard",
                    "Zero or negative consumption",
                    "consumption_raw",
                    str(cons),
                )
            )
        # OVERFLOW_EXTREME
        if cons >= CONSUMPTION_OVERFLOW or cons in KNOWN_OVERFLOW_VALUES:
            inserts.append(
                (
                    eid,
                    "OVERFLOW_EXTREME",
                    "hard",
                    "Overflow-like or extreme consumption magnitude",
                    "consumption_raw",
                    str(cons),
                )
            )
        # Duration: zero/missing is common (e.g. gym); keep event trusted for consumption totals.
        if dur is None or dur == 0:
            inserts.append(
                (
                    eid,
                    "ZERO_OR_MISSING_DURATION",
                    "soft",
                    "Duration zero or missing; flow_rate may be unavailable",
                    "duration_seconds",
                    str(dur),
                )
            )
        elif dur < 0 or dur > MAX_DURATION_SEC:
            inserts.append(
                (
                    eid,
                    "IMPOSSIBLE_DURATION",
                    "hard",
                    "Negative or implausibly long duration",
                    "duration_seconds",
                    str(dur),
                )
            )
        # SOFT: missing category on customer files
        if prof != "gym" and (not main_cat or main_cat.strip() == ""):
            inserts.append(
                (
                    eid,
                    "MISSING_MAIN_CATEGORY",
                    "soft",
                    "Main category empty",
                    "main_category",
                    main_cat or "",
                )
            )

    conn.executemany(
        """
        INSERT INTO data_quality_flags (event_id, flag_code, severity, reason, field_name, field_value)
        VALUES (?,?,?,?,?,?)
        """,
        inserts,
    )
    conn.commit()


def recreate_trusted_view(conn: sqlite3.Connection) -> None:
    conn.execute("DROP VIEW IF EXISTS trusted_events")
    conn.execute(
        """
        CREATE VIEW trusted_events AS
        SELECT e.*
        FROM consumption_events e
        WHERE e.event_id NOT IN (
          SELECT f.event_id FROM data_quality_flags f WHERE f.severity = 'hard'
        )
        """
    )
    conn.commit()


def populate_calendar_context(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM calendar_context")
    rows = conn.execute(
        "SELECT event_id, timestamp_utc FROM consumption_events"
    ).fetchall()
    for eid, ts_s in rows:
        dt = parse_ts(ts_s)
        if not dt:
            hour = 0
            dow = 0
            month = 1
        else:
            hour = dt.hour
            dow = dt.weekday()
            month = dt.month
        is_weekend = 1 if dow >= 5 else 0
        season = season_for_month(month)
        dp = daypart(hour)
        is_night = 1 if hour >= 22 or hour < 6 else 0
        conn.execute(
            """
            INSERT INTO calendar_context (
              event_id, hour_of_day, day_of_week, is_weekend, month, season, daypart, is_night
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (eid, hour, dow, is_weekend, month, season, dp, is_night),
        )
    conn.commit()


def simplify_daily_profile_peak_hour(conn: sqlite3.Connection) -> None:
    """Recompute peak_hour per group with a simpler Python pass."""
    conn.execute("DELETE FROM daily_consumption_profile")
    rows = conn.execute(
        """
        SELECT e.event_id, e.event_date, e.customer_profile, e.site_type, e.device_id,
               e.main_category, e.sub_category, e.consumption_raw, e.duration_seconds,
               e.flow_rate_raw
        FROM trusted_events e
        """
    ).fetchall()
    groups: dict[tuple, dict] = defaultdict(
        lambda: {
            "consumptions": [],
            "durations": [],
            "flows": [],
            "hours": [],
        }
    )
    event_hours = conn.execute(
        "SELECT event_id, hour_of_day FROM calendar_context"
    ).fetchall()
    eid_to_hour = dict(event_hours)

    for tup in rows:
        eid = tup[0]
        key = (
            tup[1],
            tup[2],
            tup[3],
            tup[4],
            tup[5] or "",
            tup[6] or "",
        )
        g = groups[key]
        g["consumptions"].append(tup[7])
        if tup[8] is not None:
            g["durations"].append(tup[8])
        if tup[9] is not None:
            g["flows"].append(tup[9])
        g["hours"].append(eid_to_hour.get(eid, 0))

    for key, g in groups.items():
        profile_date, cust, site, dev, main_cat, sub_cat = key
        n = len(g["consumptions"])
        total_c = sum(g["consumptions"])
        total_d = sum(g["durations"]) if g["durations"] else None
        avg_c = total_c / n if n else None
        avg_f = statistics.mean(g["flows"]) if g["flows"] else None
        peak_h = None
        if g["hours"]:
            hc: dict[int, int] = defaultdict(int)
            for h in g["hours"]:
                hc[h] += 1
            peak_h = max(hc, key=lambda x: hc[x])
        conn.execute(
            """
            INSERT INTO daily_consumption_profile (
              profile_date, customer_profile, site_type, device_id, main_category, sub_category,
              event_count, total_consumption, avg_event_consumption, total_duration_seconds,
              avg_flow_rate, peak_hour
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                profile_date,
                cust,
                site,
                dev,
                main_cat,
                sub_cat,
                n,
                total_c,
                avg_c,
                total_d,
                avg_f,
                peak_h,
            ),
        )
    conn.commit()


def build_device_baselines(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM device_baselines")
    rows = conn.execute(
        """
        SELECT e.customer_profile, e.device_id, e.consumption_raw, e.duration_seconds,
               c.is_night, c.is_weekend, e.event_date
        FROM trusted_events e
        JOIN calendar_context c ON c.event_id = e.event_id
        """
    ).fetchall()
    by_dev: dict[tuple, dict] = defaultdict(
        lambda: {
            "consumptions": [],
            "durations": [],
            "dates": set(),
            "night": 0,
            "weekend": 0,
            "total": 0,
        }
    )
    for prof, dev, cons, dur, is_night, is_weekend, ed in rows:
        key = (prof, dev)
        d = by_dev[key]
        d["consumptions"].append(cons)
        if dur is not None:
            d["durations"].append(dur)
        d["dates"].add(ed)
        d["total"] += 1
        if is_night:
            d["night"] += 1
        if is_weekend:
            d["weekend"] += 1

    for (prof, dev), d in by_dev.items():
        consumptions = sorted(d["consumptions"])
        durations = sorted(d["durations"])
        n = d["total"]
        med_c = statistics.median(consumptions) if consumptions else None
        p95_c = percentile_linear(consumptions, 95)
        p99_c = percentile_linear(consumptions, 99)
        med_d = statistics.median(durations) if durations else None
        p95_d = percentile_linear(durations, 95) if durations else None
        ndays = max(1, len(d["dates"]))
        avg_daily = sum(consumptions) / ndays
        night_rate = d["night"] / n if n else 0
        weekend_rate = d["weekend"] / n if n else 0
        # active hours: hours with any event (approximate from consumption_events)
        hours_rows = conn.execute(
            """
            SELECT cc.hour_of_day, COUNT(*) FROM trusted_events e
            JOIN calendar_context cc ON cc.event_id = e.event_id
            WHERE e.customer_profile=? AND e.device_id=?
            GROUP BY cc.hour_of_day ORDER BY COUNT(*) DESC
            """,
            (prof, dev),
        ).fetchall()
        if hours_rows:
            hrs = [h for h, _ in hours_rows if _ > 0]
            if hrs:
                ah_start, ah_end = min(hrs), max(hrs)
            else:
                ah_start = ah_end = None
        else:
            ah_start = ah_end = None

        conn.execute(
            """
            INSERT INTO device_baselines (
              customer_profile, device_id, event_count, median_consumption, p95_consumption,
              p99_consumption, median_duration, p95_duration, night_event_rate, weekend_event_rate,
              avg_daily_consumption, active_hour_start, active_hour_end
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                prof,
                dev,
                n,
                med_c,
                p95_c,
                p99_c,
                med_d,
                p95_d,
                night_rate,
                weekend_rate,
                avg_daily,
                ah_start,
                ah_end,
            ),
        )
    conn.commit()


def build_fixture_signatures(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM fixture_signatures")
    for fx in ("Flush", "Sink", "Tap"):
        rows = conn.execute(
            """
            SELECT consumption_raw, duration_seconds, flow_rate_raw
            FROM trusted_events
            WHERE customer_profile='customerC' AND sub_category=?
            """,
            (fx,),
        ).fetchall()
        if not rows:
            continue
        cons_list = sorted(float(r[0]) for r in rows if r[0] is not None)
        dur_list = sorted(float(r[1]) for r in rows if r[1] is not None)
        flow_list = sorted(float(r[2]) for r in rows if r[2] is not None)
        conn.execute(
            """
            INSERT INTO fixture_signatures (
              fixture_type, sample_count, median_consumption, p25_consumption, p75_consumption,
              median_duration, p25_duration, p75_duration, median_flow_rate
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                fx,
                len(rows),
                statistics.median(cons_list),
                percentile_linear(cons_list, 25),
                percentile_linear(cons_list, 75),
                statistics.median(dur_list) if dur_list else None,
                percentile_linear(dur_list, 25) if dur_list else None,
                percentile_linear(dur_list, 75) if dur_list else None,
                statistics.median(flow_list) if flow_list else None,
            ),
        )
    conn.commit()


def mine_motifs(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM motif_patterns")
    evs = conn.execute(
        """
        SELECT e.event_id, e.timestamp_utc, e.sub_category, e.consumption_raw, e.device_id
        FROM trusted_events e
        WHERE e.customer_profile='customerC' AND e.sub_category IN ('Flush','Sink','Tap')
        ORDER BY e.timestamp_utc
        """
    ).fetchall()

    @dataclass
    class Ev:
        event_id: int
        ts: datetime
        sub: str
        cons: float
        device_id: str

    parsed: list[Ev] = []
    for eid, ts_s, sub, cons, did in evs:
        dt = parse_ts(ts_s)
        if not dt or not sub:
            continue
        parsed.append(Ev(eid, dt, sub, float(cons), did or ""))

    def window_motif(
        name: str,
        from_sub: str,
        to_sub: str,
        max_seconds: float,
        interpretation: str,
    ) -> None:
        count = 0
        delays: list[float] = []
        examples: list[int] = []
        total_water = 0.0
        i = 0
        while i < len(parsed):
            if parsed[i].sub != from_sub:
                i += 1
                continue
            start = parsed[i]
            j = i + 1
            while j < len(parsed):
                delta = (parsed[j].ts - start.ts).total_seconds()
                if delta > max_seconds:
                    break
                if parsed[j].sub == to_sub:
                    count += 1
                    delays.append(delta)
                    total_water += start.cons + parsed[j].cons
                    if len(examples) < 6:
                        examples.extend([start.event_id, parsed[j].event_id])
                    break
                j += 1
            i += 1
        med_del = statistics.median(delays) if delays else None
        conn.execute(
            """
            INSERT INTO motif_patterns (
              motif_name, pattern_count, median_delay_seconds, example_event_ids,
              total_consumption_involved, interpretation
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                name,
                count,
                med_del,
                json.dumps(examples),
                total_water,
                interpretation,
            ),
        )

    window_motif(
        "Flush_to_Sink_120s",
        "Flush",
        "Sink",
        120,
        "Hand-washing or sink use within 2 minutes after flush (hygiene-related sequence).",
    )
    window_motif(
        "Flush_to_Sink_300s",
        "Flush",
        "Sink",
        300,
        "Sink use within 5 minutes after flush.",
    )
    window_motif(
        "Tap_to_Sink_120s",
        "Tap",
        "Sink",
        120,
        "Tap then sink within 2 minutes (possible multi-fixture use).",
    )

    # Repeated Tap same device within 60s
    rep_tap = 0
    ex_rt: list[int] = []
    i = 0
    while i < len(parsed) - 1:
        if parsed[i].sub == "Tap" and parsed[i + 1].sub == "Tap":
            if parsed[i].device_id == parsed[i + 1].device_id:
                dt = (parsed[i + 1].ts - parsed[i].ts).total_seconds()
                if 0 <= dt <= 60:
                    rep_tap += 1
                    if len(ex_rt) < 6:
                        ex_rt.extend([parsed[i].event_id, parsed[i + 1].event_id])
        i += 1
    conn.execute(
        """
        INSERT INTO motif_patterns (
          motif_name, pattern_count, median_delay_seconds, example_event_ids,
          total_consumption_involved, interpretation
        ) VALUES (?,?,?,?,?,?)
        """,
        (
            "Repeated_Tap_60s_same_device",
            rep_tap,
            None,
            json.dumps(ex_rt),
            None,
            "Two tap events on the same device within one minute.",
        ),
    )

    conn.commit()


def infer_fixtures_ab(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM inferred_fixture_events")
    sigs = conn.execute(
        "SELECT fixture_type, median_consumption, median_duration FROM fixture_signatures"
    ).fetchall()
    if not sigs:
        conn.commit()
        return
    centroids = {fx: (mc or 0, md or 0) for fx, mc, md in sigs}

    rows = conn.execute(
        """
        SELECT event_id, consumption_raw, duration_seconds
        FROM trusted_events
        WHERE customer_profile IN ('customerA','customerB')
        """
    ).fetchall()

    def dist(c: float, d: float, fx: str) -> float:
        mc, md = centroids[fx]
        return (c - mc) ** 2 + ((d or 0) - md) ** 2

    for eid, cons, dur in rows:
        scores = {fx: dist(float(cons), float(dur) if dur is not None else 0, fx) for fx in centroids}
        best = min(scores, key=lambda k: scores[k])
        vals_sorted = sorted(scores.values())
        second = vals_sorted[1] if len(vals_sorted) > 1 else vals_sorted[0]
        denom = scores[best] + second + 1e-9
        confidence = max(0.0, min(1.0, 1.0 - scores[best] / denom))
        reason = (
            f"Nearest fixture centroid by squared distance on consumption+duration vs CustomerC medians; "
            f"best={best}, distance={scores[best]:.2f}"
        )
        conn.execute(
            """
            INSERT INTO inferred_fixture_events (event_id, inferred_fixture, confidence, reason)
            VALUES (?,?,?,?)
            """,
            (eid, best.lower(), confidence, reason),
        )
    conn.commit()


def build_anomalies(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM anomaly_candidates")
    baselines = conn.execute(
        """
        SELECT customer_profile, device_id, p99_consumption, p95_duration, median_consumption
        FROM device_baselines
        """
    ).fetchall()
    bl_map = {(r[0], r[1]): (r[2], r[3], r[4]) for r in baselines}

    rows = conn.execute(
        """
        SELECT e.event_id, e.customer_profile, e.device_id, e.consumption_raw,
               e.duration_seconds, c.is_night
        FROM trusted_events e
        JOIN calendar_context c ON c.event_id = e.event_id
        """
    ).fetchall()

    candidates = []
    for eid, prof, dev, cons, dur, is_night in rows:
        key = (prof, dev)
        if key not in bl_map:
            continue
        p99_c, p95_d, med_c = bl_map[key]
        score = 0.0
        reasons = []
        if p99_c and cons > p99_c:
            score += 40
            reasons.append("consumption_gt_p99")
        if p95_d and dur is not None and dur > p95_d:
            score += 30
            reasons.append("duration_gt_p95")
        if is_night and med_c and cons > 3 * med_c:
            score += 20
            reasons.append("night_high_vs_median")
        if score >= 40:
            candidates.append(
                (
                    eid,
                    prof,
                    dev,
                    "usage_spike_or_long_flow",
                    min(100.0, score),
                    json.dumps({"reasons": reasons, "consumption": cons, "duration": dur}),
                    p99_c,
                    "Event exceeds typical baseline for this device; investigate sensor or usage.",
                    "Inspect fixture or sensor; verify no stuck valve or leak.",
                )
            )

    candidates.sort(key=lambda x: -x[4])
    for row in candidates[:800]:
        conn.execute(
            """
            INSERT INTO anomaly_candidates (
              event_id, customer_profile, device_id, anomaly_type, severity_score,
              evidence_json, baseline_reference, explanation, recommended_action
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            row,
        )
    conn.commit()


def build_gym_inference(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM gym_device_inference")
    rows = conn.execute(
        """
        SELECT device_id, event_date, SUM(consumption_raw)
        FROM trusted_events
        WHERE customer_profile='gym'
        GROUP BY device_id, event_date
        """
    ).fetchall()
    date_device: dict[tuple[str, str], float] = {}
    devices: set[str] = set()
    all_dates: set[str] = set()
    for dev, ed, s in rows:
        date_device[(dev, ed)] = float(s)
        devices.add(dev)
        all_dates.add(ed)
    devices_list = sorted(devices)
    dates_list = sorted(all_dates)
    vectors = {
        d: [date_device.get((d, day), 0.0) for day in dates_list] for d in devices_list
    }

    pairs: list[tuple[float, str, str]] = []
    for i, a in enumerate(devices_list):
        for b in devices_list[i + 1 :]:
            r = pearson(vectors[a], vectors[b])
            pairs.append((r, a, b))
    pairs.sort(reverse=True, key=lambda x: x[0])

    used: set[str] = set()
    group_id = 0
    for r, a, b in pairs:
        if a in used or b in used:
            continue
        if r < 0.1:
            break
        used.add(a)
        used.add(b)
        summary = f"Pearson r={r:.3f} on aligned daily consumption totals"
        conn.execute(
            """
            INSERT INTO gym_device_inference (group_id, device_id, pair_confidence, evidence_summary)
            VALUES (?,?,?,?)
            """,
            (group_id, a, r, summary),
        )
        conn.execute(
            """
            INSERT INTO gym_device_inference (group_id, device_id, pair_confidence, evidence_summary)
            VALUES (?,?,?,?)
            """,
            (group_id, b, r, summary),
        )
        group_id += 1

    conn.commit()


def seed_external_context(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM holiday_context")
    fixed = [
        ("2024-01-01", "New Year's Day"),
        ("2024-03-20", "Independence Day"),
        ("2024-05-01", "Labour Day"),
        ("2024-07-25", "Republic Day"),
        ("2025-01-01", "New Year's Day"),
        ("2025-03-20", "Independence Day"),
        ("2025-05-01", "Labour Day"),
        ("2025-07-25", "Republic Day"),
        ("2026-01-01", "New Year's Day"),
        ("2026-03-20", "Independence Day"),
        ("2026-05-01", "Labour Day"),
        ("2026-07-25", "Republic Day"),
    ]
    conn.executemany(
        "INSERT INTO holiday_context (holiday_date, holiday_name) VALUES (?,?)",
        fixed,
    )
    conn.execute("DELETE FROM water_stress_context")
    conn.execute(
        """
        INSERT INTO water_stress_context (indicator_code, year, value, unit, source)
        VALUES ('water_stress_note', 2024, NULL, 'qualitative',
                'Placeholder row; replace with World Bank WDI / FAO AQUASTAT pull for Tunisia.')
        """
    )
    conn.execute("DELETE FROM external_fixture_benchmarks")
    conn.execute(
        """
        INSERT INTO external_fixture_benchmarks (dataset_name, fixture_type, metric_name, metric_value, notes)
        VALUES ('WEUSEDTO (reference)', 'mixed', 'benchmark_placeholder', NULL,
                'Optional external benchmark; cite dataset license if used in reports.')
        """
    )
    conn.commit()


def fix_schema_view(conn: sqlite3.Connection) -> None:
    """schema.sql may define trusted_events before flags; ensure view matches final logic."""
    recreate_trusted_view(conn)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        load_raw(conn)
        insert_normalized_events(conn)
        apply_quality_flags(conn)
        fix_schema_view(conn)
        populate_calendar_context(conn)
        simplify_daily_profile_peak_hour(conn)
        build_device_baselines(conn)
        build_fixture_signatures(conn)
        mine_motifs(conn)
        infer_fixtures_ab(conn)
        build_anomalies(conn)
        build_gym_inference(conn)
        seed_external_context(conn)
        print(f"Built database: {DB_PATH}")
        stats = conn.execute(
            "SELECT COUNT(*) FROM consumption_events"
        ).fetchone()[0]
        trusted = conn.execute("SELECT COUNT(*) FROM trusted_events").fetchone()[0]
        flags = conn.execute(
            "SELECT COUNT(DISTINCT event_id) FROM data_quality_flags WHERE severity='hard'"
        ).fetchone()[0]
        print(f"events={stats} trusted={trusted} events_with_hard_flags~={flags}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
