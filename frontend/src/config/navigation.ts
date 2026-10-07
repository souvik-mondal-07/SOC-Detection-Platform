export interface NavItem {
  label: string;
  path: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { label: "Dashboard", path: "/dashboard" },
  { label: "Security Events", path: "/security-events" },
  { label: "Alerts", path: "/alerts" },
  { label: "Detection Rules", path: "/detection-rules" },
  { label: "Investigations", path: "/investigations" },
  { label: "Settings", path: "/settings" },
];
