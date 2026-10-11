import type { IconName } from "../components/common/Icons";

export interface NavItem {
  label: string;
  path: string;
  icon: IconName;
  /** Heading shown in the top bar for this page. */
  title: string;
  subtitle: string;
  /** Scheduled for a later roadmap step: shown but not clickable. */
  planned?: boolean;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { label: "Dashboard", path: "/dashboard", icon: "dashboard", title: "THREAT OPERATIONS CENTER", subtitle: "Security monitoring • Detection • Investigation" },
  { label: "Security Alerts", path: "/alerts", icon: "alert", title: "SECURITY ALERTS", subtitle: "Prioritized detections • read-only investigation console" },
  { label: "Security Events", path: "/security-events", icon: "events", title: "SECURITY EVENTS", subtitle: "Normalized telemetry • newest first" },
  { label: "Detection Rules", path: "/detection-rules", icon: "rules", title: "DETECTION RULES", subtitle: "Rule-based detection catalog • read-only" },
  { label: "Investigations", path: "/investigations", icon: "investigate", title: "INVESTIGATIONS", subtitle: "Planned for a later step", planned: true },
  { label: "Settings", path: "/settings", icon: "settings", title: "SETTINGS", subtitle: "Application and backend information • read-only" },
];
