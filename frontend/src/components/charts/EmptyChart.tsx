import Icon from "../common/Icons";

/** Shown instead of a chart when the API returned nothing to plot. Never draws placeholder data. */
export default function EmptyChart({ text }: { text: string }) {
  return (
    <div className="flex h-40 flex-col items-center justify-center gap-2 rounded border border-dashed border-line-strong text-center text-sm text-muted" role="status">
      <Icon name="crosshair" className="h-6 w-6 text-dim" />
      {text}
    </div>
  );
}
