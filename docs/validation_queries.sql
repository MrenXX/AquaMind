# Validation SQL (AquaMind)

Run after `python scripts/etl/build_database.py` (or use `python scripts/validate_db.py`).

```sql
-- Row counts
SELECT 'consumption_events' AS t, COUNT(*) AS n FROM consumption_events
UNION ALL SELECT 'trusted_events', COUNT(*) FROM trusted_events
UNION ALL SELECT 'data_quality_flags', COUNT(*) FROM data_quality_flags;

-- Hard quality flags
SELECT flag_code, COUNT(*) AS n
FROM data_quality_flags
WHERE severity = 'hard'
GROUP BY flag_code
ORDER BY n DESC;

-- Motifs
SELECT motif_name, pattern_count, median_delay_seconds
FROM motif_patterns
ORDER BY pattern_count DESC;

-- Top daily gym consumption (example)
SELECT profile_date, device_id, total_consumption, event_count
FROM daily_consumption_profile
WHERE customer_profile = 'gym'
ORDER BY total_consumption DESC
LIMIT 10;

-- Anomaly sample
SELECT anomaly_type, COUNT(*) FROM anomaly_candidates GROUP BY anomaly_type;

-- Gym inferred pairs
SELECT group_id, device_id, pair_confidence
FROM gym_device_inference
ORDER BY group_id, device_id;
```
