import type { ReactNode } from "react";
import type { AsyncState } from "../../hooks/useAsync";
import ErrorState from "../common/ErrorState";
import { Skeleton } from "../common/Skeleton";

/** Renders the loading and error states of one dashboard section; children render only when data is loaded. */
export default function SectionState<T>({ state, reload, title, children }: { state: AsyncState<T>; reload: () => void; title: string; children: (data: T) => ReactNode }) {
  if (state.kind === "loading") return <div role="status" aria-label={`Loading ${title}`}><Skeleton className="h-56 w-full" /></div>;
  if (state.kind === "error") return <ErrorState title={`Could not load ${title}`} message={state.message} onRetry={reload} />;
  return <>{children(state.data)}</>;
}
