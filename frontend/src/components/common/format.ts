/** Local, readable time. Falls back to the raw text when the value is not a valid date. */
export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function formatClock(date: Date): string {
  return date.toLocaleTimeString();
}
