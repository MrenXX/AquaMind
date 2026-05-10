import { useEffect, useRef } from 'react'

/**
 * @param {{ source: string }} props
 */
export function CodePanel({ source }) {
  const codeRef = useRef(null)
  const has = Boolean(source && source.length)

  useEffect(() => {
    const el = codeRef.current
    if (!el) return
    if (!has) {
      el.textContent = ''
      el.className = 'language-python'
      return
    }
    const hljs = globalThis.hljs
    if (hljs && typeof hljs.highlight === 'function') {
      const { value } = hljs.highlight(source, { language: 'python' })
      el.innerHTML = value
      el.className = 'language-python hljs'
    } else {
      el.textContent = source
      el.className = 'language-python'
    }
  }, [source, has])

  const copy = () => {
    if (!source) return
    void navigator.clipboard.writeText(source)
  }

  return (
    <section className="ws-panel">
      <header className="ws-panel__head ws-panel__head--row">
        <h2 className="ws-panel__title">Script that ran</h2>
        {has ? (
          <button
            type="button"
            className="ws-pill-btn ws-pill-btn--outline ws-pill-btn--sm"
            onClick={copy}
          >
            Copy
          </button>
        ) : null}
      </header>
      <div className="ws-panel__body">
        {!has ? (
          <div className="ws-empty">
            <span className="ws-empty__icon" aria-hidden>
              ⟨ ⟩
            </span>
            <p className="ws-empty__text">
              Expert view exposes the generated script once a run produces code.
            </p>
          </div>
        ) : (
          <div className="ws-code-wrap">
            <pre className="ws-code-pre">
              <code ref={codeRef} className="language-python" />
            </pre>
          </div>
        )}
      </div>
    </section>
  )
}
