import { canAcknowledge, type AlertListItem } from "../../types/alerts";

export type QuickAction = "acknowledge" | "investigate";

interface Props {
  alert: AlertListItem;
  /** True while any lifecycle request is running; all row actions are disabled so a request cannot be submitted twice. */
  busy: boolean;
  onAction: (alert: AlertListItem, action: QuickAction) => void;
}

/** Table shortcuts for the two changes that need no reason. Resolve, false positive and reopen live in the detail view (reason + confirmation). */
export default function AlertRowActions({ alert, busy, onAction }: Props) {
  const stop = (e: React.MouseEvent) => e.stopPropagation();
  return (
    <div className="flex gap-1.5" onClick={stop}>
      <button type="button" className="btn !px-2 !py-1 !text-xs" disabled={busy || !canAcknowledge(alert)} onClick={() => onAction(alert, "acknowledge")} aria-label={`Acknowledge alert ${alert.alert_id}`}>
        Ack
      </button>
      <button type="button" className="btn !px-2 !py-1 !text-xs" disabled={busy || alert.status !== "open"} onClick={() => onAction(alert, "investigate")} aria-label={`Start investigating alert ${alert.alert_id}`}>
        Investigate
      </button>
    </div>
  );
}
