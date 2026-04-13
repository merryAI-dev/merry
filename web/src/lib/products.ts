export type ProductSlug = "review" | "diagnosis";

export type Product = {
  slug: ProductSlug;
  label: string;
  description: string;
  href: string;
};

export const PRODUCTS: Product[] = [
  {
    slug: "review",
    label: "투자심사",
    description: "딜 검토, 시장 근거, 가정, 계산을 다루는 분석 워크벤치",
    href: "/review",
  },
  {
    slug: "diagnosis",
    label: "현황진단",
    description: "진단시트 업로드, 항목 점검, 엑셀 반영을 다루는 진단 스튜디오",
    href: "/diagnosis",
  },
];

export const DEFAULT_AFTER_LOGIN_PATH = "/products";

type WorkspaceLike = {
  teamId: string;
  memberName?: string;
} | null | undefined;

function diagnosisRolloutMode(): "all" | "internal" | "off" {
  const raw = (process.env.MERRY_DIAGNOSIS_ROLLOUT ?? "all").trim().toLowerCase();
  if (raw === "internal" || raw === "off") return raw;
  return "all";
}

function diagnosisInternalTeams(): Set<string> {
  return new Set(
    (process.env.MERRY_DIAGNOSIS_INTERNAL_TEAM_IDS ?? "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean),
  );
}

export function isDiagnosisEnabledForWorkspace(workspace?: WorkspaceLike): boolean {
  const mode = diagnosisRolloutMode();
  if (mode === "off") return false;
  if (mode === "all") return true;
  if (!workspace?.teamId) return false;
  return diagnosisInternalTeams().has(workspace.teamId);
}

export function getVisibleProducts(workspace?: WorkspaceLike): Product[] {
  return PRODUCTS.filter((product) => product.slug !== "diagnosis" || isDiagnosisEnabledForWorkspace(workspace));
}

export function getProductBySlug(slug: string): Product {
  const product = PRODUCTS.find((item) => item.slug === slug);
  if (!product) throw new Error(`Unknown product: ${slug}`);
  return product;
}

export function productNavLabel(slug: ProductSlug): string {
  return getProductBySlug(slug).label;
}
