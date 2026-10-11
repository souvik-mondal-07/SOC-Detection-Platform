import { fetchRule, fetchRules } from "../services/api";
import type { RuleQuery } from "../types/rules";
import { useAsync } from "./useAsync";
import { useRefreshKey } from "./useRefresh";

export function useRules(query: RuleQuery) {
  const { page, limit, category, severity, enabled, name } = query;
  return useAsync((signal) => fetchRules(query, signal), [page, limit, category, severity, enabled, name], { refreshKey: useRefreshKey() });
}

export function useRule(ruleId: string) {
  return useAsync((signal) => fetchRule(ruleId, signal), [ruleId]);
}
