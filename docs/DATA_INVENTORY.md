# WaterSec CSV Data Inventory

This document satisfies the **inventory-inputs** milestone: documented inputs before ETL.

## Summary

| File | Separator | Rows | Devices | Client ID | Categories |
|------|-----------|------|---------|-----------|------------|
| `customerA_consumption.csv` | `;` | 42,446 | 4 | 28 | Offices |
| `customerB_consumption.csv` | `;` | 15,346 | 1 | 30 | Bloc sanitaire |
| `customerC_consumption.csv` | `;` | 74,013 | 7 | 18 | Bathroom (Flush / Sink / Tap) |
| `gym_consumption_data.csv` | `,` | 26,982 | 8 | — | (none in file) |

## Schema differences

### Customer A, B, C (semicolon-separated)

Columns:

- `device`
- `data_consumption`
- `data_time` (ISO 8601 with `Z`)
- `data_period` (numeric; treated as duration in seconds for analytics)
- `tag` (e.g. `cold`)
- `main_category_name`
- `type` (e.g. `ws`)
- `client_id`

Customer C adds:

- `sub_category_name`: `Flush`, `Sink`, or `Tap`

### Gym (comma-separated)

Columns (dot naming):

- `data.consumption`
- `data.time`
- `data.period`
- `device`

No `tag`, `main_category_name`, `sub_category_name`, or `client_id` in the file.

## Date ranges (UTC, from profiling)

| File | Min timestamp | Max timestamp |
|------|----------------|---------------|
| customerA | 1970-01-01 | 2025-11-22 |
| customerB | 1970-01-01 | 2026-05-09 |
| customerC | 1970-01-01 | 2025-11-24 |
| gym | 1970-01-01 | **2036-02-08** (future-dated rows present) |

## Consumption and period ranges (observed)

| File | Consumption min | Consumption max | Period min | Period max |
|------|-----------------|-----------------|------------|------------|
| customerA | 0 | **4,294,967,295** (overflow-like) | 1 | 77,685 |
| customerB | 100 | 11,132,519 | 1 | 54,492 |
| customerC | 80 | 4,580,539 | 1 | 50,950 |
| gym | **0** | 172,072 | **0** | 3,916 |

## Data-quality hints (counts from profiling)

Approximate flags to expect at load time:

| Issue | customerA | customerB | customerC | gym |
|-------|-------------|-----------|-----------|-----|
| Timestamp year 1970 or 2000 | 4 | 4 | 79 | 217 |
| Timestamp year ≥ 2030 | 0 | 0 | 0 | 132 |
| Non-positive consumption | 2 | 0 | 0 | 1 |
| Consumption ≥ 1,000,000 | 6 | 7 | 2 | 0 |

These counts are diagnostic; authoritative counts are in SQLite after `data_quality_flags` is populated.

## Roles of each dataset

- **Customer A:** Office / aggregated cold-water usage; strong candidate for overflow sensor faults; no fixture subcategories.
- **Customer B:** Single sanitary-block sensor; useful for night/weekend and leak-style stories.
- **Customer C:** Residential bathroom with labeled Flush/Sink/Tap; primary source for **motifs** and **fixture signatures**.
- **Gym:** Minimal schema; eight devices; suitable for **pairwise cabin inference** (labels not in file).

## Units

Consumption units are stored as in the CSV (`consumption_raw`). Confirm with WaterSec whether values are mL, L, or pulse counts before stating units in user-facing copy.

_Last updated: generated as part of AquaMind data enhancement implementation._
