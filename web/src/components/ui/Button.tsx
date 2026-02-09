import * as React from "react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

const base =
  "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all duration-300 " +
  "disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent-purple)] " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--bg-dark)]";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-gradient-to-r from-[color:var(--accent-purple)] to-[color:var(--accent-cyan)] " +
    "text-white font-semibold shadow-lg " +
    "hover:shadow-[0_0_30px_rgba(168,85,247,0.4)] hover:scale-[1.02] " +
    "active:scale-[0.98] relative overflow-hidden " +
    "before:absolute before:inset-0 before:bg-gradient-to-r before:from-white/0 before:via-white/20 before:to-white/0 " +
    "before:translate-x-[-200%] hover:before:translate-x-[200%] before:transition-transform before:duration-700",
  secondary:
    "bg-[color:var(--card)] backdrop-blur-lg text-[color:var(--ink)] " +
    "border border-[color:var(--line)] hover:border-[color:var(--accent-purple)]/40 " +
    "hover:bg-[color:var(--card-strong)] hover:shadow-[0_0_20px_rgba(168,85,247,0.15)] " +
    "hover:scale-[1.01] active:scale-[0.99]",
  ghost:
    "text-[color:var(--ink)] hover:bg-[color:var(--card)]/50 backdrop-blur-sm " +
    "border border-transparent hover:border-[color:var(--accent-purple)]/20 " +
    "hover:shadow-[0_0_15px_rgba(168,85,247,0.1)]",
  danger:
    "bg-gradient-to-r from-[color:var(--accent-pink)] to-red-600 " +
    "text-white font-semibold shadow-lg " +
    "hover:shadow-[0_0_30px_rgba(236,72,153,0.4)] hover:scale-[1.02] " +
    "active:scale-[0.98]",
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

