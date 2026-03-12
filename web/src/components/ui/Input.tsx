import * as React from "react";

import { cn } from "@/lib/cn";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, style, ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          "h-11 w-full rounded-xl border px-3 text-sm outline-none transition-all duration-150 " +
          "placeholder:opacity-40 " +
          "focus:ring-2 " +
          "disabled:opacity-40 disabled:cursor-not-allowed " +
          "read-only:opacity-60",
          className,
        )}
        style={{
          background: "var(--bg-elevated)",
          borderColor: "var(--card-border)",
          color: "var(--ink)",
          ...style,
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = "#7C3AED";
          e.currentTarget.style.boxShadow = "0 0 0 3px rgba(124,58,237,0.2)";
          props.onFocus?.(e);
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = "var(--card-border)";
          e.currentTarget.style.boxShadow = "";
          props.onBlur?.(e);
        }}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";
