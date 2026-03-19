/**
 * Signal Radar: 5-category weekly signal scanning.
 * Adapted from vc-copilot /signal command.
 *
 * Categories: funding, talent, social, media, regulation
 * Strength: 🔴 Strong (multi-category) / 🟡 Medium (single notable) / — Reference
 */

import { type SearchResult, webSearch, deduplicateResults } from "./webSearch";

export type SignalCategory = "funding" | "talent" | "social" | "media" | "regulation";

export type Signal = {
  category: SignalCategory;
  company?: string;
  sector?: string;
  description: string;
  strength: "strong" | "medium" | "reference";
  source: string;
  url?: string;
};

const CATEGORY_LABELS: Record<SignalCategory, string> = {
  funding: "펀딩",
  talent: "인재이동",
  social: "소셜",
  media: "미디어",
  regulation: "규제/정책",
};

function buildQueries(sector?: string): Record<SignalCategory, string[]> {
  const year = new Date().getFullYear();
  const s = sector ? ` ${sector}` : "";

  return {
    funding: [
      `한국 스타트업${s} 투자 유치 이번주 ${year}`,
      `스타트업${s} 펀딩 site:platum.kr OR site:thevc.kr`,
    ],
    talent: [
      `스타트업${s} CTO VP 영입 ${year}`,
      `대기업 출신 창업${s} ${year}`,
    ],
    social: [
      `앱스토어 순위 급상승 앱${s} 한국 ${year}`,
      `스타트업${s} 대규모 채용 ${year}`,
    ],
    media: [
      `스타트업${s} site:platum.kr OR site:besuccess.com ${year}`,
      `스타트업${s} site:sedaily.com OR site:etnews.com ${year}`,
    ],
    regulation: [
      `신산업 규제 완화${s} ${year}`,
      `규제 샌드박스 신규${s} ${year}`,
    ],
  };
}

function extractSignalsFromResults(category: SignalCategory, results: SearchResult[]): Signal[] {
  return results.map((r) => ({
    category,
    description: r.title,
    strength: "medium" as const,
    source: r.source ?? "",
    url: r.url,
  }));
}

/**
 * Scan all 5 signal categories in parallel.
 */
export async function scanSignals(sector?: string): Promise<{
  signals: Signal[];
  byCategory: Record<SignalCategory, Signal[]>;
}> {
  const queries = buildQueries(sector);
  const byCategory: Record<SignalCategory, Signal[]> = {
    funding: [],
    talent: [],
    social: [],
    media: [],
    regulation: [],
  };

  const categories = Object.keys(queries) as SignalCategory[];
  const promises = categories.flatMap((cat) =>
    queries[cat].map(async (q) => {
      const results = await webSearch(q, { dateRange: "7d", maxResults: 5 });
      const signals = extractSignalsFromResults(cat, results);
      byCategory[cat].push(...signals);
    }),
  );
  await Promise.all(promises);

  // Deduplicate per category by URL
  for (const cat of categories) {
    const seen = new Set<string>();
    byCategory[cat] = byCategory[cat].filter((s) => {
      if (!s.url || seen.has(s.url)) return false;
      seen.add(s.url);
      return true;
    });
  }

  // Cross-category strength: if a company appears in 2+ categories → strong
  const companyCategories = new Map<string, Set<SignalCategory>>();
  const allSignals = categories.flatMap((cat) => byCategory[cat]);
  for (const s of allSignals) {
    // Simple company extraction from description
    const company = s.description.split(/[,|·\-—]/)[0].trim().slice(0, 20);
    const cats = companyCategories.get(company) ?? new Set();
    cats.add(s.category);
    companyCategories.set(company, cats);
  }
  for (const s of allSignals) {
    const company = s.description.split(/[,|·\-—]/)[0].trim().slice(0, 20);
    const cats = companyCategories.get(company);
    if (cats && cats.size >= 2) {
      s.strength = "strong";
      s.company = company;
    }
  }

  return { signals: allSignals, byCategory };
}

/**
 * Format signal radar as a system prompt block.
 */
export function formatSignalRadarBlock(byCategory: Record<SignalCategory, Signal[]>): string {
  const categories = Object.keys(byCategory) as SignalCategory[];
  const hasSignals = categories.some((cat) => byCategory[cat].length > 0);
  if (!hasSignals) return "";

  const lines = ["\n[시그널 레이더]"];

  for (const cat of categories) {
    const signals = byCategory[cat];
    if (!signals.length) continue;

    const strong = signals.filter((s) => s.strength === "strong");
    const medium = signals.filter((s) => s.strength === "medium");

    if (strong.length) {
      lines.push(`🔴 ${CATEGORY_LABELS[cat]}: ${strong.map((s) => s.description).join("; ").slice(0, 100)}`);
    } else if (medium.length) {
      lines.push(`🟡 ${CATEGORY_LABELS[cat]}: ${medium.slice(0, 3).map((s) => s.description).join("; ").slice(0, 100)}`);
    }
  }

  lines.push("--- 끝 ---\n");
  return lines.join("\n");
}
