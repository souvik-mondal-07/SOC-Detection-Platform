import { useEffect, useState } from "react";

/** Local date and time, updated once a second. Isolated so only this small component re-renders. */
export default function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <time dateTime={now.toISOString()} className="font-mono text-xs tabular-nums text-body">
      {now.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })} {now.toLocaleTimeString()}
    </time>
  );
}
