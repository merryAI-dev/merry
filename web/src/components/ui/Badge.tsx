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
    "bg-emerald-50 text-emerald-700 border border-emerald-200 " +
    "dark:bg-emerald-500/20 dark:text-emerald-300 dark:border-emerald-500/30",
  warn:
    "bg-amber-50 text-amber-700 border border-amber-200 " +
    "dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-500/30",
  danger:
    "bg-rose-50 text-rose-700 border border-rose-200 " +
    "dark:bg-rose-500/20 dark:text-rose-300 dark:border-rose-500/30",
  accent:
    "bg-gradient-to-r from-[color:var(--accent-purple)]/10 to-[color:var(--accent-cyan)]/10 " +
    "text-[color:var(--accent-purple)] border border-[color:var(--accent-purple)]/20 " +
    "dark:from-[color:var(--accent-purple)]/20 dark:to-[color:var(--accent-cyan)]/20 " +
    "dark:text-[color:var(--accent-cyan)] dark:border-[color:var(--accent-purple)]/30",
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

