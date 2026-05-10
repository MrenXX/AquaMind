# AquaMind SQLite backend — normalization & enhancements

This branch adds a **deterministic SQLite data layer** for WaterSec telemetry: raw CSVs → normalized events → quality flags → **trusted** analytics → derived insight tables. The FastAPI agent should query SQLite for numbers (see hackathon / AquaMind plan), not sum CSVs in the LLM.

## Why normalization?

The four exports **do not share one schema**:

| Source | Column style | Extra fields |
|--------|----------------|--------------|
| Customer A/B/C | `data_consumption`, `data_time`, `data_period` | Categories; **C** has `Flush` / `Sink` / `Tap` |
| Gym | `data.consumption`, `data.time`, `data.period` | **No** category, client, or cabin labels |

**Normalization** maps every row into one table, `consumption_events`, so tools use stable column names (`timestamp_utc`, `consumption_raw`, `device_id`, …) and can join across sites. See [`NORMALIZED_MAPPING.md`](NORMALIZED_MAPPING.md).

## Why cleaning / trusted data?

Real IoT exports contain:

- Default-era timestamps (`1970`, `2000`)
- Future timestamps (e.g. gym **2036**)
- Overflow-like consumption (e.g. **4294967295**)
- Non-positive consumption
- Missing or zero **duration** (common in gym — consumption may still be valid)

We **flag** these in `data_quality_flags` and expose **`trusted_events`** for default KPIs so totals are not destroyed by one bad row. Zero-duration rows get a **soft** flag so gym usage can remain in trusted totals when consumption is real. See [`AGENT_DATA_RULES.md`](AGENT_DATA_RULES.md).

## What the ETL builds

Run from repo root:

```bash
python scripts/etl/build_database.py
python scripts/validate_db.py
```

Output: `data/aquamind.sqlite` (gitignored; build locally).

| Layer | Contents |
|-------|-----------|
| Raw tables | Original CSV columns preserved for audit |
| `consumption_events` | Unified event model |
| `data_quality_flags` | Per-issue codes and severity |
| `trusted_events` | View excluding hard failures |
| `calendar_context` | Hour, weekday, season, night, … |
| `daily_consumption_profile` | Daily rollups |
| `device_baselines` | Per-device medians / p95 / p99 |
| `motif_patterns` | Customer C sequences (e.g. Flush→Sink) |
| `fixture_signatures` | Reference stats by Flush/Sink/Tap |
| `inferred_fixture_events` | Weak labels for Customer A/B vs C signatures |
| `anomaly_candidates` | Rule-based candidates vs baselines |
| `gym_device_inference` | Correlation-based device pairs (hypothesis, not ground truth) |

Schema DDL: [`scripts/etl/schema.sql`](../scripts/etl/schema.sql). Pipeline: [`scripts/etl/build_database.py`](../scripts/etl/build_database.py).

## Enhancement data (optional / external)

Not part of the four CSVs, but supported for **demo storytelling** and correlation:

| Source | Table / script | Notes |
|--------|----------------|------|
| Tunisia fixed-date holidays | `holiday_context` | Seeded in ETL; Islamic movable holidays need manual refresh |
| Water stress placeholder | `water_stress_context` | Replace with World Bank / FAO if needed |
| Open-Meteo archive API | `scripts/fetch_open_meteo.py` → `climate_context` | Optional; requires network; join by date for heatwave-style analysis |
| External fixture benchmarks | `external_fixture_benchmarks` | Placeholder row; cite dataset license if used |

**Important:** Consumption **units** stay `consumption_raw` until WaterSec confirms mL, L, or pulses ([`DATA_INVENTORY.md`](DATA_INVENTORY.md)).

## Further reading

- [`DATA_INVENTORY.md`](DATA_INVENTORY.md) — row counts, ranges, known issues  
- [`BEGINNER_DATA_GUIDE.md`](BEGINNER_DATA_GUIDE.md) — full walkthrough  
- [`PITCH_DATA_RESUME.md`](PITCH_DATA_RESUME.md) — pitch cheat sheet  
