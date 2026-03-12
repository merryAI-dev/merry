import * as React from "react";

import { cn } from "@/lib/cn";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, style, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "min-h-28 w-full resize-y rounded-xl border px-3 py-2 text-sm outline-none transition-all duration-150 " +
          "placeholder:opacity-40 " +
          "disabled:opacity-40 disabled:cursor-not-allowed",
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
Textarea.displayName = "Textarea";
