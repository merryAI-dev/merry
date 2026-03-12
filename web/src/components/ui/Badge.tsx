import * as React from "react";

import { cn } from "@/lib/cn";

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warn" | "danger" | "accent";
};

const tones: Record<NonNullable<BadgeProps["tone"]>, React.CSSProperties> = {
  neutral: { background: "rgba(255,255,255,0.06)", color: "#A0A0BC", border: "1px solid rgba(255,255,255,0.1)" },
  success: { background: "rgba(20,184,166,0.15)",  color: "#2DD4BF", border: "1px solid rgba(20,184,166,0.3)" },
  warn:    { background: "rgba(251,191,36,0.12)",  color: "#FCD34D", border: "1px solid rgba(251,191,36,0.25)" },
  danger:  { background: "rgba(244,63,94,0.12)",   color: "#FB7185", border: "1px solid rgba(244,63,94,0.25)" },
  accent:  { background: "rgba(124,58,237,0.15)",  color: "#A78BFA", border: "1px solid rgba(124,58,237,0.3)" },
};

export function Badge({ className, tone = "neutral", style, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium transition-all duration-200",
        className,
      )}
      style={{ ...tones[tone], ...style }}
      {...props}
    />
  );
}
