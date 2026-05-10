# Normalized event mapping

Raw rows from four tables load into `consumption_events` as follows.

| Source raw table | `customer_profile` | `site_type` | `main_category` | `sub_category` |
|------------------|-------------------|-------------|-----------------|----------------|
| `raw_customer_a_consumption` | `customerA` | `office` | CSV `main_category_name` or `Offices` | null |
| `raw_customer_b_consumption` | `customerB` | `sanitary_block` | CSV or `Bloc sanitaire` | null |
| `raw_customer_c_consumption` | `customerC` | `residential_bathroom` | CSV or `Bathroom` | `Flush` / `Sink` / `Tap` |
| `raw_gym_consumption` | `gym` | `gym` | `''` | `''` |

**Columns:**

- `timestamp_utc` — ISO 8601 UTC (`Z`).
- `event_date` — calendar date from timestamp (fallback `1970-01-01` if unparseable).
- `consumption_raw` — float from CSV.
- `duration_seconds` — float from `data_period` / `data.period` (may be null or zero).
- `flow_rate_raw` — `consumption_raw / duration_seconds` only when duration &gt; 0.
- `water_type` — CSV `tag` for customer files; null for gym.
- `sensor_type` — CSV `type` (`ws`) where present.

Implementation: [`scripts/etl/build_database.py`](../scripts/etl/build_database.py) (`insert_normalized_events`).
