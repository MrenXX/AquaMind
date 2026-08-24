#  AquaMind Data Work

This guide explains, in simple terms, what was built for the AquaMind data task, what the input data means, what the SQLite output contains, and what can still be improved.

## 1. Your Data Role

Your data task is to turn four raw WaterSec CSV files into one clean SQLite database.

The raw CSV files are not ready for the AI agent to use directly because:

- The files do not all have the same columns.
- Some timestamps are wrong, like `1970` or future dates.
- Some consumption values are impossible or suspicious.
- Some files have rich labels, while others have almost no labels.
- Raw totals can become wrong if bad sensor rows are included.

So the data pipeline does this:

```text
Raw CSV files
  -> raw SQLite tables
  -> normalized consumption_events table
  -> data quality flags
  -> trusted_events view
  -> derived insight tables
```

The final data product is:

```text
data/aquamind.sqlite
```

That SQLite file is what the backend, dashboard, and AI agent can query.

## 2. Input Files

There are four input CSV files.

### 2.1 `customerA_consumption.csv`

This is office-style water consumption data.

It contains:

- `device`: the sensor ID
- `data_consumption`: raw water consumption value
- `data_time`: timestamp
- `data_period`: event duration or period
- `tag`: water type, usually `cold`
- `main_category_name`: `Offices`
- `type`: sensor type
- `client_id`: customer/client identifier

Main use:

- Office water analytics
- Device comparison
- Detecting bad sensor values
- Showing why data quality matters

Important issue:

- This file contains a very large overflow-like value, `4294967295`.
- If that row is used in raw totals, the result becomes wrong.
- That is why quality flags and trusted views are necessary.

### 2.2 `customerB_consumption.csv`

This is sanitary-block water data.

It contains:

- One main device
- Cold water usage
- Category `Bloc sanitaire`
- Timestamps, consumption, and duration

Main use:

- Sanitary-block analytics
- Night and weekend usage analysis
- Possible leak or out-of-hours usage stories

Important note:

- It does not have fixture labels like `Sink`, `Flush`, or `Tap`.
- Any fixture type for this dataset must be treated as an estimate, not truth.

### 2.3 `customerC_consumption.csv`

This is the most useful dataset for behavior analysis.

It contains:

- Bathroom water usage
- Real fixture labels in `sub_category_name`

The fixture labels are:

- `Flush`
- `Sink`
- `Tap`

Main use:

- Learning bathroom behavior
- Finding sequences like `Flush -> Sink`
- Building fixture signatures
- Helping estimate fixture type in unlabeled data

Why this file is important:

- It is labeled.
- Labeled data is more valuable because we know what each event represents.
- CustomerC is the best dataset for innovation and behavior motifs.

### 2.4 `gym_consumption_data.csv`

This is gym water data.

It contains only:

- `device`
- `data.consumption`
- `data.time`
- `data.period`

It does not contain:

- Water type
- Category
- Shower cabin number
- Hot or cold water label
- Client ID

Main use:

- Gym usage analytics
- Device comparison
- Possible shower device grouping

Important warning:

- We cannot honestly say which device is a specific shower cabin unless WaterSec gives a device mapping.
- We can only infer possible groups with a confidence score.

## 3. What Cursor Built

Cursor built a SQLite ETL pipeline.

ETL means:

```text
Extract -> Transform -> Load
```

In this project:

- Extract means reading the CSV files.
- Transform means cleaning and standardizing the data.
- Load means inserting the data into SQLite tables.

Main implementation files:

- `scripts/etl/schema.sql`
- `scripts/etl/build_database.py`

To build the database:

```bash
python scripts/etl/build_database.py
```

To validate the database:

```bash
python scripts/validate_db.py
```

The generated database is:

```text
data/aquamind.sqlite
```

## 4. Database Layers

The SQLite database is organized in layers.

Each layer has a purpose.

### 4.1 Raw Tables

Raw tables preserve the original CSV data.

Tables:

- `raw_customer_a_consumption`
- `raw_customer_b_consumption`
- `raw_customer_c_consumption`
- `raw_gym_consumption`

Why raw tables matter:

