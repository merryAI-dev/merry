import * as React from "react";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

const base =
  "inline-flex items-center justify-center gap-2 rounded-xl font-semibold " +
  "transition-all duration-150 " +
  "disabled:opacity-40 disabled:pointer-events-none " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7C3AED] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0F]";

const variants: Record<ButtonVariant, string> = {
  primary:
    "text-white " +
    "shadow-[0_2px_12px_rgba(124,58,237,0.4)] hover:shadow-[0_4px_20px_rgba(124,58,237,0.5)] active:scale-[0.98]",
  secondary:
    "border text-[#A0A0BC] " +
    "hover:text-[#F0F0F8] active:scale-[0.98]",
  ghost:
    "hover:text-[#F0F0F8] active:scale-[0.98]",
  danger:
    "bg-[#F43F5E] text-white hover:bg-[#E11D48] active:bg-[#BE123C] active:scale-[0.98] " +
    "shadow-[0_2px_12px_rgba(244,63,94,0.35)]",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-4 text-sm",
  lg: "h-12 px-5 text-[15px]",
};

export function Button({
  className,
  variant = "secondary",
  size = "md",
  type,
  style,
  ...props
}: ButtonProps) {
  const variantStyle: React.CSSProperties =
    variant === "primary"
      ? { background: "linear-gradient(135deg, #7C3AED, #6D28D9)" }
      : variant === "secondary"
      ? { background: "var(--bg-elevated)", borderColor: "var(--card-border)" }
      : variant === "ghost"
      ? { color: "var(--ink-light)" }
      : {};

  return (
    <button
      className={cn(base, variants[variant], sizes[size], className)}
      type={type ?? "button"}
      style={{ ...variantStyle, ...style }}
      {...props}
    />
  );
}
