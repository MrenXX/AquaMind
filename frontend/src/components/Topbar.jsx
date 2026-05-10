import { useId } from 'react'

function LogoSvg() {
  return (
    <svg
      className="ws-logo-svg"
      width="36"
      height="36"
      viewBox="0 0 36 36"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M18 4C14 10 8 16 8 22a10 10 0 1 0 20 0c0-6-6-12-10-18z"
        stroke="var(--ws-primary)"
        strokeWidth="2"
        fill="none"
        strokeLinejoin="round"
      />
      <path
        d="M18 14v8M14 18h8"
        stroke="var(--ws-primary)"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

/**
 * @typedef {'overview' | 'pipeline' | 'routing' | 'insights' | 'docs'} AppTabId
 */

/**
 * @param {{
 *   topbarOk: boolean,
 *   activeTab: AppTabId,
 *   onSelectTab: (id: AppTabId) => void,
 * }} props
 */
export function Topbar({ topbarOk, activeTab, onSelectTab }) {
  const navId = useId()

  /** @type {{ id: AppTabId, label: string }[]} */
  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'pipeline', label: 'Pipeline' },
    { id: 'routing', label: 'Model routing' },
    { id: 'insights', label: 'Insights' },
    { id: 'docs', label: 'Docs' },
  ]

  return (
    <header className="ws-topbar">
      <div className="ws-topbar__left">
        <div className="ws-logo-mark" aria-label="AquaMind">
          <LogoSvg />
          <span className="ws-logo-mark__wordmark">
            <span className="ws-logo-mark__aqua">aqua</span>
            <span className="ws-logo-mark__mind">mind.</span>
          </span>
        </div>
      </div>
      <nav className="ws-topbar__nav" aria-label="Primary" id={navId}>
        <div className="ws-topbar__tabs" role="tablist" aria-orientation="horizontal">
          {tabs.map((t) => {
            const selected = activeTab === t.id
            return (
              <button
                key={t.id}
                type="button"
                role="tab"
                id={`ws-tab-${t.id}`}
                aria-selected={selected}
                tabIndex={selected ? 0 : -1}
                aria-controls={`ws-tabpanel-${t.id}`}
                className={`ws-topbar__link ${selected ? 'ws-topbar__link--active' : ''}`}
                onClick={() => onSelectTab(t.id)}
              >
                {t.label}
              </button>
            )
          })}
        </div>
      </nav>
      <div className="ws-topbar__right">
        <span
          className={`ws-status-dot ${topbarOk ? 'ws-status-dot--ok' : 'ws-status-dot--bad'}`}
          title={topbarOk ? 'Connected' : 'Error'}
          aria-hidden
        />
        <span className="ws-ops-pill">WaterSec Ops</span>
      </div>
    </header>
  )
}