- They keep the original data.
- They make the work traceable.
- If a transformed value looks wrong, you can go back to the original row.
- This helps explain the pipeline to judges.

Think of raw tables as the safe backup copy inside SQLite.

### 4.2 `consumption_events`

This is the main normalized table.

Normalization means taking different file formats and converting them into one common structure.

Why it was needed:

- Customer files use columns like `data_consumption`, `data_time`, and `data_period`.
- The gym file uses columns like `data.consumption`, `data.time`, and `data.period`.
- The backend should not need to understand four different CSV formats.

Important columns:

- `event_id`: unique event identifier
- `raw_table`: original raw table name
- `raw_row_id`: original row inside the raw table
- `source_file`: original CSV file
- `customer_profile`: `customerA`, `customerB`, `customerC`, or `gym`
- `site_type`: office, sanitary block, residential bathroom, or gym
- `device_id`: sensor/device identifier
- `timestamp_utc`: timestamp in UTC format
- `event_date`: date extracted from the timestamp
- `consumption_raw`: raw consumption value
- `duration_seconds`: event duration
- `flow_rate_raw`: consumption divided by duration, when possible
- `water_type`: usually `cold` for customer files, unknown for gym
- `main_category`: examples: `Offices`, `Bloc sanitaire`, `Bathroom`
- `sub_category`: examples: `Flush`, `Sink`, `Tap`
- `client_id`: available for customer files, missing for gym

Why this table matters:

- It lets the AI agent and backend query one clean table.
- It preserves links back to the original raw rows.
- It avoids repeated logic in every future analytics query.

### 4.3 `data_quality_flags`

This table records suspicious or bad rows.

Each flag says:

- Which event has a problem
- What the problem is
- Whether the problem is hard or soft
- Which field caused the problem
- Why it matters

Hard flags mean the row should be excluded from trusted analytics.

Examples of hard flags:

- `DEFAULT_TIMESTAMP`: timestamp is `1970` or `2000`
- `FUTURE_TIMESTAMP`: timestamp is too far in the future
- `NON_POSITIVE_CONSUMPTION`: consumption is zero or negative
- `OVERFLOW_EXTREME`: consumption is unrealistically huge
- `IMPOSSIBLE_DURATION`: duration is negative or extremely long

Soft flags mean the row is suspicious but can still be useful.

Example of a soft flag:

- `ZERO_OR_MISSING_DURATION`

Why zero duration is soft:

- Some gym rows may have duration `0`.
- The consumption value can still be useful for totals.
- But flow rate cannot be calculated safely.

Why this table matters:

- Bad rows can ruin totals and averages.
- This makes the data cleaning explainable.
- The agent can tell users why some rows were excluded.

### 4.4 `trusted_events`

`trusted_events` is a SQLite view.

A view is like a saved query.

`trusted_events` contains only events that do not have hard quality flags.

The agent and dashboard should use this view for normal calculations.

Why this matters:

- Raw data may contain sensor errors.
- Trusted data is safer for totals, averages, and comparisons.
- It protects the demo from incorrect numbers.

Simple rule:

```text
Use trusted_events for analytics.
Use raw tables only for tracing and debugging.
```

### 4.5 `calendar_context`

This table adds time information to each event.

It stores:

- Hour of day
- Day of week
- Weekend flag
- Month
- Season
- Daypart: morning, afternoon, evening, night
- Night flag

Why this matters:

- Water usage depends on time.
- Gym showers may peak in the evening.
- Office water usage may drop on weekends.
- Night usage can sometimes suggest leaks.

### 4.6 `daily_consumption_profile`

This table stores daily summaries.

It groups trusted events by:

- Date
- Customer profile
- Site type
- Device
- Main category
- Subcategory

It stores metrics like:

- Event count
- Total consumption
- Average event consumption
- Total duration
- Average flow rate
- Peak hour

Why this matters:

- Many demo questions are daily or date-range questions.
- This table makes those answers faster and more consistent.

Example question it helps answer:

```text
What is the average daily water consumption in the gym?
```

### 4.7 `device_baselines`

This table stores normal behavior for each device.

A baseline means:

```text
What is normal for this device?
```

It stores:

