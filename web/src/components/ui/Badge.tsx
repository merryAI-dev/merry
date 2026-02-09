import * as React from "react";

import { cn } from "@/lib/cn";

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warn" | "danger" | "accent";
};

const tones: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral:
    "bg-[color:var(--card)]/80 backdrop-blur-sm text-[color:var(--ink)] " +
    "border border-[color:var(--line)]",
  success:
    "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 " +
    "shadow-[0_0_10px_rgba(16,185,129,0.2)]",
  warn:
    "bg-amber-500/20 text-amber-300 border border-amber-500/30 " +
    "shadow-[0_0_10px_rgba(245,158,11,0.2)]",
  danger:
    "bg-rose-500/20 text-rose-300 border border-rose-500/30 " +
    "shadow-[0_0_10px_rgba(244,63,94,0.2)]",
  accent:
    "bg-gradient-to-r from-[color:var(--accent-purple)]/20 to-[color:var(--accent-cyan)]/20 " +
    "text-[color:var(--accent-cyan)] border border-[color:var(--accent-purple)]/30 " +
    "shadow-[0_0_10px_rgba(14,165,233,0.15)]",
};

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium transition-all duration-200",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

