import { Link } from "react-router-dom";
import type { InvestigationListItem } from "../../types/investigations";
import { formatTimestamp } from "../common/format";
import StatusBadge from "../common/StatusBadge";

const TH = "px-3 py-2.5 text-left font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-muted";
const TD = "px-3 py-2 align-top text-sm text-body";

export default function InvestigationTable({ investigations }: { investigations: readonly InvestigationListItem[] }) {
  return (
    <div className="panel overflow-x-auto">
      <table className="min-w-full divide-y divide-line">
        <caption className="sr-only">Investigations, newest first</caption>
        <thead className="bg-panel-2">
          <tr>
            <th scope="col" className={TH}>Investigation</th>
            <th scope="col" className={TH}>Title</th>
            <th scope="col" className={TH}>Status</th>
            <th scope="col" className={TH}>Alerts</th>
            <th scope="col" className={TH}>Notes</th>
            <th scope="col" className={TH}>Created</th>
            <th scope="col" className={TH}>Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line/60">
          {investigations.map((item) => (
            <tr key={item.investigation_id} className="hover:bg-neon/5">
              <td className={`${TD} whitespace-nowrap font-mono text-xs`}>{item.investigation_id}</td>
              <td className={`${TD} max-w-sm`}>
                <Link
                  to={`/investigations/${encodeURIComponent(item.investigation_id)}`}
                  className="block truncate font-semibold text-fg hover:text-neon hover:underline focus-visible:outline-2 focus-visible:outline-neon"
                  title={item.title}
                  aria-label={`Open investigation ${item.investigation_id}: ${item.title}`}
                >
                  {item.title}
                </Link>
              </td>
              <td className={TD}><StatusBadge value={item.status} /></td>
              <td className={`${TD} tabular-nums`}>{item.alert_count}</td>
              <td className={`${TD} tabular-nums`}>{item.note_count}</td>
              <td className={`${TD} whitespace-nowrap font-mono text-xs tabular-nums text-muted`}>{formatTimestamp(item.created_at)}</td>
              <td className={`${TD} whitespace-nowrap font-mono text-xs tabular-nums text-muted`}>{formatTimestamp(item.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
