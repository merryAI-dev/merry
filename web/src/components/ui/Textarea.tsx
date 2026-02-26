import * as React from "react";

import { cn } from "@/lib/cn";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={cn(
          "min-h-28 w-full resize-y rounded-xl border border-[#E5E8EB] " +
            "bg-white px-3 py-2 text-sm text-[#191F28] " +
            "outline-none " +
            "placeholder:text-[#B0B8C1] " +
            "hover:border-[#C7CDD3] " +
            "focus:border-[#3182F6] focus:ring-2 focus:ring-[#3182F6]/15 " +
            "disabled:bg-[#F2F4F6] disabled:text-[#B0B8C1] disabled:cursor-not-allowed",
          className,
        )}
        {...props}
      />
    );
  },
);
Textarea.displayName = "Textarea";