- Median consumption
- p95 consumption
- p99 consumption
- Median duration
- p95 duration
- Night event rate
- Weekend event rate
- Average daily consumption
- Active hour range

What p95 and p99 mean:

- p95 means 95 percent of values are below this value.
- p99 means 99 percent of values are below this value.
- Values above p99 are usually unusual.

Why this matters:

- A sink and a shower do not have the same normal usage.
- Each device should be compared with its own normal behavior.
- This reduces false anomaly alerts.

### 4.8 `motif_patterns`

A motif is a repeated behavior pattern.

For example:

```text
Flush -> Sink
```

This may represent a person flushing and then washing hands.

Implemented motifs:

- `Flush_to_Sink_120s`: flush followed by sink within 2 minutes
- `Flush_to_Sink_300s`: flush followed by sink within 5 minutes
- `Tap_to_Sink_120s`: tap followed by sink within 2 minutes
- `Repeated_Tap_60s_same_device`: repeated tap events within 60 seconds on the same device

Why this matters:

- It shows behavior intelligence.
- AquaMind becomes more than a chatbot over CSV files.
- The agent can explain patterns, not only totals.

### 4.9 `fixture_signatures`

This table summarizes typical behavior for each labeled fixture in CustomerC.

Fixture types:

- Flush
- Sink
- Tap

It stores:

- Number of samples
- Median consumption
- p25 and p75 consumption
- Median duration
- p25 and p75 duration
- Median flow rate

What p25 and p75 mean:

- p25 means 25 percent of values are below this value.
- p75 means 75 percent of values are below this value.
- Together they describe the normal middle range.

Why this matters:

- CustomerC has real labels.
- We can use CustomerC as a reference for unlabeled datasets.

### 4.10 `inferred_fixture_events`

This table estimates fixture type for unlabeled CustomerA and CustomerB events.

It estimates whether an event looks like:

- Flush
- Sink
- Tap

Important:

- These are not facts.
- They are educated guesses.
- The table includes a confidence score and reason.

Correct wording:

```text
This event is likely sink-like with medium confidence.
```

Incorrect wording:

```text
This event is definitely a sink.
```

Why this matters:

- It adds value to unlabeled data.
- It stays honest about uncertainty.

### 4.11 `anomaly_candidates`

This table stores suspicious operational events.

Current anomaly logic checks things like:

- Consumption greater than the device p99
- Duration greater than the device p95
- High night consumption compared with the device median

Each anomaly row stores:

- Event ID
- Customer profile
- Device ID
- Anomaly type
- Severity score
- Evidence
- Baseline reference
- Explanation
- Recommended action

Example recommended action:

```text
Inspect fixture or sensor; verify no stuck valve or leak.
```

Why this matters:

- The agent can produce practical recommendations.
- The dashboard can show anomaly cards.
- Gmail reports can include evidence.

### 4.12 `gym_device_inference`

The gym file has eight devices but no cabin labels.

This table tries to pair devices that behave similarly.

Current method:

- Compute daily consumption for each gym device.
- Compare devices using correlation.
- Pair devices with similar daily patterns.

Correlation means:

```text
Do two devices rise and fall together over time?
```

Important:

- This is only a hypothesis.
- It does not prove cabin identity.
- It should be shown with confidence.

### 4.13 Optional external context tables

The schema also includes:

- `climate_context`
- `holiday_context`
- `water_stress_context`
- `external_fixture_benchmarks`

These are for extra context.

Examples:

- Weather and heatwaves
- Tunisia holidays
- Water stress indicators
- External water fixture benchmarks

Cursor also added:

```text
scripts/fetch_open_meteo.py
```

This can fetch weather data from Open-Meteo into `climate_context`.

Current status:

- External context support exists.
- Weather is not automatically loaded unless the fetch script is run.
- Water stress and external benchmark rows are placeholders.

## 5. Is The Work Complete?

The core data foundation is complete.

The advanced analytics are usable but can be improved.

### Completed well

