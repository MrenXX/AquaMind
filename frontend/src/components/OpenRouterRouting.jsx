function routeParts(route) {
  if (!route) return []
  if (typeof route === 'string') return [route]
  if (Array.isArray(route)) return route.filter((item) => typeof item === 'string')
  if (typeof route !== 'object') return []

  const primary =
    typeof route.primary === 'string'
      ? route.primary
      : typeof route.model === 'string'
        ? route.model
        : typeof route.default === 'string'
          ? route.default
          : null

  const fallbackRaw = route.fallbacks ?? route.fallback ?? route.secondary ?? []
  const fallbacks =
    typeof fallbackRaw === 'string'
      ? [fallbackRaw]
      : Array.isArray(fallbackRaw)
        ? fallbackRaw.filter((item) => typeof item === 'string')
        : []

  return [primary, ...fallbacks].filter(Boolean)
}

const ROLE_LABELS = {
  chat: 'Chat',
  planner: 'Planner',
  code: 'Code',
}

/**
 * @param {{
 *   roles: Record<string, unknown> | null,
 *   currentModel: string | null,
 *   error: string | null,
 *   healthReady?: boolean,
 * }} props
 */
export function OpenRouterRouting({ roles, currentModel, error, healthReady = false }) {
  const roleEntries = roles && typeof roles === 'object' ? Object.entries(roles) : []
  const ordered = ['chat', 'planner', 'code']
    .map((key) => [key, roles?.[key]])
    .filter(([, value]) => value != null)

  const extra = roleEntries.filter(([key]) => !ordered.some(([known]) => known === key))
  const entries = [...ordered, ...extra]

  return (
    <section className="ws-router-card" aria-label="OpenRouter routing">
      <header className="ws-router-card__head">
        <div>
          <p className="ws-router-card__eyebrow">OpenRouter</p>
          <h2 className="ws-router-card__title">Model routing</h2>
        </div>
        <span className="ws-router-card__current" title="Per-run slug comes from SSE (openrouter_model), not only from this table.">
          {currentModel ? `Answered by ${currentModel}` : 'Per-run slug: SSE events'}
        </span>
      </header>
      {error ? <p className="ws-router-card__error">{error}</p> : null}
      {entries.length > 0 ? (
        <div className="ws-router-routes">
          {entries.map(([role, route]) => {
            const parts = routeParts(route)
            return (
              <div key={role} className="ws-router-route">
                <span className="ws-router-route__role">
                  {ROLE_LABELS[role] ?? role.replace(/_/g, ' ')}
                </span>
                {parts.length > 0 ? (
                  <span className="ws-router-route__models">
                    {parts.map((part, i) => (
                      <span key={`${role}-${part}-${i}`} className="ws-router-route__model">
                        {i > 0 ? <span className="ws-router-route__arrow">→</span> : null}
                        {part}
                      </span>
                    ))}
                  </span>
                ) : (
                  <span className="ws-router-route__muted">Not reported</span>
                )}
              </div>
            )
          })}
        </div>
      ) : error ? null : !healthReady ? (
        <p className="ws-router-card__empty">Fetching /health…</p>
      ) : (
        <div className="ws-router-card__empty ws-router-card__empty--block">
          <p>
            No planned routing table in this /health JSON (look for{' '}
            <code className="ws-router-card__code">openrouter_roles</code>). That only affects this
            card; it does not block the run status bar.
          </p>
          <p>
            After you send a prompt, the status bar shows the slug when the API includes{' '}
            <code className="ws-router-card__code">openrouter_model</code> on{' '}
            <code className="ws-router-card__code">status</code>, <code className="ws-router-card__code">model_output</code>, or{' '}
            <code className="ws-router-card__code">done</code>. Restart the chat backend after changing model env vars,
            then reload this page or switch tabs away and back to refetch /health.
          </p>
        </div>
      )}
    </section>
  )
}
