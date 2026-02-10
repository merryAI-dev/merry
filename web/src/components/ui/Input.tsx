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
            "bg-[color:var(--card)] backdrop-blur-md px-3 text-sm text-[color:var(--ink)] " +
            "shadow-sm outline-none transition-all duration-300 " +
            "placeholder:text-[color:var(--muted)] " +
            "focus:border-[color:var(--accent-cyan)] " +
            "focus:bg-white " +
            "focus:shadow-[0_0_15px_rgba(0,102,204,0.12),0_4px_16px_rgba(0,30,70,0.08)] " +
            "hover:border-[color:var(--accent-purple)]/40 " +
            "dark:focus:bg-[color:var(--card-strong)] dark:focus:shadow-[0_0_20px_rgba(30,64,175,0.15)]",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