- CSV profiling
- Raw SQLite tables
- Normalized `consumption_events`
- Quality flag system
- `trusted_events` view
- Calendar context
- Daily consumption profiles
- Device baselines
- CustomerC motif mining
- Fixture signatures
- Basic fixture inference for CustomerA and CustomerB
- Basic anomaly candidate generation
- Basic gym device pairing
- Validation script and SQL queries
- Agent confidence rules
- Optional Open-Meteo weather loader

### Not fully complete yet

The plan is mostly implemented, but some advanced ideas are simplified.

#### Motifs can be enhanced

Currently implemented:

- Flush to Sink
- Tap to Sink
- Repeated Tap

Can add:

- Repeated Flush
- Flush without nearby Sink
- Long Sink usage
- Morning or evening routine patterns

#### Anomaly detection can be enhanced

Currently it uses simple thresholds.

Can add:

- Repeated burst detection
- Daily spike detection
- Leak-like continuous flow
- Separate sensor fault anomaly rows
- Water-impact based severity

#### Gym inference can be enhanced

Currently it uses daily correlation.

Can add:

- Events starting close together
- Hot/cold pair detection
- Multi-signal confidence score
- Clearer cabin group evidence

#### Weather enrichment can be enhanced

Currently the weather fetch script exists, but weather is optional.

Can add:

- Automatically load Open-Meteo data
- Join weather to daily profiles
- Create heatwave vs normal-day comparison table

#### Holiday context can be enhanced

Currently simple fixed-date holidays are seeded.

Can add:

- Full Tunisia holiday calendar
- Ramadan and Eid dates
- Holiday impact on office and gym usage

#### Units need confirmation

The database stores `consumption_raw`.

Before saying liters or milliliters, ask WaterSec to confirm the unit.

This is very important for the demo.

## 6. How To Explain This Project

You can say:

```text
I built the data foundation for AquaMind. The system transforms four inconsistent WaterSec CSV files into one SQLite database. It preserves raw data, normalizes all rows into one event table, flags bad sensor rows, creates a trusted analytics view, and generates derived insight tables for daily profiles, device baselines, behavior motifs, anomalies, fixture inference, and gym device grouping. This makes the AI agent reliable because it queries verified SQLite tables instead of calculating directly from messy CSVs.
```

## 7. What To Demo

Good demo points:

1. Show that the CSV files are inconsistent.
2. Show the raw tables preserve the original data.
3. Show `consumption_events` unifies all four files.
4. Show `data_quality_flags` catches bad rows.
5. Show `trusted_events` protects calculations.
6. Show `motif_patterns` finds behavior like `Flush -> Sink`.
7. Show `anomaly_candidates` gives evidence-backed alerts.
8. Show `gym_device_inference` gives cautious shower grouping.
9. Explain uncertainty honestly.

## 8. Beginner Glossary

### CSV

A text file that stores data in rows and columns.

### SQLite

A small database stored in one file.

### ETL

Extract, Transform, Load.

It means reading raw data, cleaning it, and loading it into a useful database.

### Raw table

A database table that keeps the original CSV data.

### Normalization

Making different datasets follow one common structure.

### Quality flag

A warning that a row may be wrong or suspicious.

### Hard flag

A serious problem. The row is excluded from trusted analytics.

### Soft flag

A warning. The row may still be useful.

### Trusted view

A cleaned database view used for normal calculations.

### Baseline

The normal behavior of a device.

### Anomaly

Something unusual compared with normal behavior.

### Motif

A repeated behavior pattern.

Example: Flush followed by Sink.

### Fixture

A water-using object, such as a sink, tap, flush, or shower.

### Inference

An educated guess based on data.

### Confidence score

A number showing how strong the guess is.

### Correlation

A way to measure whether two things move together.

## 9. Recommended Next Enhancements

If there is time, improve in this order:

1. Add missing motifs:
   - repeated flush
   - flush without sink
2. Improve anomaly detection:
   - repeated bursts
   - daily spikes
   - leak-like continuous flow
3. Improve gym inference:
   - pair devices by close event timestamps
4. Load real Open-Meteo weather data:
   - fill `climate_context`
   - compare heatwave days vs normal days
5. Add API or dashboard examples that query the SQLite tables

The most valuable next improvement for judging is:

```text
Better CustomerC motifs + better anomaly explanations.
```

These show domain intelligence, not just database cleaning.

