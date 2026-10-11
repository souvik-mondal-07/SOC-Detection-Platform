import type { ReactNode } from "react";
import Icon, { type IconName } from "./Icons";

type Variant = "loading" | "error" | "empty";

const STYLES: Record<Variant, string> = {
  loading: "border-line bg-panel text-muted",
  error: "border-critical/50 bg-critical/10 text-critical",
  empty: "border-dashed border-line-strong bg-panel/60 text-muted",
};
const ICONS: Record<Variant, IconName> = { loading: "pulse", error: "alert", empty: "inbox" };

interface StateMessageProps {
  variant: Variant;
  title: string;
  children?: ReactNode;
}

/** Loading, error and empty states share one look. Errors are announced to screen readers. */
export default function StateMessage({ variant, title, children }: StateMessageProps) {
  return (
    <div className={`rounded-lg border p-8 text-center ${STYLES[variant]}`} role={variant === "error" ? "alert" : "status"}>
      <Icon name={ICONS[variant]} className="mx-auto mb-3 h-7 w-7 opacity-80" />
      <p className={`text-sm font-semibold ${variant === "error" ? "text-critical" : "text-fg"}`}>{title}</p>
      {children && <div className="mt-1 text-sm text-body">{children}</div>}
    </div>
  );
}
