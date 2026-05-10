import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { initialState, reducer } from './reducer.js'
import { getHealthUrl, useSSEStream } from './hooks/useSSEStream.js'
import { Topbar } from './components/Topbar.jsx'
import { ChatThread } from './components/ChatThread.jsx'
import { ChatComposer } from './components/ChatComposer.jsx'
import { PipelineStatus } from './components/PipelineStatus.jsx'
import { ModelOutput } from './components/ModelOutput.jsx'
import { CodePanel } from './components/CodePanel.jsx'
import { SandboxResult } from './components/SandboxResult.jsx'
import { ChartPanel } from './components/ChartPanel.jsx'
import { EvidenceStage } from './components/EvidenceStage.jsx'
import { OpenRouterRouting } from './components/OpenRouterRouting.jsx'
import { WaterSecInsights } from './components/WaterSecInsights.jsx'
import { DocsTab } from './components/DocsTab.jsx'

const DEBUG_STORAGE_KEY = 'aquamind_debug_details'

/** @typedef {'overview' | 'pipeline' | 'routing' | 'insights' | 'docs'} AppTabId */

function readInitialDebug() {
  if (typeof window === 'undefined') return false
  try {
    const params = new URLSearchParams(window.location.search)
    if (params.get('debug') === '1') return true
  } catch {
    /* ignore */
  }
  try {
    return window.localStorage.getItem(DEBUG_STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

function sseAction(event, data) {
  if (data == null || typeof data !== 'object') return null
  switch (event) {
    case 'status':
      return { type: 'SSE_STATUS', payload: data }
    case 'model_output':
      return { type: 'SSE_MODEL_OUTPUT', payload: data }
    case 'code':
      return { type: 'SSE_CODE', payload: data }
    case 'sandbox_result':
      return { type: 'SSE_SANDBOX_RESULT', payload: data }
    case 'repair':
      return { type: 'SSE_REPAIR', payload: data }
    case 'done':
      return { type: 'SSE_DONE', payload: data }
    default:
      return null
  }
}

function makeMessage(role, text) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    role,
    text,
  }
}

function firstLineSnippet(text, maxLen = 140) {
  const line = (text ?? '').split('\n')[0].trim()
  if (line.length <= maxLen) return line
  return `${line.slice(0, maxLen - 1)}…`
}

/**
 * @param {unknown} payload
 * @returns {Record<string, unknown> | null}
 */
function extractOpenrouterRoles(payload) {
  if (payload == null || typeof payload !== 'object' || Array.isArray(payload)) return null
  const o = /** @type {Record<string, unknown>} */ (payload)
  const direct =
    o.openrouter_roles ??
    o.openrouterRoles ??
    o.openrouter_routing ??
    o.openrouterRouting
  if (direct && typeof direct === 'object' && !Array.isArray(direct)) {
    return /** @type {Record<string, unknown>} */ (direct)
  }
  const routing = o.routing
  if (routing && typeof routing === 'object' && !Array.isArray(routing)) {
    const r = /** @type {Record<string, unknown>} */ (routing)
    const nested = r.openrouter_roles ?? r.openrouterRoles
    if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
      return /** @type {Record<string, unknown>} */ (nested)
    }
  }
  return null
}

/**
 * @param {Record<string, unknown>} data
 * @returns {string}
 */
function statusMessageText(data) {
  const raw = data.message
  if (typeof raw === 'string') return raw
  if (Array.isArray(raw)) return raw.filter((x) => typeof x === 'string').join('\n')
  return ''
}

/**
 * @param {object} opts
 * @param {boolean} opts.showTechnical
 * @param {'conversational' | 'data' | null} opts.userIntent
 */
