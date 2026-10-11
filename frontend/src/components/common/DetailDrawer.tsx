import { useEffect, useRef, type ReactNode } from "react";

interface DetailDrawerProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** Right-hand read-only panel. Escape or the backdrop closes it; focus moves in and returns to the trigger on close. */
export default function DetailDrawer({ title, onClose, children }: DetailDrawerProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} aria-hidden="true" />
      <aside role="dialog" aria-modal="true" aria-label={title} className="relative flex h-full w-full max-w-xl flex-col overflow-y-auto border-l border-neon/30 bg-panel shadow-[-12px_0_40px_rgb(0_0_0/0.5)]">
        <div className="sticky top-0 flex items-center justify-between gap-3 border-b border-line bg-panel px-5 py-3">
          <h2 className="font-mono text-[13px] font-bold tracking-[0.1em] text-neon">{title}</h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="btn"
          >
            Close
          </button>
        </div>
        <div className="p-5">{children}</div>
      </aside>
    </div>
  );
}
