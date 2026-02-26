import * as React from "react";

import { cn } from "@/lib/cn";

export type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "success" | "warn" | "danger" | "accent";
};

const tones: Record<NonNullable<BadgeProps["tone"]>, string> = {
  neutral: "bg-[#F2F4F6] text-[#4E5968] border border-[#E5E8EB]",
  success: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  warn:    "bg-amber-50 text-amber-700 border border-amber-200",
  danger:  "bg-rose-50 text-rose-700 border border-rose-200",
  accent:  "bg-[#EBF3FF] text-[#3182F6] border border-[#C0D8FF]",
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

