import { useEffect } from "react";
import { useOutletContext } from "react-router-dom";
import type { BackendState } from "./useBackendHealth";

/** Shared by all pages through the layout: one refresh counter, one "last updated" time. */
export interface LayoutContext {
  backend: BackendState;
  refreshKey: number;
  /** Re-runs every data request on the current page. */
  refresh: () => void;
  /** Called by pages with the time of their last successful load (null while nothing has loaded). */
  reportUpdated: (date: Date | null) => void;
}

export function useLayoutContext(): LayoutContext {
  return useOutletContext<LayoutContext>();
}

export function useRefreshKey(): number {
  return useLayoutContext().refreshKey;
}

/** Publishes the page's last successful retrieval time to the top bar. */
export function useReportUpdated(updatedAt: Date | null): void {
  const { reportUpdated } = useLayoutContext();
  const time = updatedAt?.getTime() ?? null;
  useEffect(() => {
    reportUpdated(time === null ? null : new Date(time));
  }, [time, reportUpdated]);
}
