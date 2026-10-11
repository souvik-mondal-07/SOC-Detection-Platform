import { formatClock } from "./format";

interface RefreshErrorProps {
  /** Refresh errors from the data sources on the page; null entries are ignored. */
  errors: readonly (string | null)[];
  /** Time of the data still on screen. */
  updatedAt: Date | null;
  onRetry: () => void;
  /** Names the data source when several banners can appear on one page. */
  label?: string;
}

/** Non-blocking notice shown when a background refresh failed. The previously loaded data stays visible. */
export default function RefreshError({ errors, updatedAt, onRetry, label }: RefreshErrorProps) {
  const messages = [...new Set(errors.filter((e): e is string => e !== null).map((e) => e.replace(/\.+$/, "")))];
  if (messages.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-medium/50 bg-medium/10 px-4 py-2 text-sm text-medium" role="alert">
      <p>
        Could not refresh{label ? ` ${label}` : ""}: {messages.join(" · ")}.{" "}
        {updatedAt ? `Showing data from ${formatClock(updatedAt)}.` : "Showing the previously loaded data."}
      </p>
      <button type="button" onClick={onRetry} className="btn">
        Retry
      </button>
    </div>
  );
}
