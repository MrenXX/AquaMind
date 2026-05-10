-- AquaMind SQLite schema: raw imports, normalized events, quality, derived tables.
-- Execute via build_database.py (also creates views and indexes).

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Raw import tables (preserve CSV columns before normalization)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw_customer_a_consumption (
  raw_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
  device TEXT,
  data_consumption TEXT,
  data_time TEXT,
  data_period TEXT,
  tag TEXT,
  main_category_name TEXT,
  type TEXT,
  client_id TEXT,
  source_file TEXT NOT NULL,
  imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS raw_customer_b_consumption (
  raw_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
  device TEXT,
  data_consumption TEXT,
  data_time TEXT,
  data_period TEXT,
  tag TEXT,
  main_category_name TEXT,
  type TEXT,
  client_id TEXT,
  source_file TEXT NOT NULL,
  imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS raw_customer_c_consumption (
  raw_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
  device TEXT,
  data_consumption TEXT,
  data_time TEXT,
  data_period TEXT,
  tag TEXT,
  main_category_name TEXT,
  sub_category_name TEXT,
  type TEXT,
  client_id TEXT,
  source_file TEXT NOT NULL,
  imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS raw_gym_consumption (
  raw_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
  data_consumption TEXT,
  data_time TEXT,
  data_period TEXT,
  device TEXT,
  source_file TEXT NOT NULL,
  imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Normalized events
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS consumption_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_table TEXT NOT NULL,
  raw_row_id INTEGER NOT NULL,
  source_file TEXT NOT NULL,
  customer_profile TEXT NOT NULL,
  site_type TEXT NOT NULL,
  device_id TEXT NOT NULL,
  timestamp_utc TEXT NOT NULL,
  event_date TEXT NOT NULL,
  consumption_raw REAL NOT NULL,
  duration_seconds REAL,
  flow_rate_raw REAL,
  water_type TEXT,
  main_category TEXT,
  sub_category TEXT,
  client_id TEXT,
  sensor_type TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_profile ON consumption_events(customer_profile);
CREATE INDEX IF NOT EXISTS idx_events_device ON consumption_events(device_id);
CREATE INDEX IF NOT EXISTS idx_events_date ON consumption_events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_ts ON consumption_events(timestamp_utc);

-- ---------------------------------------------------------------------------
-- Data quality flags (hard = excluded from trusted_events by default)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS data_quality_flags (
  flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER NOT NULL REFERENCES consumption_events(event_id) ON DELETE CASCADE,
  flag_code TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('hard', 'soft')),
  reason TEXT,
  field_name TEXT,
  field_value TEXT
);

CREATE INDEX IF NOT EXISTS idx_flags_event ON data_quality_flags(event_id);
CREATE INDEX IF NOT EXISTS idx_flags_code ON data_quality_flags(flag_code);

-- Trusted analytics slice (view defined after flags populated)
CREATE VIEW IF NOT EXISTS trusted_events AS
SELECT e.*
FROM consumption_events e
WHERE e.event_id NOT IN (
  SELECT f.event_id FROM data_quality_flags f WHERE f.severity = 'hard'
);

-- ---------------------------------------------------------------------------
-- Calendar context (one row per event)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS calendar_context (
  event_id INTEGER PRIMARY KEY REFERENCES consumption_events(event_id) ON DELETE CASCADE,
  hour_of_day INTEGER NOT NULL,
  day_of_week INTEGER NOT NULL,
  is_weekend INTEGER NOT NULL,
  month INTEGER NOT NULL,
  season TEXT NOT NULL,
  daypart TEXT NOT NULL,
  is_night INTEGER NOT NULL
);

-- ---------------------------------------------------------------------------
-- Core analytics aggregates
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS daily_consumption_profile (
  profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_date TEXT NOT NULL,
  customer_profile TEXT NOT NULL,
  site_type TEXT NOT NULL,
  device_id TEXT NOT NULL,
  main_category TEXT NOT NULL DEFAULT '',
  sub_category TEXT NOT NULL DEFAULT '',
  event_count INTEGER NOT NULL,
  total_consumption REAL NOT NULL,
  avg_event_consumption REAL,
  total_duration_seconds REAL,
  avg_flow_rate REAL,
  peak_hour INTEGER,
  UNIQUE (
    profile_date,
    customer_profile,
    site_type,
    device_id,
    main_category,
    sub_category
  )
);

CREATE INDEX IF NOT EXISTS idx_daily_profile_date ON daily_consumption_profile(profile_date);

CREATE TABLE IF NOT EXISTS device_baselines (
  customer_profile TEXT NOT NULL,
  device_id TEXT NOT NULL,
  event_count INTEGER NOT NULL,
  median_consumption REAL,
  p95_consumption REAL,
  p99_consumption REAL,
  median_duration REAL,
  p95_duration REAL,
  night_event_rate REAL,
  weekend_event_rate REAL,
  avg_daily_consumption REAL,
  active_hour_start INTEGER,
  active_hour_end INTEGER,
  PRIMARY KEY (customer_profile, device_id)
);

-- ---------------------------------------------------------------------------
-- Behavior insights
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS motif_patterns (
  motif_id INTEGER PRIMARY KEY AUTOINCREMENT,
  motif_name TEXT NOT NULL UNIQUE,
  pattern_count INTEGER NOT NULL,
  median_delay_seconds REAL,
  example_event_ids TEXT,
  total_consumption_involved REAL,
  interpretation TEXT
);

CREATE TABLE IF NOT EXISTS fixture_signatures (
  fixture_type TEXT PRIMARY KEY,
  sample_count INTEGER NOT NULL,
  median_consumption REAL,
  p25_consumption REAL,
  p75_consumption REAL,
  median_duration REAL,
  p25_duration REAL,
  p75_duration REAL,
  median_flow_rate REAL
);

CREATE TABLE IF NOT EXISTS inferred_fixture_events (
  event_id INTEGER PRIMARY KEY REFERENCES consumption_events(event_id) ON DELETE CASCADE,
  inferred_fixture TEXT NOT NULL,
  confidence REAL NOT NULL,
  reason TEXT
);

-- ---------------------------------------------------------------------------
-- Anomalies & gym inference
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS anomaly_candidates (
  anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER REFERENCES consumption_events(event_id) ON DELETE SET NULL,
  customer_profile TEXT,
  device_id TEXT,
  anomaly_type TEXT NOT NULL,
  severity_score REAL,
  evidence_json TEXT,
  baseline_reference REAL,
  explanation TEXT,
  recommended_action TEXT
);

CREATE INDEX IF NOT EXISTS idx_anomaly_event ON anomaly_candidates(event_id);

CREATE TABLE IF NOT EXISTS gym_device_inference (
  inference_id INTEGER PRIMARY KEY AUTOINCREMENT,
  group_id INTEGER NOT NULL,
  device_id TEXT NOT NULL,
  pair_confidence REAL,
  evidence_summary TEXT,
  UNIQUE (group_id, device_id)
);

-- ---------------------------------------------------------------------------
-- Optional external context (may be empty; populated by seeds or fetch scripts)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS climate_context (
  context_date TEXT PRIMARY KEY,
  temp_max_c REAL,
  temp_min_c REAL,
  precip_mm REAL,
  heatwave_flag INTEGER NOT NULL DEFAULT 0,
  data_source TEXT
);

CREATE TABLE IF NOT EXISTS holiday_context (
  holiday_date TEXT PRIMARY KEY,
  holiday_name TEXT NOT NULL,
  country_code TEXT NOT NULL DEFAULT 'TN'
);

CREATE TABLE IF NOT EXISTS water_stress_context (
  indicator_code TEXT NOT NULL,
  year INTEGER NOT NULL,
  value REAL,
  unit TEXT,
  source TEXT,
  PRIMARY KEY (indicator_code, year)
);

CREATE TABLE IF NOT EXISTS external_fixture_benchmarks (
  benchmark_id INTEGER PRIMARY KEY AUTOINCREMENT,
  dataset_name TEXT NOT NULL,
  fixture_type TEXT,
  metric_name TEXT NOT NULL,
  metric_value REAL,
  notes TEXT
);
