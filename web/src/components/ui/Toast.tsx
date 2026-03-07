"use client";

import * as React from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/cn";

/* ─── Types ─── */

export type ToastTone = "success" | "error" | "info";

export type ToastItem = {
  id: string;
  message: string;
  tone: ToastTone;
  durationMs: number;
};

type ToastContextValue = {
  toast: (message: string, tone?: ToastTone, durationMs?: number) => void;
};

const ToastContext = React.createContext<ToastContextValue>({
  toast: () => {},
});

export function useToast() {
  return React.useContext(ToastContext);
}

/* ─── Styling ─── */

const toneStyles: Record<ToastTone, string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  error: "border-rose-200 bg-rose-50 text-rose-800",
  info: "border-[#C0D8FF] bg-[#EBF3FF] text-[#1B64DA]",
};

const toneIcons: Record<ToastTone, React.ReactNode> = {
  success: <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />,
  error: <XCircle className="h-4 w-4 shrink-0 text-rose-600" />,
  info: <Info className="h-4 w-4 shrink-0 text-[#3182F6]" />,
};

/* ─── Single Toast ─── */

function ToastRow({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: (id: string) => void;
}) {
  const [exiting, setExiting] = React.useState(false);

  React.useEffect(() => {
    const timer = setTimeout(() => setExiting(true), item.durationMs - 300);
    const remove = setTimeout(() => onDismiss(item.id), item.durationMs);
    return () => {
      clearTimeout(timer);
      clearTimeout(remove);
    };
  }, [item.id, item.durationMs, onDismiss]);

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium shadow-lg transition-all duration-300",
        toneStyles[item.tone],
        exiting ? "translate-x-full opacity-0" : "translate-x-0 opacity-100",
      )}
    >
      {toneIcons[item.tone]}
      <span className="flex-1">{item.message}</span>
      <button
        onClick={() => onDismiss(item.id)}
        className="shrink-0 rounded p-0.5 opacity-50 transition-opacity hover:opacity-100"
        aria-label="알림 닫기"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/* ─── Provider ─── */

const MAX_TOASTS = 5;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);

  const dismiss = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = React.useCallback(
    (message: string, tone: ToastTone = "info", durationMs: number = 4000) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev.slice(-(MAX_TOASTS - 1)), { id, message, tone, durationMs }]);
    },
    [],
  );

  const value = React.useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}

      {/* Toast container — fixed bottom-right */}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2" role="status" aria-live="polite" aria-atomic="false">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto">
            <ToastRow item={t} onDismiss={dismiss} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
