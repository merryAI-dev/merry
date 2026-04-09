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
    href: "/review",
    label: "세션",
    icon: ClipboardList,
    match: (pathname) =>
      pathname === "/review"
      || pathname === "/report"
      || (
        (pathname.startsWith("/review/") || pathname.startsWith("/report/"))
        && pathname !== "/review/new"
        && !pathname.startsWith("/review/new/")
        && pathname !== "/review/queue"
        && !pathname.startsWith("/review/queue/")
        && pathname !== "/report/new"
        && !pathname.startsWith("/report/new/")
      ),
  },
  {
    href: "/review/new",
    label: "새 보고서",
    icon: FilePlus2,
    match: (pathname) =>
      pathname === "/review/new"
      || pathname.startsWith("/review/new/")
      || pathname === "/report/new"
      || pathname.startsWith("/report/new/"),
  },
  {
    href: "/review/queue",
    label: "검토 큐",
    icon: ShieldAlert,
    match: (pathname) => pathname === "/review/queue" || pathname.startsWith("/review/queue/"),
  },
  {
    href: "/history",
    label: "히스토리",
    icon: History,
    match: (pathname) => pathname === "/history" || pathname.startsWith("/history/"),
  },
];