function updateChatForFrame(messages, event, data, opts) {
  const { showTechnical, userIntent } = opts
  if (data == null || typeof data !== 'object') return messages

  /** Payload sometimes carries intent before intentRef updates */
  const intentForChat =
    userIntent ??
    (data.intent === 'conversational' || data.intent === 'data' ? data.intent : null)

  if (event === 'status') {
    const text = statusMessageText(data)
    if (!text) return messages
    if (data.step === 'intent') {
      return messages
    }
    /** Routine pipeline narration stays in PipelineStatus / activityLog only (not here). */
    if (data.error === true) {
      return [...messages, makeMessage('system', text)]
    }
    return messages
  }

  if (event === 'model_output' && typeof data.raw === 'string' && data.raw) {
    if (!showTechnical && intentForChat !== 'conversational') return messages
    const next = [...messages]
    const last = next[next.length - 1]
    if (last?.role === 'assistant') {
      next[next.length - 1] = { ...last, text: last.text + data.raw }
      return next
    }
    return [...next, makeMessage('assistant', data.raw)]
  }

  if (event === 'repair') {
    const attempt = data.attempt ?? '?'
    const max = data.max ?? 3
    const error = typeof data.error === 'string' ? data.error : 'Something went wrong in the run.'
    const detail = firstLineSnippet(error)
    return [
      ...messages,
      makeMessage(
        'system',
        `Fixing a problem (try ${attempt} of ${max}).${detail ? ` ${detail}` : ''}`,
      ),
    ]
  }

  if (event === 'done') {
    const intent =
      data.intent === 'conversational' || data.intent === 'data' ? data.intent : intentForChat
    const tail =
      intent === 'data'
        ? ' (data run)'
        : intent === 'conversational'
          ? ' (chat reply)'
          : ''
    return [
      ...messages,
      makeMessage(
        'system',
        data.success ? `All set — run finished.${tail}` : `Something went wrong.${tail}`,
      ),
    ]
  }

  return messages
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [prompt, setPrompt] = useState('')
  const [messages, setMessages] = useState([])
  const [debugDetails, setDebugDetails] = useState(readInitialDebug)
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState(null)
  /** First /health attempt finished (success or failure). */
  const [healthReady, setHealthReady] = useState(false)
  const [activeTab, setActiveTab] = useState(
    /** @type {'overview' | 'pipeline' | 'routing' | 'insights' | 'docs'} */ ('overview'),
  )
  const { run, cancel, streaming } = useSSEStream()
  const userAbortRef = useRef(false)
  const intentRef = useRef(/** @type {'conversational' | 'data' | null} */ (null))

  const setDebugDetailsPersisted = useCallback((value) => {
    setDebugDetails(value)
    try {
      window.localStorage.setItem(DEBUG_STORAGE_KEY, value ? 'true' : 'false')
    } catch {
      /* ignore */
    }
  }, [])

  const topbarOk =
    !state.networkError && !(state.done && state.done.success === false)

  useEffect(() => {
    if (state.userIntent === 'conversational' || state.userIntent === 'data') {
      intentRef.current = state.userIntent
    }
  }, [state.userIntent])

  const loadHealth = useCallback(async (signal) => {
    try {
      const response = await fetch(getHealthUrl(), { signal })
      if (!response.ok) throw new Error(`Health check failed (${response.status})`)
      const payload = await response.json()
      setHealth(payload)
      setHealthError(null)
    } catch (e) {
      if (signal?.aborted) return
      setHealth(null)
      setHealthError(e instanceof Error ? e.message : 'Health check failed')
    } finally {
      if (!signal?.aborted) setHealthReady(true)
    }
  }, [])

  useEffect(() => {
    const ac = new AbortController()
    queueMicrotask(() => {
      void loadHealth(ac.signal)
    })
    return () => ac.abort()
  }, [loadHealth])

  /** Refetch OpenRouter routing metadata when opening the Model routing tab. */
  useEffect(() => {
    if (activeTab !== 'routing') return
    const ac = new AbortController()
    queueMicrotask(() => {
      void loadHealth(ac.signal)
    })
    return () => ac.abort()
  }, [activeTab, loadHealth])

  /** Refetch after a run finishes — backend may expose routing only then. */
  const wasStreamingRef = useRef(false)
  useEffect(() => {
    if (wasStreamingRef.current && !streaming) {
      const ac = new AbortController()
      queueMicrotask(() => {
        void loadHealth(ac.signal)
      })
      return () => ac.abort()
    }
    wasStreamingRef.current = streaming
  }, [streaming, loadHealth])

  /** Refetch when returning to the tab (e.g. after restarting the API). */
  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState !== 'visible') return
      const ac = new AbortController()
      queueMicrotask(() => {
        void loadHealth(ac.signal)
      })
    }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [loadHealth])

  const openrouterRoles = useMemo(() => extractOpenrouterRoles(health), [health])

  const onClearConversation = useCallback(() => {
    if (streaming) return
    intentRef.current = null
    dispatch({ type: 'RESET_SESSION' })
    setMessages([])
  }, [streaming])

  const onSend = useCallback(async () => {
    const trimmed = prompt.trim()
    if (!trimmed || streaming) return
    userAbortRef.current = false
    intentRef.current = null
    setMessages((prev) => [...prev, makeMessage('user', trimmed)])
    setPrompt('')
    dispatch({ type: 'RUN_START' })
    try {
      await run(trimmed, (event, data) => {
        if (
          event === 'status' &&
          data &&
          typeof data === 'object' &&
          data.step === 'intent' &&
          (data.intent === 'conversational' || data.intent === 'data')
        ) {
          intentRef.current = data.intent
        }
        const action = sseAction(event, data)
        if (action) dispatch(action)
        setMessages((prev) =>
          updateChatForFrame(prev, event, data, {
            showTechnical: debugDetails,
            userIntent: intentRef.current,
          }),
        )
      })
    } catch (e) {
      if (userAbortRef.current) return
      const msg =
        e instanceof Error ? e.message : typeof e === 'string' ? e : 'Network error'
      dispatch({ type: 'SSE_ERROR', payload: { message: msg } })
      setMessages((prev) => [...prev, makeMessage('system', msg)])
    }
  }, [run, streaming, prompt, debugDetails])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && streaming) {
        userAbortRef.current = true
        cancel()
        dispatch({ type: 'RUN_CANCELLED' })
        setMessages((prev) => [...prev, makeMessage('system', 'Cancelled.')])
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [streaming, cancel])

  const pipelineSection = (
    <section className="ws-dashboard" aria-label="Run evidence panels">
      <div className="ws-run-status-card">
        <PipelineStatus
          steps={state.steps}
          repair={state.repair}
          done={state.done}
          networkError={state.networkError}
          streaming={streaming}
          activityLog={state.activityLog}
          userIntent={state.userIntent}
          expanded={debugDetails}
          openrouterModel={state.openrouterModel}
          lastOpenrouterModel={state.lastOpenrouterModel}
        />
      </div>
      <div className="ws-expert-bar">
        <div className="ws-expert-bar__text">
          <span className="ws-expert-bar__label">Expert view</span>
          <span className="ws-expert-bar__hint">
            Optional: model transcript and generated script for review.
          </span>
        </div>
        <button
          type="button"
          className={`ws-debug-toggle ${debugDetails ? 'ws-debug-toggle--on' : ''}`}
          role="switch"
          aria-checked={debugDetails}
          aria-label={debugDetails ? 'Turn off expert view' : 'Turn on expert view'}
          onClick={() => setDebugDetailsPersisted(!debugDetails)}
        >
          <span className="ws-debug-toggle__knob" aria-hidden />
        </button>
      </div>
      {debugDetails ? (
        <div className="ws-dashboard__row2">
          <ModelOutput text={state.modelRaw} />
          <CodePanel source={state.codeSource} />
        </div>
      ) : null}
      {state.sandboxResult ? (
        <div className="ws-dashboard__row3">
          <SandboxResult result={state.sandboxResult} />
          <ChartPanel
            pngBase64={state.sandboxResult?.png_base64}
            chartArtifacts={state.sandboxResult?.chart_artifacts}
          />
        </div>
      ) : (
        <EvidenceStage streaming={streaming} />
      )}
    </section>
  )

  return (
    <div className="ws-app">
      <Topbar topbarOk={topbarOk} activeTab={activeTab} onSelectTab={setActiveTab} />
      <div className="ws-shell">
        <main className="ws-main">
          {activeTab === 'overview' ? (
            <div
              className="ws-tab-panel"
              id="ws-tabpanel-overview"
              role="tabpanel"
              aria-labelledby="ws-tab-overview"
            >
              <div className="ws-workspace ws-workspace--overview">
                <section className="ws-chat-column">
                  <ChatThread
                    messages={messages}
                    streaming={streaming}
                    onClearConversation={onClearConversation}
                  />
                  <ChatComposer
                    value={prompt}
                    streaming={streaming}
                    onChange={setPrompt}
                    onSend={() => void onSend()}
                  />
                  <p className="ws-chat-note">
                    {debugDetails
                      ? 'Expert view adds technical detail to streamed replies when shown here. Use Pipeline for execution evidence and Model routing for OpenRouter tiers.'
                      : 'Runs your request securely on WaterSec systems. Open Pipeline for run status and charts.'}
                  </p>
                </section>
              </div>
            </div>
          ) : null}

          {activeTab === 'pipeline' ? (
            <div
              className="ws-tab-panel"
              id="ws-tabpanel-pipeline"
              role="tabpanel"
              aria-labelledby="ws-tab-pipeline"
            >
              <div
                className={`ws-pipeline-page ${debugDetails ? 'ws-pipeline-page--expert' : ''}`}
              >
                {pipelineSection}
              </div>
            </div>
          ) : null}

          {activeTab === 'routing' ? (
            <div
              className="ws-tab-panel"
              id="ws-tabpanel-routing"
              role="tabpanel"
              aria-labelledby="ws-tab-routing"
            >
              <div className="ws-routing-page">
                <OpenRouterRouting
                  roles={openrouterRoles}
                  currentModel={state.openrouterModel ?? state.lastOpenrouterModel}
                  error={healthError}
                  healthReady={healthReady}
                />
                <p className="ws-routing-page__hint">
                  Planned slugs come from <code className="ws-routing-page__code">GET /health</code>.
                  The live model for the last run is shown when the API streams{' '}
                  <code className="ws-routing-page__code">openrouter_model</code>.
                </p>
              </div>
            </div>
          ) : null}

          {activeTab === 'insights' ? (
            <div
              className="ws-tab-panel"
              id="ws-tabpanel-insights"
              role="tabpanel"
              aria-labelledby="ws-tab-insights"
            >
              <WaterSecInsights />
            </div>
          ) : null}

          {activeTab === 'docs' ? (
            <div
              className="ws-tab-panel"
              id="ws-tabpanel-docs"
              role="tabpanel"
              aria-labelledby="ws-tab-docs"
            >
              <DocsTab />
            </div>
          ) : null}
        </main>
      </div>
    </div>
  )
}
