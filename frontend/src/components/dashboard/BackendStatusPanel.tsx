import type { BackendState } from "../../hooks/useBackendHealth";

export default function BackendStatusPanel({ backend }: { backend: BackendState }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5" aria-labelledby="backend-heading">
      <h2 id="backend-heading" className="text-base font-semibold text-ink">
        Backend connection
      </h2>
      {backend.kind === "loading" && <p className="mt-2 text-sm text-slate-500">Contacting the API…</p>}
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
          ].map(([term, detail]) => (
            <div key={term} className="flex justify-between gap-4 border-b border-slate-100 pb-1">
              <dt className="text-slate-500">{term}</dt>
              <dd className="font-medium text-ink">{detail}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
