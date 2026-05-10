/**
 * @param {{ text: string }} props
 */
export function ModelOutput({ text }) {
  const has = Boolean(text && text.length)

  return (
    <section className="ws-panel">
      <header className="ws-panel__head ws-panel__head--stack">
        <h2 className="ws-panel__title">Model draft</h2>
        <p className="ws-panel__subtitle">
          OpenRouter transcript. The answering model appears in the routing card when reported.
        </p>
      </header>
      <div className="ws-panel__body">
        {!has ? (
          <div className="ws-empty">
            <span className="ws-empty__icon" aria-hidden>
              ≡
            </span>
            <p className="ws-empty__text">
              Turn on Expert view during a run to inspect the raw model transcript
              here.
            </p>
          </div>
        ) : (
          <pre className="ws-model-pre">{text}</pre>
        )}
      </div>
    </section>
  )
}
