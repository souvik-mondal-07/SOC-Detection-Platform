interface UnavailableStateProps {
  title: string;
  message: string;
  /** What this page will show once the backend provides it. */
  plannedFields?: readonly string[];
}

/** For sections whose backend functionality does not exist yet. Shows no data at all. */
export default function UnavailableState({ title, message, plannedFields }: UnavailableStateProps) {
  return (
    <section className="rounded-lg border border-dashed border-slate-300 bg-white p-8" aria-labelledby="unavailable-heading">
      <h2 id="unavailable-heading" className="text-base font-semibold text-ink">
        {title}
      </h2>
      <p className="mt-1 max-w-2xl text-sm text-slate-600">{message}</p>
      {plannedFields && plannedFields.length > 0 && (
        <div className="mt-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Planned for this page</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {plannedFields.map((field) => (
              <li key={field} className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
                {field}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
