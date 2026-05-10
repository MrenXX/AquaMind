import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Chart,
  BarController,
  BarElement,
  CategoryScale,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Legend,
  Tooltip,
} from 'chart.js'
import { fetchAnalytics } from '../api.js'

Chart.register(
  BarController,
  BarElement,
  CategoryScale,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Legend,
  Tooltip,
)

/**
 * @typedef {{
 *   total_events: number,
 *   trusted_events: number,
 *   hard_flagged_events: number,
 *   profiles: string[],
 *   device_count: number,
 *   motif_top: { motif_name?: string, pattern_count?: number }[],
 *   anomaly_count: number,
 *   db_path: string,
 *   db_mtime_iso: string | null,
 * }} DashboardSummary
 */

function pctTrusted(summary) {
  if (!summary.total_events) return 0
  return Math.round((100 * summary.trusted_events) / summary.total_events)
}

/**
 * @param {unknown} row
 */
function rowNum(row, key) {
  if (row == null || typeof row !== 'object') return null
  const v = /** @type {Record<string, unknown>} */ (row)[key]
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

/**
 * @param {unknown[]} rows
 * @returns {{ labels: string[], values: number[] }}
 */
function profileChartData(rows) {
  const labels = []
  const values = []
  for (const r of rows) {
    if (r == null || typeof r !== 'object') continue
    const o = /** @type {Record<string, unknown>} */ (r)
    const key = o.group_key
    const total = rowNum(r, 'total_consumption')
    if (typeof key === 'string' && total != null) {
      labels.push(key)
      values.push(total)
    }
  }
  return { labels, values }
}

/**
 * @param {unknown[]} rows
 * @returns {{ labels: string[], values: number[] }}
 */
function dayChartData(rows) {
  const parsed = []
  for (const r of rows) {
    if (r == null || typeof r !== 'object') continue
    const o = /** @type {Record<string, unknown>} */ (r)
    const key = o.group_key
    const total = rowNum(r, 'total_consumption')
    if (typeof key === 'string' && total != null) {
      parsed.push({ key, total })
    }
  }
  parsed.sort((a, b) => a.key.localeCompare(b.key))
  return {
    labels: parsed.map((p) => p.key),
    values: parsed.map((p) => p.total),
  }
}

/**
 * @param {HTMLCanvasElement | null} canvas
 * @param {'bar' | 'line'} kind
 * @param {{ labels: string[], values: number[], label: string }} spec
 * @returns {Chart | null}
 */
function createTrendChart(canvas, kind, spec) {
  if (!canvas || spec.labels.length === 0) return null
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  const isLine = kind === 'line'
  return new Chart(ctx, {
    type: isLine ? 'line' : 'bar',
    data: {
      labels: spec.labels,
      datasets: [
        {
          label: spec.label,
          data: spec.values,
          borderColor: '#0d4cd3',
          backgroundColor: isLine ? 'rgba(13, 76, 211, 0.12)' : 'rgba(13, 76, 211, 0.55)',
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true },
      },
      scales: {
        x: {
          ticks: {
            color: '#475569',
            maxRotation: isLine ? 45 : 0,
          },
          grid: { color: 'rgba(148, 163, 184, 0.2)' },
        },
        y: {
          ticks: { color: '#475569' },
          grid: { color: 'rgba(148, 163, 184, 0.2)' },
        },
      },
    },
  })
}

export function WaterSecInsights() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(/** @type {string | null} */ (null))
  const [summary, setSummary] = useState(/** @type {DashboardSummary | null} */ (null))
  const [profileRows, setProfileRows] = useState(/** @type {unknown[]} */ ([]))
  const [dayRows, setDayRows] = useState(/** @type {unknown[]} */ ([]))
  const [motifRows, setMotifRows] = useState(/** @type {unknown[]} */ ([]))
  const [anomalyRows, setAnomalyRows] = useState(/** @type {unknown[]} */ ([]))

  const profileCanvasRef = useRef(/** @type {HTMLCanvasElement | null} */ (null))
  const dayCanvasRef = useRef(/** @type {HTMLCanvasElement | null} */ (null))
  const profileChartRef = useRef(/** @type {Chart | null} */ (null))
  const dayChartRef = useRef(/** @type {Chart | null} */ (null))

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const sum = /** @type {DashboardSummary} */ (await fetchAnalytics('/dashboard/summary'))
      setSummary(sum)

      const prof = /** @type {{ evidence_rows?: unknown[] }} */ (
        await fetchAnalytics('/tools/query_metrics', {
          use_trusted: true,
          group_by: 'profile',
          limit: 50,
        })
      )
      setProfileRows(Array.isArray(prof.evidence_rows) ? prof.evidence_rows : [])

      const days = /** @type {{ evidence_rows?: unknown[] }} */ (
        await fetchAnalytics('/tools/query_metrics', {
          use_trusted: true,
          group_by: 'day',
          limit: 90,
        })
      )
      setDayRows(Array.isArray(days.evidence_rows) ? days.evidence_rows : [])

      const motifs = /** @type {{ evidence_rows?: unknown[] }} */ (
        await fetchAnalytics('/tools/find_motifs', { limit: 20 })
      )
      setMotifRows(Array.isArray(motifs.evidence_rows) ? motifs.evidence_rows : [])

      const anomalies = /** @type {{ evidence_rows?: unknown[] }} */ (
        await fetchAnalytics('/tools/detect_anomalies', { limit: 15 })
      )
      setAnomalyRows(Array.isArray(anomalies.evidence_rows) ? anomalies.evidence_rows : [])
    } catch (e) {
      const msg =
        e instanceof Error
          ? e.message
          : 'Could not load analytics. Is the FastAPI backend running with data/aquamind.sqlite?'
      setError(msg)
      setSummary(null)
      setProfileRows([])
      setDayRows([])
      setMotifRows([])
      setAnomalyRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const t = window.setTimeout(() => {
      if (!cancelled) void loadAll()
    }, 0)
    return () => {
      cancelled = true
      window.clearTimeout(t)
    }
  }, [loadAll])

  const profileSpec = useMemo(() => profileChartData(profileRows), [profileRows])
  const daySpec = useMemo(() => dayChartData(dayRows), [dayRows])

  useEffect(() => {
    const canvas = profileCanvasRef.current
    if (profileChartRef.current) {
      profileChartRef.current.destroy()
      profileChartRef.current = null
    }
    if (!canvas || profileSpec.labels.length === 0) return
    profileChartRef.current = createTrendChart(canvas, 'bar', {
      ...profileSpec,
      label: 'Total consumption_raw (trusted)',
    })
    return () => {
      profileChartRef.current?.destroy()
      profileChartRef.current = null
    }
  }, [profileSpec])

  useEffect(() => {
    const canvas = dayCanvasRef.current
    if (dayChartRef.current) {
      dayChartRef.current.destroy()
      dayChartRef.current = null
    }
    if (!canvas || daySpec.labels.length === 0) return
    dayChartRef.current = createTrendChart(canvas, 'line', {
      ...daySpec,
      label: 'Daily total consumption_raw (trusted)',
    })
    return () => {
      dayChartRef.current?.destroy()
      dayChartRef.current = null
    }
  }, [daySpec])

  const trustedPct = summary ? pctTrusted(summary) : 0

  return (
    <div className="ws-insights">
      <header className="ws-insights__hero">
        <div>
          <p className="ws-insights__eyebrow">SQLite telemetry</p>
          <h1 className="ws-insights__title">WaterSec insights</h1>
          <p className="ws-insights__lede">
            Deterministic KPIs from <code className="ws-insights__code">trusted_events</code> and
            derived tables — same contracts the agent uses. Units are raw telemetry until WaterSec
            confirms liters vs pulses.
          </p>
        </div>
        <button
          type="button"
          className="ws-pill-btn ws-pill-btn--outline ws-insights__refresh"
          disabled={loading}
          onClick={() => void loadAll()}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>

      {error ? (
        <div className="ws-insights__alert" role="alert">
          <strong className="ws-insights__alert-title">Analytics unavailable</strong>
          <p className="ws-insights__alert-text">{error}</p>
          <p className="ws-insights__alert-hint">
            Build the DB: <code className="ws-insights__code">python scripts\etl\build_database.py</code>{' '}
            in WaterSec-OpenClaw, then start{' '}
            <code className="ws-insights__code">scripts\start-aquamind-backend.ps1</code>. Use{' '}
            <code className="ws-insights__code">VITE_CHAT_API=/api</code> so Vite proxies to the API.
          </p>
        </div>
      ) : null}

      {loading && !summary ? (
        <p className="ws-insights__loading">Loading dashboard…</p>
      ) : null}

      {summary ? (
        <>
          <section className="ws-insights__kpis" aria-label="Key metrics">
            <article className="ws-insights-kpi">
              <span className="ws-insights-kpi__label">Trusted coverage</span>
              <span className="ws-insights-kpi__value">{trustedPct}%</span>
              <span className="ws-insights-kpi__meta">
                {summary.trusted_events.toLocaleString()} / {summary.total_events.toLocaleString()}{' '}
                events
              </span>
            </article>
            <article className="ws-insights-kpi ws-insights-kpi--warn">
              <span className="ws-insights-kpi__label">Hard quality flags</span>
              <span className="ws-insights-kpi__value">
                {summary.hard_flagged_events.toLocaleString()}
              </span>
              <span className="ws-insights-kpi__meta">Excluded from trusted KPIs by default</span>
            </article>
            <article className="ws-insights-kpi">
              <span className="ws-insights-kpi__label">Devices</span>
              <span className="ws-insights-kpi__value">{summary.device_count.toLocaleString()}</span>
              <span className="ws-insights-kpi__meta">Distinct device_id</span>
            </article>
            <article className="ws-insights-kpi ws-insights-kpi--accent">
              <span className="ws-insights-kpi__label">Anomaly candidates</span>
              <span className="ws-insights-kpi__value">{summary.anomaly_count.toLocaleString()}</span>
              <span className="ws-insights-kpi__meta">Verify in the field before acting</span>
            </article>
          </section>

          <p className="ws-insights__dbmeta">
            DB mtime:{' '}
            {summary.db_mtime_iso ? (
              <time dateTime={summary.db_mtime_iso}>{summary.db_mtime_iso}</time>
            ) : (
              '—'
            )}
          </p>

          <div className="ws-insights__charts">
            <section className="ws-insights-chart-card">
              <h2 className="ws-insights-chart-card__title">By customer profile</h2>
              <p className="ws-insights-chart-card__hint">
                Compare gym, residential, and office-scale aggregates (consumption_raw sum).
              </p>
              <div className="ws-insights-chart-card__canvas">
                {profileSpec.labels.length > 0 ? (
                  <canvas ref={profileCanvasRef} className="ws-insights-canvas" />
                ) : (
                  <p className="ws-insights__empty">No profile groups returned.</p>
                )}
              </div>
            </section>
            <section className="ws-insights-chart-card">
              <h2 className="ws-insights-chart-card__title">Daily trend</h2>
              <p className="ws-insights-chart-card__hint">
                Days sorted chronologically for trend context (top rows from API re-ordered
                client-side).
              </p>
              <div className="ws-insights-chart-card__canvas">
                {daySpec.labels.length > 0 ? (
                  <canvas ref={dayCanvasRef} className="ws-insights-canvas" />
                ) : (
                  <p className="ws-insights__empty">No daily aggregates returned.</p>
                )}
              </div>
            </section>
          </div>

          <div className="ws-insights__split">
            <section className="ws-insights-panel">
              <h2 className="ws-insights-panel__title">Motif patterns (Customer C)</h2>
              <p className="ws-insights-panel__desc">
                Behavioral sequences such as flush→sink — cite as patterns, not proof of fixture
                labels on other profiles.
              </p>
              <ul className="ws-insights-motifs">
                {(summary.motif_top ?? []).map((m, i) => (
                  <li key={`${m.motif_name ?? i}-${i}`} className="ws-insights-motifs__item">
                    <span className="ws-insights-motifs__name">{m.motif_name ?? '—'}</span>
                    <span className="ws-insights-motifs__count">
                      {(m.pattern_count ?? 0).toLocaleString()} patterns
                    </span>
                  </li>
                ))}
              </ul>
              {motifRows.length > 0 ? (
                <details className="ws-insights-details">
                  <summary>Full motif rows</summary>
                  <pre className="ws-insights-pre">{JSON.stringify(motifRows, null, 2)}</pre>
                </details>
              ) : null}
            </section>

            <section className="ws-insights-panel ws-insights-panel--alert">
              <h2 className="ws-insights-panel__title">Anomaly queue</h2>
              <p className="ws-insights-panel__desc">
                Ranked candidates from device baselines; sensor faults and leaks remain possible —
                validate before dispatch.
              </p>
              <ul className="ws-insights-anomalies">
                {anomalyRows.slice(0, 8).map((row, i) => {
                  if (row == null || typeof row !== 'object') return null
                  const o = /** @type {Record<string, unknown>} */ (row)
                  const dev = typeof o.device_id === 'string' ? o.device_id : '—'
                  const typ = typeof o.anomaly_type === 'string' ? o.anomaly_type : '—'
                  const expl = typeof o.explanation === 'string' ? o.explanation : ''
                  const action =
                    typeof o.recommended_action === 'string' ? o.recommended_action : ''
                  return (
                    <li key={`${String(o.anomaly_id ?? i)}`} className="ws-insights-anomalies__item">
                      <div className="ws-insights-anomalies__head">
                        <span className="ws-insights-anomalies__device">{dev}</span>
                        <span className="ws-insights-anomalies__type">{typ}</span>
                      </div>
                      {expl ? <p className="ws-insights-anomalies__text">{expl}</p> : null}
                      {action ? (
                        <p className="ws-insights-anomalies__action">
                          <strong>Action:</strong> {action}
                        </p>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
              {anomalyRows.length === 0 ? (
                <p className="ws-insights__empty">No anomaly rows in this build.</p>
              ) : null}
            </section>
          </div>

          <footer className="ws-insights__footer">
            <p>
              Profiles in dataset:{' '}
              {(summary.profiles ?? []).length ? summary.profiles.join(', ') : '—'}
            </p>
          </footer>
        </>
      ) : null}
    </div>
  )
}
