import { useCallback, useRef, useState } from 'react'

function parseFrames(buffer) {
  const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const frames = []
  const parts = normalized.split('\n\n')
  const incomplete = parts.pop() ?? ''
  for (const block of parts) {
    const lines = block.split('\n').filter(Boolean)
    let eventName = 'message'
    const dataLines = []
    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
    }
    const dataStr = dataLines.join('\n')
    if (!dataStr) continue
    try {
      const data = JSON.parse(dataStr)
      frames.push({ event: eventName, data })
    } catch {
      frames.push({ event: eventName, data: dataStr })
    }
  }
  return { frames, rest: incomplete }
}

/**
 * POST /run SSE consumer. Yields { event, data } for each SSE frame.
 * @param {ReadableStreamDefaultReader<Uint8Array>} reader
 */
export async function* readSSEFrames(reader, signal) {
  const decoder = new TextDecoder()
  let carry = ''
  for (;;) {
    if (signal?.aborted) break
    const { value, done } = await reader.read()
    if (done) break
    carry += decoder.decode(value, { stream: true })
    const { frames, rest } = parseFrames(carry)
    carry = rest
    for (const f of frames) yield f
  }
  if (carry.trim()) {
    const { frames } = parseFrames(carry + '\n\n')
    for (const f of frames) yield f
  }
}

export function getApiBase() {
  const chatEnv = import.meta.env.VITE_CHAT_API
  if (typeof chatEnv === 'string' && chatEnv.trim()) {
    return chatEnv.replace(/\/$/, '')
  }
  const fromEnv = import.meta.env.VITE_API_BASE
  if (typeof fromEnv === 'string' && fromEnv.trim()) {
    return fromEnv.replace(/\/$/, '')
  }
  return 'http://127.0.0.1:8765'
}

export function getRunUrl(apiBase = getApiBase()) {
  return `${apiBase}/run`
}

export function getHealthUrl(apiBase = getApiBase()) {
  return `${apiBase}/health`
}

function runErrorMessage(error, runUrl) {
  if (error instanceof TypeError) {
    return `Cannot reach ${runUrl}. Start the chat backend, set VITE_CHAT_API if it is not on this URL, and make sure CORS allows the Vite origin.`
  }

  return error instanceof Error ? error.message : 'Network error'
}

/**
 * @typedef {{ event: string, data: unknown }} SseEventRecord
 */

/**
 * @param {{ apiBase?: string }} [opts]
 */
export function useSSEStream(opts = {}) {
  const apiBase = opts.apiBase ?? getApiBase()
  const readerRef = useRef(null)
  const abortRef = useRef(null)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState(null)
  const [events, setEvents] = useState(/** @type {SseEventRecord[]} */ ([]))

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    const r = readerRef.current
    if (r) {
      void r.cancel()
      readerRef.current = null
    }
  }, [])

  const run = useCallback(
    async (prompt, onFrame) => {
      cancel()
      const ac = new AbortController()
      abortRef.current = ac
      setEvents([])
      setError(null)
      setStreaming(true)
      const runUrl = getRunUrl(apiBase)
      try {
        const response = await fetch(runUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt }),
          signal: ac.signal,
        })
        if (!response.ok) {
          let detail =
            response.status === 429
              ? 'The model service is busy (rate limit). Wait a minute and try again.'
              : `Run failed (${response.status})`
          try {
            const t = await response.text()
            if (t && t.length > 0 && t.length < 600) {
              try {
                const j = JSON.parse(t)
                const msg = j?.detail ?? j?.message
                if (typeof msg === 'string' && msg.trim()) {
                  detail = `${detail}: ${msg.trim()}`
                }
              } catch {
                if (t.length < 400) detail = `${detail}: ${t.trim()}`
              }
            }
          } catch {
            /* keep detail */
          }
          throw new Error(detail)
        }
        if (!response.body) {
          throw new Error('Run failed (empty response body)')
        }
        const reader = response.body.getReader()
        readerRef.current = reader
        for await (const frame of readSSEFrames(reader, ac.signal)) {
          setEvents((prev) => [...prev, frame])
          onFrame?.(frame.event, frame.data)
        }
      } catch (e) {
        const message = runErrorMessage(e, runUrl)
        if (ac.signal.aborted) {
          setError(null)
        } else {
          setError(message)
        }
        throw new Error(message, { cause: e })
      } finally {
        readerRef.current = null
        setStreaming(false)
        abortRef.current = null
      }
    },
    [apiBase, cancel],
  )

  return { streaming, error, events, run, cancel, setError }
}
