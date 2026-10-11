import type { BackendState } from "../../hooks/useBackendHealth";

export default function BackendStatusPanel({ backend }: { backend: BackendState }) {
  return (
    <section className="panel p-5" aria-labelledby="backend-heading">
      <h2 id="backend-heading" className="font-mono text-[13px] font-bold uppercase tracking-[0.12em] text-fg">
        Backend connection
      </h2>
      {backend.kind === "loading" && <p className="mt-2 text-sm text-muted">Contacting the API…</p>}
      {backend.kind === "offline" && (
        <p className="mt-2 text-sm text-critical">
          Cannot reach the backend ({backend.reason}). Start it with <code>uvicorn app.main:app --reload</code> from
          the <code>backend</code> folder.
        </p>
      )}
      {backend.kind === "online" && (
        <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
          {[
            ["Status", backend.data.status],
            ["Service", backend.data.service],
            ["Version", backend.data.version],
            ["Environment", backend.data.environment],
            ["Database", backend.data.database],
          ].map(([term, detail]) => (
            <div key={term} className="flex justify-between gap-4 border-b border-line/60 pb-1">
              <dt className="text-muted">{term}</dt>
              <dd className="font-medium text-fg">{detail}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
