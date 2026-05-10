import { useState } from 'react'
import { isBareIntentMetadataJson } from '../intentMeta.js'
import { PanelFullscreen } from './PanelFullscreen.jsx'
import { IconExpand } from './Icons.jsx'

/**
 * @param {{ stdout: string }} props
 */
function tryParseToolResponse(stdout) {
  const t = (stdout ?? '').trim()
  if (!t.startsWith('{')) return null
  try {
    const o = JSON.parse(t)
    if (o == null || typeof o !== 'object') return null
    const hasSummary = typeof o.answer_summary === 'string'
    const hasRows = Array.isArray(o.evidence_rows)
    if (!hasSummary && !hasRows) return null
    return o
  } catch {
    return null
  }
}

/**
 * @param {{ rows: Record<string, unknown>[] }} props
 */
function EvidenceTable({ rows }) {
  if (!rows || rows.length === 0) return null
  const keys = Object.keys(rows[0] ?? {})
  if (keys.length === 0) return null
  return (
    <div className="ws-sqlite-table-wrap">
      <table className="ws-sqlite-table">
        <thead>
          <tr>
            {keys.map((k) => (
              <th key={k}>{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {keys.map((k) => (
                <td key={k}>{String(row[k] ?? '')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * @param {{
 *   result: {
 *     sandbox_id: string,
 *     exit_code: number,
 *     stdout: string,
 *     chart_artifacts: { type: string, title: string }[],
 *   },
 *   className?: string,
 * }} props
 */
function SandboxResultInner({ result, className = '' }) {
  const ok = Number(result.exit_code) === 0
  const sid = result.sandbox_id ?? ''
  const isConversational = sid === 'intent:conversational'
  const isSqlite = sid === 'sqlite:local'
  const tool = isSqlite ? tryParseToolResponse(result.stdout ?? '') : null

  const wrapCls = className ? ` ${className}` : ''

  if (isConversational) {
    return (
      <div className={`ws-sandbox ws-sandbox--conversational${wrapCls}`}>
        <div className="ws-sandbox__meta">
          <span className="ws-sandbox__chip">Quick reply</span>
          <span
            className={`ws-exit-pill ${ok ? 'ws-exit-pill--ok' : 'ws-exit-pill--bad'}`}
          >
            {ok ? 'Finished successfully' : 'Did not finish as expected'}
          </span>
        </div>
        <p className="ws-sandbox__lead">
          No sandbox was used for this message. Your answer is in the chat.
        </p>
        {result.stdout?.trim() && !isBareIntentMetadataJson(result.stdout) ? (
          <div className="ws-sandbox__note">
            <p className="ws-sandbox__note-title">Server output</p>
            <pre className="ws-sandbox__stdout ws-sandbox__stdout--tight">
              {result.stdout}
            </pre>
          </div>
        ) : null}
      </div>
    )
  }

  if (isSqlite && tool) {
    return (
      <div className={`ws-sandbox ws-sandbox--sqlite${wrapCls}`}>
        <div className="ws-sandbox__meta">
          <span className="ws-sandbox__chip">Local data</span>
          <span
            className={`ws-exit-pill ${ok ? 'ws-exit-pill--ok' : 'ws-exit-pill--bad'}`}
          >
            {ok ? 'Finished successfully' : 'Did not finish as expected'}
          </span>
        </div>
        {tool.answer_summary ? (
          <div className="ws-sqlite-summary">
            <p className="ws-sqlite-summary__label">Summary</p>
            <p className="ws-sqlite-summary__text">{tool.answer_summary}</p>
          </div>
        ) : null}
        {tool.confidence_notes ? (
          <div className="ws-sqlite-notes">
            <p className="ws-sqlite-notes__label">Notes</p>
            <p className="ws-sqlite-notes__text">{tool.confidence_notes}</p>
          </div>
        ) : null}
        <EvidenceTable rows={Array.isArray(tool.evidence_rows) ? tool.evidence_rows : []} />
        {!tool.answer_summary &&
        !(Array.isArray(tool.evidence_rows) && tool.evidence_rows.length) ? (
          <pre className="ws-sandbox__stdout">{result.stdout ?? ''}</pre>
        ) : null}
      </div>
    )
  }

  return (
    <div className={`ws-sandbox${wrapCls}`}>
      <div className="ws-sandbox__meta">
        <code className="ws-sandbox__id">{result.sandbox_id}</code>
        <span className={`ws-exit-pill ${ok ? 'ws-exit-pill--ok' : 'ws-exit-pill--bad'}`}>
          {ok ? 'Finished successfully' : 'Did not finish as expected'}
        </span>
      </div>
      <pre className="ws-sandbox__stdout">{result.stdout ?? ''}</pre>
      {result.chart_artifacts && result.chart_artifacts.length > 0 ? (
        <div className="ws-chip-row">
          {result.chart_artifacts.map((a, i) => (
            <span key={`${a.type}-${a.title}-${i}`} className="ws-art-chip">
              [{a.type}] {a.title}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}

/**
 * @param {{
 *   result: null | {
 *     sandbox_id: string,
 *     exit_code: number,
 *     stdout: string,
 *     chart_artifacts: { type: string, title: string }[],
 *   },
 * }} props
 */
export function SandboxResult({ result }) {
  const [fullscreen, setFullscreen] = useState(false)
  const has = result != null
  const canExpand = Boolean(has)

  return (
    <>
      <section className="ws-panel ws-panel--hero">
        <header className="ws-panel__head ws-panel__head--row">
          <h2 className="ws-panel__title">Run output</h2>
          <button
            type="button"
            className="ws-icon-btn ws-icon-btn--ghost"
            disabled={!canExpand}
            title="Expand run output"
            aria-label="Expand run output full screen"
            onClick={() => canExpand && setFullscreen(true)}
          >
            <IconExpand />
          </button>
        </header>
        <div className="ws-panel__body">
          {!has ? (
            <div className="ws-empty">
              <span className="ws-empty__icon" aria-hidden>
                ▤
              </span>
              <p className="ws-empty__text">Results from the run will show here.</p>
            </div>
          ) : (
            <SandboxResultInner result={result} />
          )}
        </div>
      </section>

      <PanelFullscreen
        open={fullscreen && canExpand && result != null}
        onClose={() => setFullscreen(false)}
        title="Run output"
      >
        <div className="ws-fs-panel-scroll">{result ? <SandboxResultInner result={result} /> : null}</div>
      </PanelFullscreen>
    </>
  )
}
