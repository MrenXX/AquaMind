# Raw SQLite Import Tables

Raw tables preserve CSV columns before normalization. They are populated by [`scripts/etl/build_database.py`](../scripts/etl/build_database.py).

| Table | Source CSV | Purpose |
|-------|------------|---------|
| `raw_customer_a_consumption` | `customerA_consumption.csv` | Offices telemetry |
| `raw_customer_b_consumption` | `customerB_consumption.csv` | Sanitary block |
| `raw_customer_c_consumption` | `customerC_consumption.csv` | Residential bathroom + fixture labels |
| `raw_gym_consumption` | `gym_consumption_data.csv` | Gym (dot-style column names mapped on load) |

Each table includes `source_file` and `imported_at` for traceability. The ETL then builds `consumption_events` and all derived tables.

See also [DATA_INVENTORY.md](DATA_INVENTORY.md).
