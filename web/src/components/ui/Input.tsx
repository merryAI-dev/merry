import * as React from "react";

import { cn } from "@/lib/cn";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          "h-11 w-full rounded-xl border border-[color:var(--line)] " +
            "bg-[color:var(--card)]/60 backdrop-blur-md px-3 text-sm text-[color:var(--ink)] " +
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
Input.displayName = "Input";

