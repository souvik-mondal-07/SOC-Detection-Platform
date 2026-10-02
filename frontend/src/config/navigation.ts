export const NAV_ITEMS = [
  "Overview",
  "Security Events",
  "Alerts",
  "Detection Rules",
  "Investigations",
  "Settings",
] as const;

export type NavItem = (typeof NAV_ITEMS)[number];
