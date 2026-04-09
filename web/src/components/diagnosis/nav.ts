import {
  FolderKanban,
  History,
  Stethoscope,
  UploadCloud,
  type LucideIcon,
} from "lucide-react";

export type DiagnosisNavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  match: (pathname: string) => boolean;
};

export const DIAGNOSIS_NAV_ITEMS: DiagnosisNavItem[] = [
  {
    href: "/diagnosis",
    label: "진단 시작",
    icon: Stethoscope,
    match: (pathname) => pathname === "/diagnosis",
  },
  {
    href: "/diagnosis/upload",
    label: "업로드",
    icon: UploadCloud,
    match: (pathname) => pathname === "/diagnosis/upload" || pathname.startsWith("/diagnosis/upload/"),
  },
  {
    href: "/diagnosis/sessions",
    label: "진단 세션",
    icon: FolderKanban,
    match: (pathname) => pathname === "/diagnosis/sessions" || pathname.startsWith("/diagnosis/sessions/"),
  },
  {
    href: "/diagnosis/history",
    label: "히스토리",
    icon: History,
    match: (pathname) => pathname === "/diagnosis/history" || pathname.startsWith("/diagnosis/history/"),
  },
];
