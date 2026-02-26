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
  "transition-colors duration-150 " +
  "disabled:opacity-40 disabled:pointer-events-none " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3182F6] focus-visible:ring-offset-2";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-[#3182F6] text-white hover:bg-[#1B6AE4] active:bg-[#1460CC] " +
    "shadow-[0_2px_8px_rgba(49,130,246,0.25)]",
  secondary:
    "bg-white text-[#191F28] border border-[#E5E8EB] " +
    "hover:bg-[#F8F9FA] hover:border-[#D1D6DC] active:bg-[#F2F4F6]",
  ghost:
    "text-[#4E5968] hover:bg-[#F2F4F6] active:bg-[#E5E8EB]",
  danger:
    "bg-[#F03E3E] text-white hover:bg-[#D63030] active:bg-[#BE2A2A] " +
    "shadow-[0_2px_8px_rgba(240,62,62,0.25)]",
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
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(base, variants[variant], sizes[size], className)}
      type={type ?? "button"}
      {...props}
    />
  );
}
