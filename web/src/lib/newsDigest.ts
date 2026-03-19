/**
 * News Digest: Multi-media coverage filtering and clustering.
 * Adapted from vc-copilot /news command.
 *
 * Coverage Score = unique media count + bonuses
 * - base: unique outlets
 * - +1: specialist + general media both cover
 * - +2: global media mentions
 * - score 1 = EXCLUDED (single source unreliable)
 */

import { type SearchResult, webSearch, deduplicateResults } from "./webSearch";

export type NewsCluster = {
  company: string;
  event: string;
  articles: SearchResult[];
  coverageScore: number;
  grade: "HOT" | "WARM" | "NOTABLE";
  sources: string[];
};

// vc-copilot media source definitions
const SPECIALIST_MEDIA = new Set(["platum.kr", "thevc.kr", "besuccess.com", "byline.network", "venturesquare.net"]);
const GENERAL_MEDIA = new Set(["sedaily.com", "etnews.com", "tech42.co.kr", "unicornfactory.co.kr"]);
const GLOBAL_MEDIA = new Set(["techcrunch.com", "theinformation.com", "bloomberg.com"]);

function classifySource(source: string): "specialist" | "general" | "global" | "other" {
  if (SPECIALIST_MEDIA.has(source)) return "specialist";
  if (GENERAL_MEDIA.has(source)) return "general";
  if (GLOBAL_MEDIA.has(source)) return "global";
  return "other";
}

export function calculateCoverageScore(articles: SearchResult[]): number {
  const uniqueSources = new Set(articles.map((a) => a.source).filter(Boolean));
  let score = uniqueSources.size;

  const hasSpecialist = [...uniqueSources].some((s) => SPECIALIST_MEDIA.has(s!));
  const hasGeneral = [...uniqueSources].some((s) => GENERAL_MEDIA.has(s!));
  const hasGlobal = [...uniqueSources].some((s) => GLOBAL_MEDIA.has(s!));

  if (hasSpecialist && hasGeneral) score += 1;
  if (hasGlobal) score += 2;

  return score;
}

function gradeFromScore(score: number): "HOT" | "WARM" | "NOTABLE" {
  if (score >= 5) return "HOT";
  if (score >= 3) return "WARM";
  return "NOTABLE";
}

/**
 * Simple clustering: group articles by company name appearing in title.
 * Returns clusters with coverage scores.
 */
export function clusterArticles(results: SearchResult[]): NewsCluster[] {
  // Extract company names from titles (simple heuristic: quoted names or first noun phrase)
  const clusters = new Map<string, SearchResult[]>();

  for (const r of results) {
    // Use the first meaningful segment of the title as cluster key
    const key = r.title
      .replace(/[[\]()'"]/g, "")
      .split(/[,|·\-—…]/)[0]
      .trim()
      .slice(0, 30);
    if (!key) continue;

    const existing = clusters.get(key) ?? [];
    existing.push(r);
    clusters.set(key, existing);
  }

  const output: NewsCluster[] = [];
  for (const [company, articles] of clusters) {
    const score = calculateCoverageScore(articles);
    if (score < 2) continue; // Exclude single-source (score 1)

    output.push({
      company,
      event: articles[0].title,
      articles,
      coverageScore: score,
      grade: gradeFromScore(score),
      sources: [...new Set(articles.map((a) => a.source).filter(Boolean))] as string[],
    });
  }

  return output.sort((a, b) => b.coverageScore - a.coverageScore);
}

/**
 * Generate a news digest for a given period and optional sector.
 */
export async function generateNewsDigest(options?: {
  period?: string;
  sector?: string;
}): Promise<{ clusters: NewsCluster[]; totalArticles: number }> {
  const { period = "7d", sector } = options ?? {};
  const year = new Date().getFullYear();

  const sectorQ = sector ? ` ${sector}` : "";

  // Parallel searches across media groups (vc-copilot pattern)
  const queries = [
    `스타트업${sectorQ} 투자 펀딩 ${year}`,
    `스타트업${sectorQ} site:platum.kr OR site:thevc.kr`,
    `스타트업${sectorQ} site:besuccess.com OR site:byline.network OR site:venturesquare.net`,
    `스타트업${sectorQ} site:sedaily.com OR site:etnews.com OR site:tech42.co.kr`,
  ];

  const allResults: SearchResult[] = [];
  const promises = queries.map(async (q) => {
    const results = await webSearch(q, { dateRange: period, maxResults: 10 });
    allResults.push(...results);
  });
  await Promise.all(promises);

  const deduplicated = deduplicateResults(allResults);
  const clusters = clusterArticles(deduplicated);

  return { clusters, totalArticles: deduplicated.length };
}

/**
 * Format news digest as a system prompt block.
 */
export function formatNewsDigestBlock(clusters: NewsCluster[]): string {
  if (!clusters.length) return "";

  const today = new Date().toISOString().slice(0, 10);
  const lines = [`\n[시장 뉴스 다이제스트 — ${today}]`];

  for (const c of clusters.slice(0, 10)) {
    const sourcesStr = c.sources.join(", ");
    lines.push(`[${c.grade}] ${c.company} — ${c.event} (Coverage ${c.coverageScore}, ${sourcesStr})`);
  }

  lines.push("--- 끝 ---\n");
  return lines.join("\n");
}
