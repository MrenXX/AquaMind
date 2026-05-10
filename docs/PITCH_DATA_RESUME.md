# Pitch cheat sheet — data problems, cleaning, and why it matters

Use this to rehearse **what was wrong with the raw data**, **what normalization/cleaning did**, and **why**, in under two minutes. Longer detail lives in [`BEGINNER_DATA_GUIDE.md`](BEGINNER_DATA_GUIDE.md) and [`DATA_INVENTORY.md`](DATA_INVENTORY.md).

---

## 1. WaterSec in one sentence (context for judges)

**WaterSec** (Tunisia, founded [2021](https://www.linkedin.com/company/water-sec/)) positions itself as **smart water monitoring** — IoT sensors and analytics so buildings and operators can **see consumption, catch waste and anomalies, and act** instead of flying blind. Official site: [water-sec.com](https://www.water-sec.com/). That matches our hackathon story: **turn telemetry into decisions** (aligned with the AquaMind demo thesis: WhatsApp + verified SQLite analytics, not raw CSV chat).

*Note: `watersec_hackathon_latest.pdf` was not in this repo when this doc was written; scoring hooks below follow the in-repo AquaMind demo plan ([`aquamind-demo_846f602b.plan.md`](../aquamind-demo_846f602b.plan.md)).*

---

## 2. High-level resume — what the four files are

| CSV | Role | Rich metadata? |
|-----|------|----------------|
| **Customer A** | Offices, 4 devices | Category only; **no** Flush/Sink/Tap |
| **Customer B** | Sanitary block, 1 device | Same; good for **night/weekend** stories |
| **Customer C** | Residential bathroom, 7 devices | **Has** `Flush` / `Sink` / `Tap` → **motifs & signatures** |
| **Gym** | 8 devices | **Minimal columns** — **no** cabin, hot/cold, or client ID in file |

**Takeaway for the pitch:** We have **one labeled residential dataset** (Customer C), **two aggregate site datasets** (A/B), and **one gym dataset** that needs cautious inference.

---

## 3. Problems we found in the data (honest list)

These are the issues called out in [`DATA_INVENTORY.md`](DATA_INVENTORY.md) and reflected in the pipeline:

| Problem | Why it hurts | Example / signal |
|--------|----------------|------------------|
| **Inconsistent CSV schemas** | Same concept, different column names → easy to load wrong fields | Customer files use `data_time`; gym uses `data.time` |
| **Bad timestamps** | Totals and trends become nonsense | **1970 / 2000** default-era dates; gym has **2036** future dates |
| **Overflow / extreme consumption** | One row can **inflate totals by billions** | Customer A includes **`4294967295`**-style values |
| **Non-positive consumption** | Invalid physics | Zeros or negatives in some rows |
| **Missing or zero duration** | Flow rate undefined; gym often has **period = 0** | Still keep consumption for totals; flag duration softly |
| **Mixed certainty** | Risk of **overclaiming** | Gym has **no** cabin map in data — inference is **hypothesis + confidence** |

**Sound bite:** *“Raw IoT exports are messy: clock faults, overflow spikes, and mixed schemas. We don’t hide that — we **flag it**, **exclude hard failures from trusted metrics**, and **keep evidence** for the agent to explain.”*

---

## 4. What “normalization” means here (and why it’s logical)

**Goal:** One row shape for every event so the backend and agent **always query the same columns**.

**What we did:**

1. **Preserve originals** in raw SQLite tables → audit trail for judges.
2. **Map everything into `consumption_events`** — same fields: device, time, consumption, duration, categories, profile (`customerA` … `gym`).
3. **Derive `flow_rate_raw`** only when duration &gt; 0 (otherwise leave null — logical).
4. **Do not invent labels** — gym stays without fixture/cabin labels; Customer C keeps real Flush/Sink/Tap.

**Why:** Matches the global AquaMind plan — **SQLite is the source of truth for numbers**; the LLM should call tools, not sum CSVs in its head.

---

## 5. What “cleaning” means here (trusted vs raw)

**Not** “delete bad data and pretend it never existed.” **Instead:**

- **`data_quality_flags`** — each issue has a **code**, **severity**, and **reason**.
- **`trusted_events`** — analytics default surface: **no hard failures** (bad time, impossible consumption, absurd duration).
- **Soft flags** — e.g. **zero duration**: common in gym data; we **still allow** those rows in trusted totals so we don’t wipe real shower usage; we **don’t** pretend flow-per-second is reliable there.

**Sound bite:** *“Cleaning here means **transparent rules**: what we trust for KPIs vs what we keep only for investigation.”*

---

## 6. Derived insights that matter for the demo (only what’s useful)

Aligned with **innovation scoring** (motifs, anomalies, calendar, optional climate) from the AquaMind plan:

| Deliverable | Use in pitch |
|-------------|----------------|
| **`motif_patterns` (Customer C)** | “We mine **Flush→Sink** sequences — hygiene / behavior story, not just liters.” |
| **`fixture_signatures` + `inferred_fixture_events` (A/B)** | “Aggregate sites get **weak** flush/sink/tap guesses from labeled residential reference — always **confidence**, never certainty.” |
| **`anomaly_candidates`** | “Ranked **inspect / leak / sensor fault** style alerts with **device baselines**, not global thresholds.” |
| **`gym_device_inference`** | “**Possible** cabin pairs from correlation — we say **pairs**, not ‘cabin 3 hot water’ without a mapping file.” |
| **`calendar_context`** | “Office vs gym vs night usage — schedule-aware stories.” |
| **`climate_context` + holidays** (optional) | “Heatwave / holiday **correlation** — **association**, not causation; fill via Open-Meteo when ready.” |

**Do not oversell:** Confirm **consumption units** with WaterSec before saying “liters” in customer-facing text ([`DATA_INVENTORY.md`](DATA_INVENTORY.md)).

---

## 7. Thirty-second pitch script (data portion)

> “We ingested four WaterSec telemetry exports — offices, sanitary block, labeled residential bathrooms, and a minimal gym file. The raw data had schema mismatches, default and future timestamps, and overflow-like readings that would destroy totals if unchecked. We normalized everything into one SQLite event model, flagged every bad row with reasons, and exposed **trusted** metrics separately. On top of that we derived **behavior motifs** from labeled residential data, **anomaly candidates** per device, and **cautious** gym grouping — so AquaMind answers from **verified SQL**, not hallucinated spreadsheet math. That’s how we support WaterSec’s mission: **measurable, actionable water intelligence.**”

---

## 8. Q&A you might get

- **“Did you throw away data?”** → No — raw tables remain; we **exclude** only from **trusted** aggregates where rules say so.
- **“How do you know gym cabins?”** → We don’t from CSV alone — we output **inferred groups + confidence**; ground truth needs WaterSec’s device map.
- **“What unit is consumption?”** → Stored as in telemetry; **confirm with WaterSec** before claiming liters/mL.

---

*Links: [WaterSec website](https://www.water-sec.com/) · [WaterSec LinkedIn](https://www.linkedin.com/company/water-sec/) · [Facebook page](https://www.facebook.com/watersec216/) (social presence; product detail prefers official site).*
