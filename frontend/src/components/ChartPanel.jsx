import { useEffect, useMemo, useRef, useState } from 'react'
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
import { PanelFullscreen } from './PanelFullscreen.jsx'
import { IconExpand } from './Icons.jsx'

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

function artifactChartSpec(artifacts) {
  if (!artifacts || artifacts.length === 0) return null
  const first = artifacts[0]
  const labels = first.labels ?? first.categories ?? first.x
  const values =
    first.values ??
    first.data ??
    first.y ??
    (Array.isArray(first.series) ? first.series : null)
  if (
    Array.isArray(labels) &&
    labels.length > 0 &&
    Array.isArray(values) &&
    values.length > 0 &&
    values.every((n) => typeof n === 'number')
  ) {
    const kind =
      typeof first.type === 'string' && first.type.toLowerCase().includes('line')
        ? 'line'
        : 'bar'
    return { kind, labels, values, title: first.title }
  }
  return null
}

/**
 * @param {HTMLCanvasElement | null} canvas
 * @param {NonNullable<ReturnType<typeof artifactChartSpec>>} spec
 * @returns {Chart | null}
 */
function createChartInstance(canvas, spec) {
  if (!canvas) return null
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  const isLine = spec.kind === 'line'
  return new Chart(ctx, {
    type: isLine ? 'line' : 'bar',
    data: {
      labels: spec.labels,
      datasets: [
        {
          label: spec.title ?? 'Series',
          data: spec.values,
          borderColor: '#1A56FF',
          backgroundColor: isLine
            ? 'rgba(26, 86, 255, 0.2)'
            : 'rgba(26, 86, 255, 0.55)',
          tension: 0.25,
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
          ticks: { color: '#475569' },
          grid: { color: 'rgba(148, 163, 184, 0.25)' },
        },
        y: {
          ticks: { color: '#475569' },
          grid: { color: 'rgba(148, 163, 184, 0.25)' },
        },
      },
    },
  })
}

/**
 * @param {{
 *   pngBase64: string | null | undefined,
 *   chartArtifacts: { type: string, title: string, labels?: string[], values?: number[], data?: number[], series?: number[] }[] | null | undefined,
 * }} props
 */
export function ChartPanel({ pngBase64, chartArtifacts }) {
  const canvasRef = useRef(null)
  const fsCanvasRef = useRef(null)
  const chartRef = useRef(/** @type {Chart | null} */ (null))
  const fsChartRef = useRef(/** @type {Chart | null} */ (null))

  const spec = useMemo(() => artifactChartSpec(chartArtifacts ?? []), [chartArtifacts])

  const hasPng = Boolean(pngBase64 && pngBase64.length)
  const [fullscreenOpen, setFullscreenOpen] = useState(false)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || hasPng || !spec) {
      if (chartRef.current) {
        chartRef.current.destroy()
        chartRef.current = null
      }
      return
    }

    if (chartRef.current) {
      chartRef.current.destroy()
      chartRef.current = null
    }

    chartRef.current = createChartInstance(canvas, spec)

    return () => {
      chartRef.current?.destroy()
      chartRef.current = null
    }
  }, [hasPng, spec])

  useEffect(() => {
    if (!fullscreenOpen) {
      if (fsChartRef.current) {
        fsChartRef.current.destroy()
        fsChartRef.current = null
      }
      return
    }

    const canvas = fsCanvasRef.current
    if (!canvas || hasPng || !spec) {
      if (fsChartRef.current) {
        fsChartRef.current.destroy()
        fsChartRef.current = null
      }
      return
    }

    const t = window.setTimeout(() => {
      if (fsChartRef.current) {
        fsChartRef.current.destroy()
        fsChartRef.current = null
      }
      fsChartRef.current = createChartInstance(canvas, spec)
    }, 0)

    return () => {
      window.clearTimeout(t)
      fsChartRef.current?.destroy()
      fsChartRef.current = null
    }
  }, [fullscreenOpen, hasPng, spec])

  const downloadPng = () => {
    if (!pngBase64) return
    const a = document.createElement('a')
    a.href = `data:image/png;base64,${pngBase64}`
    a.download = 'aquamind-chart.png'
    a.click()
  }

  const hasArtifacts = Boolean(chartArtifacts && chartArtifacts.length > 0)
  const showMetaOnly =
    !hasPng && hasArtifacts && !spec && chartArtifacts && chartArtifacts.length > 0

  const empty = !hasPng && !hasArtifacts
  const canExpand = !empty

  const metaMessage = (
    <p className="ws-chart-meta-msg">
      We received chart titles but not a picture file. Turn on Expert view and ask for a saved chart
      image if you need support to troubleshoot.
    </p>
  )

  return (
    <>
      <section className="ws-panel ws-panel--hero">
        <header className="ws-panel__head ws-panel__head--row">
          <h2 className="ws-panel__title">Visualization</h2>
          <button
            type="button"
            className="ws-icon-btn ws-icon-btn--ghost"
            disabled={!canExpand}
            title="Expand visualization"
            aria-label="Expand visualization full screen"
            onClick={() => canExpand && setFullscreenOpen(true)}
          >
            <IconExpand />
          </button>
        </header>
        <div className="ws-panel__body">
          {empty ? (
            <div className="ws-empty">
              <span className="ws-empty__icon" aria-hidden>
                ▣
              </span>
              <p className="ws-empty__text">
                Charts and exported graphics from each run appear here.
              </p>
            </div>
          ) : null}
          {hasPng ? (
            <div className="ws-chart-out ws-chart-out--hero">
              <img
                src={`data:image/png;base64,${pngBase64}`}
                alt="Visualization from run"
                className="ws-chart-img"
              />
              <button
                type="button"
                className="ws-pill-btn ws-pill-btn--outline ws-chart-dl"
                onClick={downloadPng}
              >
                Download PNG
              </button>
            </div>
          ) : null}
          {showMetaOnly ? metaMessage : null}
          {!hasPng && spec ? (
            <div className="ws-chart-canvas-wrap ws-chart-canvas-wrap--hero">
              <canvas ref={canvasRef} className="ws-chart-canvas" />
            </div>
          ) : null}
        </div>
      </section>

      <PanelFullscreen
        open={fullscreenOpen && canExpand}
        onClose={() => setFullscreenOpen(false)}
        title="Visualization"
      >
        <div className="ws-fs-chart-stage">
          {hasPng ? (
            <div className="ws-chart-out ws-chart-out--fs">
              <img
                src={`data:image/png;base64,${pngBase64}`}
                alt="Visualization — expanded"
                className="ws-chart-img ws-chart-img--fs"
              />
              <button type="button" className="ws-pill-btn ws-pill-btn--outline" onClick={downloadPng}>
                Download PNG
              </button>
            </div>
          ) : null}
          {!hasPng && spec ? (
            <div className="ws-chart-canvas-wrap ws-chart-canvas-wrap--fs">
              <canvas ref={fsCanvasRef} className="ws-chart-canvas" />
            </div>
          ) : null}
          {showMetaOnly ? metaMessage : null}
        </div>
      </PanelFullscreen>
    </>
  )
}
