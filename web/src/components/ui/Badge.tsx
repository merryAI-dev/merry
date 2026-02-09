import * as React from "react";

import { cn } from "@/lib/cn";

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warn" | "danger" | "accent";
};

const tones: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "bg-black/5 text-[color:var(--ink)]",
  success: "bg-emerald-500/15 text-emerald-900",
  warn: "bg-amber-500/15 text-amber-900",
  danger: "bg-rose-500/15 text-rose-900",
  accent: "bg-[color:color-mix(in_oklab,var(--accent),white_82%)] text-[color:var(--ink)]",
};

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

