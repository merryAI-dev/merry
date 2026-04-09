import {
  ClipboardList,
  FilePlus2,
  History,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";

export type ReviewNavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  match: (pathname: string) => boolean;
};

export const REVIEW_NAV_ITEMS: ReviewNavItem[] = [
  {
    href: "/report",
    label: "세션",
    icon: ClipboardList,
    match: (pathname) =>
      pathname === "/report" ||
      (pathname.startsWith("/report/") && pathname !== "/report/new" && !pathname.startsWith("/report/new/")),
  },
  {
    href: "/report/new",
    label: "새 보고서",
    icon: FilePlus2,
    match: (pathname) => pathname === "/report/new" || pathname.startsWith("/report/new/"),
  },
  {
    href: "/review",
    label: "검토 큐",
    icon: ShieldAlert,
    match: (pathname) => pathname === "/review" || pathname.startsWith("/review/"),
  },
  {
    href: "/history",
    label: "히스토리",
    icon: History,
    match: (pathname) => pathname === "/history" || pathname.startsWith("/history/"),
  },
];
