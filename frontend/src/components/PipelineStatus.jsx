function firstLineSnippet(text, maxLen = 96) {
  const line = (text ?? '').split('\n')[0].trim()
  if (line.length <= maxLen) return line
  return `${line.slice(0, maxLen - 1)}…`
}

function stepLabel(state) {
  if (state === 'active') return 'Active'
  if (state === 'retrying') return 'Retrying'
  if (state === 'done') return 'Done'
  if (state === 'failed') return 'Failed'
  if (state === 'skipped') return 'Skipped'
  return 'Pending'
}

function phaseClass(state) {
  if (state === 'active' || state === 'retrying') return 'ws-status-phase--active'
  if (state === 'done' || state === 'skipped') return 'ws-status-phase--ok'
  if (state === 'failed') return 'ws-status-phase--bad'
  return 'ws-status-phase--idle'
}

/**
 * @typedef {{
 *   steps: { model: string, sandbox: string, done: string },
 *   repair: { attempt: number, max: number, error: string, variant?: string, mode?: string } | null,
 *   done: { success: boolean, attempts: number, intent?: string } | null,
 *   networkError: string | null,
 *   streaming: boolean,
 *   activityLog: string[],
 *   userIntent: 'conversational' | 'data' | null,
 *   expanded?: boolean,
 *   openrouterModel?: string | null,
 *   lastOpenrouterModel?: string | null,
 * }} PipelineStatusProps
 */

/**
 * One-line current phase: Thinking → Running → Finishing → Done (replaces previous text).
 *
 * @param {PipelineStatusProps} props
 */
