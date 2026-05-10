/**
 * @param {{ streaming: boolean }} props
 */
export function EvidenceStage({ streaming }) {
  return (
    <section className="ws-evidence-stage" aria-label="Awaiting run evidence">
      <div className="ws-evidence-stage__orb" aria-hidden />
      <div className="ws-evidence-stage__grid" aria-hidden />
      <div className="ws-evidence-stage__content">
        <p className="ws-evidence-stage__eyebrow">
          {streaming ? 'Preparing evidence' : 'Evidence stage'}
        </p>
        <h2 className="ws-evidence-stage__title">
          {streaming ? 'AquaMind is building the result view.' : 'Run evidence will land here.'}
        </h2>
        <p className="ws-evidence-stage__text">
          Output cards and visualizations stay hidden until the backend returns something
          worth inspecting.
        </p>
        <div className="ws-evidence-stage__rail" aria-hidden>
          <span>Output</span>
          <span>Rows</span>
          <span>Visuals</span>
        </div>
      </div>
    </section>
  )
}
