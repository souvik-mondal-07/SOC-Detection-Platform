// Mirrors backend/app/models/rule_management.py and GET /rules query parameters.

export const RULE_CATEGORIES = ["authentication", "web", "network", "privilege", "correlation", "system", "application"] as const;

export interface RuleSummary {
  rule_id: string;
  name: string;
  category: string;
  severity: string;
  enabled: boolean;
}

export interface RuleDetail extends RuleSummary {
  description: string;
  conditions: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface RuleListResponse {
  success: boolean;
  page: number;
  limit: number;
  total: number;
  count: number;
  rules: RuleSummary[];
}

export interface RuleResponse {
  success: boolean;
  rule: RuleDetail;
}

export interface RuleFilters {
  category: string;
  severity: string;
  enabled: "" | "true" | "false";
  name: string;
}

export interface RuleQuery extends RuleFilters {
  page: number;
  limit: number;
}

export const DEFAULT_RULE_FILTERS: RuleFilters = { category: "", severity: "", enabled: "", name: "" };
