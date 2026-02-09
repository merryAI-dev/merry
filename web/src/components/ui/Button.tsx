import * as React from "react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

const base =
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors " +
  "disabled:opacity-50 disabled:pointer-events-none " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--bg)]";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-[color:var(--ink)] text-white hover:bg-[color:color-mix(in_oklab,var(--ink),black_12%)]",
  secondary:
    "bg-white/70 text-[color:var(--ink)] border border-[color:var(--line)] hover:bg-white/90",
  ghost:
    "text-[color:var(--ink)] hover:bg-black/5 border border-transparent hover:border-[color:var(--line)]",
  danger:
    "bg-[color:var(--accent-2)] text-white hover:bg-[color:color-mix(in_oklab,var(--accent-2),black_12%)]",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-4 text-sm",
  lg: "h-12 px-5 text-base",
};

export function Button({
  className,
  variant = "secondary",
  size = "md",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(base, variants[variant], sizes[size], className)}
      {...props}
    />
  );
}

