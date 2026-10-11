import type { ReactNode } from "react";

export type IconName =
  | "shield" | "dashboard" | "alert" | "events" | "rules" | "settings" | "investigate"
  | "refresh" | "database" | "pulse" | "crosshair" | "inbox" | "menu" | "close" | "server" | "clock";

const PATHS: Record<IconName, ReactNode> = {
  shield: <path d="M12 3l7 3v5c0 4.5-3 8.2-7 10-4-1.8-7-5.5-7-10V6l7-3z M9 12l2 2 4-4" />,
  dashboard: <path d="M4 13h6V4H4v9zm0 7h6v-5H4v5zm10 0h6v-9h-6v9zm0-16v5h6V4h-6z" />,
  alert: <path d="M12 3l9.5 17h-19L12 3z M12 10v4 M12 17.2v.1" />,
  events: <path d="M4 5h16 M4 10h10 M4 15h16 M4 20h8" />,
  rules: <path d="M9 6h11 M9 12h11 M9 18h11 M4 6l1.2 1.2L7 5.4 M4 12l1.2 1.2L7 11.4 M4 18l1.2 1.2L7 17.4" />,
  settings: <path d="M12 15a3 3 0 100-6 3 3 0 000 6z M19.4 13.5a7.6 7.6 0 000-3l2-1.5-2-3.4-2.3.9a7.5 7.5 0 00-2.6-1.5L14 2.5h-4l-.5 2.5a7.5 7.5 0 00-2.6 1.5l-2.3-.9-2 3.4 2 1.5a7.6 7.6 0 000 3l-2 1.5 2 3.4 2.3-.9a7.5 7.5 0 002.6 1.5l.5 2.5h4l.5-2.5a7.5 7.5 0 002.6-1.5l2.3.9 2-3.4-2-1.5z" />,
  investigate: <path d="M10.5 18a7.5 7.5 0 100-15 7.5 7.5 0 000 15z M16 16l5 5" />,
  refresh: <path d="M20 11a8 8 0 00-14.5-4M4 4v4h4 M4 13a8 8 0 0014.5 4M20 20v-4h-4" />,
  database: <path d="M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6 M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />,
  pulse: <path d="M3 12h4l2-6 4 12 2-6h6" />,
  crosshair: <path d="M12 21a9 9 0 100-18 9 9 0 000 18z M12 2v5 M12 17v5 M2 12h5 M17 12h5" />,
  inbox: <path d="M3 13l3-8h12l3 8v6H3v-6z M3 13h5l1 3h6l1-3h5" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  server: <path d="M4 5h16v6H4V5zm0 8h16v6H4v-6z M8 8h.01 M8 16h.01" />,
  clock: <path d="M12 21a9 9 0 100-18 9 9 0 000 18z M12 7v5l3 2" />,
};

/** Stroke icons drawn inline (no icon library). Decorative by default; pass `label` when the icon is the only content. */
export default function Icon({ name, className = "h-5 w-5", label }: { name: IconName; className?: string; label?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      {PATHS[name]}
    </svg>
  );
}
