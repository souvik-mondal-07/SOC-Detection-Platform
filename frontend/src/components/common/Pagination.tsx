import { PAGE_SIZES } from "../../types/alerts";

interface PaginationProps {
  page: number;
  limit: number;
  /** Items matching the current filters across all pages, as reported by the API. */
  total: number;
  onPage: (page: number) => void;
  onLimit: (limit: number) => void;
}

const BTN = "btn";

export default function Pagination({ page, limit, total, onPage, onLimit }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / limit));
  const first = total === 0 ? 0 : (page - 1) * limit + 1;
  const last = Math.min(total, page * limit);
  return (
    <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted">
      <p role="status">
        Showing {first}–{last} of {total}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2">
          <span>Per page</span>
          <select
            value={limit}
            onChange={(e) => onLimit(Number(e.target.value))}
            className="field !mt-0 !w-auto"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>{size}</option>
            ))}
          </select>
        </label>
        <button type="button" className={BTN} onClick={() => onPage(page - 1)} disabled={page <= 1}>Previous</button>
        <span aria-current="page">Page {page} of {pages}</span>
        <button type="button" className={BTN} onClick={() => onPage(page + 1)} disabled={page >= pages}>Next</button>
      </div>
    </nav>
  );
}
