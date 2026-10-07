import type { ReactNode } from "react";

type Variant = "loading" | "error" | "empty";

const STYLES: Record<Variant, string> = {
  loading: "border-slate-200 bg-white text-slate-500",
  error: "border-red-200 bg-red-50 text-critical",
  empty: "border-dashed border-slate-300 bg-white text-slate-600",
};

interface StateMessageProps {
  variant: Variant;
  title: string;
  children?: ReactNode;
}

/** Loading, error and empty states share one look. Errors are announced to screen readers. */
export default function StateMessage({ variant, title, children }: StateMessageProps) {
  return (
    <div
      className={`rounded-lg border p-8 text-center ${STYLES[variant]}`}
      role={variant === "error" ? "alert" : "status"}
    >
      <p className="text-sm font-semibold">{title}</p>
      {children && <div className="mt-1 text-sm">{children}</div>}
    </div>
  );
}
