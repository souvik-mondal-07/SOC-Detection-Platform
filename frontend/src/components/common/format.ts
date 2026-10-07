/** Local, readable time. Falls back to the raw text when the value is not a valid date. */
export function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
