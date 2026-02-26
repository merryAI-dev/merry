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
          "h-11 w-full rounded-xl border border-[#E5E8EB] bg-white px-3 text-sm text-[#191F28] " +
          "placeholder:text-[#B0B8C1] outline-none " +
          "hover:border-[#C7CDD3] " +
          "focus:border-[#3182F6] focus:ring-2 focus:ring-[#3182F6]/15 " +
          "disabled:bg-[#F2F4F6] disabled:text-[#B0B8C1] disabled:cursor-not-allowed " +
          "read-only:bg-[#F8F9FA] read-only:text-[#4E5968]",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

