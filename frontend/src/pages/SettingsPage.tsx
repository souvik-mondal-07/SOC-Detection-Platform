import { useLayoutContext } from "../components/layout/AppLayout";
import { getApiBaseUrlForDisplay } from "../services/api";

function Section({ title, rows }: { title: string; rows: readonly (readonly [string, string])[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5" aria-label={title}>
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
        {rows.map(([term, detail]) => (
          <div key={term} className="flex justify-between gap-4 border-b border-slate-100 pb-1">
            <dt className="text-slate-500">{term}</dt>
            <dd className="break-all text-right font-medium text-ink">{detail}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Read-only information. No secrets are read or shown, and there are no security settings to change. */
export default function SettingsPage() {
  const { backend } = useLayoutContext();
  const online = backend.kind === "online" ? backend.data : null;
  const unknown = backend.kind === "loading" ? "Checking…" : "Unavailable";

  return (
    <>
      <Section title="Frontend" rows={[
        ["Application", "SOC Detection Platform"],
        ["Frontend version", __APP_VERSION__],
        ["Build mode", import.meta.env.MODE],
      ]} />
      <Section title="API configuration" rows={[
        ["API base URL", getApiBaseUrlForDisplay()],
        ["Set by", "VITE_API_BASE_URL (frontend .env)"],
      ]} />
      <Section title="Backend" rows={[
        ["Status", online?.status ?? unknown],
        ["Service", online?.service ?? unknown],
        ["Backend version", online?.version ?? unknown],
        ["Environment", online?.environment ?? unknown],
        ["Database", online?.database ?? unknown],
      ]} />
      <p className="text-sm text-slate-500">
        Authentication and security settings are not shown because the backend does not support them yet.
      </p>
    </>
  );
}
