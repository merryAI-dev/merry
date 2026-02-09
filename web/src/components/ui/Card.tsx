import * as React from "react";

import { cn } from "@/lib/cn";

export type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  variant?: "default" | "strong";
};

export function Card({ className, variant = "default", ...props }: CardProps) {
  return (
    <div
      className={cn(variant === "strong" ? "m-card-strong" : "m-card", "rounded-2xl p-5", className)}
      {...props}
    />
  );
}

