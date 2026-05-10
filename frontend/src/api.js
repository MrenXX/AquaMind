import { getApiBase, getRunUrl, readSSEFrames } from './hooks/useSSEStream.js'

export function getAnalyticsBase() {
  const fromEnv = import.meta.env.VITE_ANALYTICS_API
  if (typeof fromEnv === 'string' && fromEnv.trim()) {
    return fromEnv.replace(/\/$/, '')
  }
  return getApiBase()
}

/**
 * @param {string} prompt
 * @param {(event: string, data: unknown) => void} onEvent
 * @param {() => void} [onDone]
 * @param {(err: Error) => void} [onError]
 * @param {{ signal?: AbortSignal }} [opts]
 */
export async function postRun(prompt, onEvent, onDone, onError, opts = {}) {
  const apiBase = getApiBase()
  const runUrl = getRunUrl(apiBase)
  try {
    const response = await fetch(runUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
      signal: opts.signal,
    })
    if (!response.ok || !response.body) {
      throw new Error(`Run failed (${response.status})`)
    }
    const reader = response.body.getReader()
    for await (const frame of readSSEFrames(reader, opts.signal)) {
      onEvent(frame.event, frame.data)
      if (frame.event === 'done') break
    }
    onDone?.()
  } catch (e) {
    const err =
      e instanceof TypeError
        ? new Error(
            `Cannot reach ${runUrl}. Start the chat backend, set VITE_CHAT_API if needed, and enable CORS for the Vite origin.`,
          )
        : e instanceof Error
          ? e
          : new Error('Request failed')
    onError?.(err)
    throw err
  }
}

/**
 * Fetches real analytics sidecar data. Use this only for paths backed by the
 * analytics FastAPI service; the UI must not invent telemetry.
 *
 * @param {string} path
 * @param {unknown} [body]
 */
export async function fetchAnalytics(path, body) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const response = await fetch(`${getAnalyticsBase()}${normalizedPath}`, {
    method: body == null ? 'GET' : 'POST',
    headers: body == null ? undefined : { 'Content-Type': 'application/json' },
    body: body == null ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(`Analytics request failed (${response.status})`)
  }

  if (response.status === 204) return null
  const text = await response.text()
  return text ? JSON.parse(text) : null
}
