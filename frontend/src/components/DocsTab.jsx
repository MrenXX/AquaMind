export function DocsTab() {
  return (
    <div className="ws-docs">
      <header className="ws-docs__head">
        <p className="ws-docs__eyebrow">Integration</p>
        <h1 className="ws-docs__title">AquaMind dashboard</h1>
        <p className="ws-docs__lede">
          Quick reference for running the chat backend, SQLite analytics, and this Vite UI against
          WaterSec-OpenClaw.
        </p>
      </header>

      <section className="ws-docs__section">
        <h2 className="ws-docs__h2">Environment</h2>
        <ul className="ws-docs__list">
          <li>
            <code className="ws-docs__code">VITE_CHAT_API=/api</code> — same-origin proxy to FastAPI
            (see <code className="ws-docs__code">vite.config.ts</code>).
          </li>
          <li>
            <code className="ws-docs__code">VITE_ANALYTICS_API</code> — optional override for SQLite
            dashboard calls; defaults to the chat API base.
          </li>
          <li>
            <code className="ws-docs__code">AQUAMIND_CORS_ORIGINS</code> — only if you call the API
            without the proxy.
          </li>
        </ul>
      </section>

      <section className="ws-docs__section">
        <h2 className="ws-docs__h2">Backend contract</h2>
        <table className="ws-docs__table">
          <thead>
            <tr>
              <th scope="col">Endpoint</th>
              <th scope="col">Role</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <code className="ws-docs__code">POST /run</code>
              </td>
              <td>SSE chat runs — status, model_output, code, sandbox_result, done</td>
            </tr>
            <tr>
              <td>
                <code className="ws-docs__code">GET /health</code>
              </td>
              <td>
                Liveness; may include <code className="ws-docs__code">openrouter_roles</code> for model
                routing
              </td>
            </tr>
            <tr>
              <td>
                <code className="ws-docs__code">GET /dashboard/summary</code>
              </td>
              <td>SQLite KPI snapshot for the Insights tab</td>
            </tr>
            <tr>
              <td>
                <code className="ws-docs__code">POST /tools/query_metrics</code>
              </td>
              <td>Aggregates on trusted or raw events</td>
            </tr>
            <tr>
              <td>
                <code className="ws-docs__code">POST /tools/find_motifs</code>
              </td>
              <td>Customer C motif patterns</td>
            </tr>
            <tr>
              <td>
                <code className="ws-docs__code">POST /tools/detect_anomalies</code>
              </td>
              <td>Anomaly candidates with caveats</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="ws-docs__section">
        <h2 className="ws-docs__h2">SQLite data layer</h2>
        <ol className="ws-docs__list ws-docs__list--ordered">
          <li>
            From WaterSec-OpenClaw repo root:{' '}
            <code className="ws-docs__code">python scripts\etl\build_database.py</code>
          </li>
          <li>
            <code className="ws-docs__code">python scripts\validate_db.py</code>
          </li>
          <li>
            <code className="ws-docs__code">.\scripts\start-aquamind-backend.ps1</code>
          </li>
        </ol>
        <p className="ws-docs__note">
          Output DB: <code className="ws-docs__code">data\aquamind.sqlite</code>. See{' '}
          <code className="ws-docs__code">docs/SQLITE_BACKEND.md</code> in that repo for normalization and
          trusted vs flagged rows.
        </p>
      </section>
    </div>
  )
}
