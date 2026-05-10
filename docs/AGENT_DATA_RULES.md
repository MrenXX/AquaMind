# Agent Data Confidence Rules (AquaMind)

These rules align numeric answers with the SQLite data layer. The LLM must **not** invent totals; FastAPI tools should run SQL or deterministic Python on `data/aquamind.sqlite`.

## Safe claims

- **Exact aggregates** when computed from `trusted_events`, `daily_consumption_profile`, `device_baselines`, `motif_patterns`, or other derived tables produced by the ETL.
- **Quality caveats**: cite `data_quality_flags` when explaining exclusions (hard flags remove rows from `trusted_events`).
- **Motifs**: report counts and delays from `motif_patterns`; cite example `example_event_ids` as evidence IDs only.
- **Anomalies**: describe rows in `anomaly_candidates` as *candidates*; reference `severity_score`, `evidence_json`, and `recommended_action`.
- **Fixture inference** (`inferred_fixture_events`): always use language like *likely* / *estimated*; show `confidence` when available.

## Unsafe or restricted claims

- **Raw CSV totals** without mentioning rows excluded by quality flags.
- **Exact gym cabin or hot/cold labels** unless WaterSec provides a device mapping file.
- **Consumption units** (mL vs L vs pulses) unless confirmed by WaterSec.
- **Causality**: weather vs usage correlations are **associative**, not proof of cause.

## Heatwaves / climate

If `climate_context` is empty, say that enrichment is pending or run an approved fetch script; do not fabricate temperatures.

## Gmail / escalation

Incident narratives must align with `anomaly_candidates` evidence and device IDs from SQLite.

_Last updated: AquaMind data implementation._