export function PipelineStatus({
  steps,
  repair,
  done,
  networkError,
  streaming,
  activityLog,
  userIntent,
  expanded = false,
  openrouterModel = null,
  lastOpenrouterModel = null,
}) {
  const displayModel = openrouterModel ?? lastOpenrouterModel ?? null
  const intentBadge =
    done?.intent === 'conversational' || done?.intent === 'data'
      ? done.intent
      : userIntent === 'conversational' || userIntent === 'data'
        ? userIntent
        : null

  const lastActivity =
    activityLog.length > 0 ? activityLog[activityLog.length - 1] : null

  /** @type {{ text: string, tone: 'idle' | 'active' | 'ok' | 'warn' | 'error', showSpinner: boolean }} */
  let line = { text: 'Send a message to run.', tone: 'idle', showSpinner: false }

  if (networkError) {
    line = { text: networkError, tone: 'error', showSpinner: false }
  } else if (repair?.mode === 'repair') {
    line = {
      text: `Fixing issue (${repair.attempt}/${repair.max}). ${firstLineSnippet(repair.error)}`,
      tone: 'warn',
      showSpinner: streaming,
    }
  } else if (repair?.mode === 'terminal') {
    line = {
      text: repair.error ? firstLineSnippet(repair.error, 120) : 'Run failed.',
      tone: 'error',
      showSpinner: false,
    }
  } else if (!streaming && !done && steps.done === 'failed') {
    line = { text: 'Stopped.', tone: 'warn', showSpinner: false }
  } else if (!streaming && done?.success === true) {
    line = {
      text:
        intentBadge === 'data'
          ? 'Run complete · data'
          : intentBadge === 'conversational'
            ? 'Run complete · chat reply'
            : 'Run complete.',
      tone: 'ok',
      showSpinner: false,
    }
  } else if (!streaming && done?.success === false) {
    line = { text: 'Run failed.', tone: 'error', showSpinner: false }
  } else if (streaming) {
    if (steps.model === 'active') {
      line =
        lastActivity && lastActivity.length <= 56
          ? {
              text: `${lastActivity} · Thinking…`,
              tone: 'active',
              showSpinner: true,
            }
          : { text: 'Thinking…', tone: 'active', showSpinner: true }
    } else if (steps.sandbox === 'retrying') {
      line = { text: 'Retrying sandbox…', tone: 'warn', showSpinner: true }
    } else if (steps.sandbox === 'active') {
      line = { text: 'Running…', tone: 'active', showSpinner: true }
    } else if (
      steps.model === 'done' &&
      steps.sandbox === 'pending' &&
      userIntent === 'data'
    ) {
      line = { text: 'Starting run…', tone: 'active', showSpinner: true }
    } else if (
      steps.model === 'done' &&
      (steps.sandbox === 'done' ||
        steps.sandbox === 'skipped' ||
        steps.sandbox === 'failed') &&
      steps.done === 'pending'
    ) {
      line = { text: 'Finishing…', tone: 'active', showSpinner: true }
    } else {
      line = { text: 'Working…', tone: 'active', showSpinner: true }
    }
  }

  const toneClass =
    line.tone === 'ok'
      ? 'ws-run-bar--ok'
      : line.tone === 'error'
        ? 'ws-run-bar--error'
        : line.tone === 'warn'
          ? 'ws-run-bar--warn'
          : line.tone === 'active'
            ? 'ws-run-bar--active'
            : 'ws-run-bar--idle'

  const recentLogs = activityLog.slice(-6).reverse()
  const intentLabel =
    intentBadge === 'data'
      ? 'Data'
      : intentBadge === 'conversational'
        ? 'Chat'
        : null

  return (
    <div className={`ws-status-stack ${expanded ? 'ws-status-stack--expanded' : ''}`}>
      <div
        className={`ws-run-bar ${toneClass} ${displayModel ? 'ws-run-bar--has-model' : ''}`}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        title={networkError || repair?.error || undefined}
      >
        <div className="ws-run-bar__row">
          {line.showSpinner ? (
            <span className="ws-run-bar__spinner" aria-hidden />
          ) : line.tone === 'ok' ? (
            <span className="ws-run-bar__tick" aria-hidden>
              ✓
            </span>
          ) : line.tone === 'error' ? (
            <span className="ws-run-bar__tick ws-run-bar__tick--bad" aria-hidden>
              ✗
            </span>
          ) : (
            <span className="ws-run-bar__dot" aria-hidden />
          )}
          <span className="ws-run-bar__text">{line.text}</span>
          {intentBadge && (streaming || expanded) ? (
            <span
              className={`ws-run-bar__intent ws-intent-pill ws-intent-pill--${intentBadge}`}
              title="Turn type"
            >
              {expanded ? `Intent: ${intentLabel}` : intentLabel}
            </span>
          ) : null}
        </div>
        {displayModel ? (
          <div className="ws-run-bar__model-row">
            <span className="ws-run-bar__model" title="OpenRouter model used for this answer">
              Model: {displayModel}
            </span>
          </div>
        ) : streaming && expanded ? (
          <div className="ws-run-bar__model-row">
            <span className="ws-run-bar__model ws-run-bar__model--pending" title="Waiting for model slug from server">
              Model: …
            </span>
          </div>
        ) : null}
      </div>

      {expanded ? (
        <div className="ws-status-diagnostics" aria-label="Run diagnostics">
          <div className="ws-status-phases">
            <div className={`ws-status-phase ${phaseClass(steps.model)}`}>
              <span className="ws-status-phase__label">OpenRouter</span>
              <span className="ws-status-phase__value">{stepLabel(steps.model)}</span>
              <span className="ws-status-phase__detail">
                {displayModel || 'Model pending'}
              </span>
            </div>
            <div className={`ws-status-phase ${phaseClass(steps.sandbox)}`}>
              <span className="ws-status-phase__label">Tools</span>
              <span className="ws-status-phase__value">{stepLabel(steps.sandbox)}</span>
              <span className="ws-status-phase__detail">
                {intentLabel ? `Intent: ${intentLabel}` : 'Intent pending'}
              </span>
            </div>
            <div className={`ws-status-phase ${phaseClass(steps.done)}`}>
              <span className="ws-status-phase__label">Finish</span>
              <span className="ws-status-phase__value">{stepLabel(steps.done)}</span>
            </div>
          </div>

          <div className="ws-status-log">
            <div className="ws-status-log__head">
              <span>Recent stream events</span>
              {intentBadge ? <span>{intentBadge === 'data' ? 'Data route' : 'Chat route'}</span> : null}
            </div>
            {recentLogs.length > 0 ? (
              <ol className="ws-status-log__list">
                {recentLogs.map((log, i) => (
                  <li key={`${i}-${log.slice(0, 32)}`}>{log}</li>
                ))}
              </ol>
            ) : (
              <p className="ws-status-log__empty">Waiting for server status events.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
