import * as React from "react";

import { cn } from "@/lib/cn";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "min-h-28 w-full resize-y rounded-xl border border-[color:var(--line)] " +
            "bg-[color:var(--card)]/60 backdrop-blur-md px-3 py-2 text-sm text-[color:var(--ink)] " +
            "shadow-sm outline-none transition-all duration-300 " +
            "placeholder:text-[color:var(--muted)] " +
            "focus:border-[color:var(--accent-purple)]/60 " +
            "focus:bg-[color:var(--card)]/80 " +
            "focus:shadow-[0_0_20px_rgba(30,64,175,0.15)] " +
            "hover:border-[color:var(--accent-purple)]/40",
          className,
        )}
        {...props}
      />
    );
  },
);
Textarea.displayName = "Textarea";

