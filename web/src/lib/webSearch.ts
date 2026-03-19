/**
 * Google Custom Search API integration for market intelligence.
 * Provides web search, parallel multi-query, and site-filtered search.
 */

export type SearchResult = {
  title: string;
  url: string;
  snippet: string;
  publishedAt?: string;
  source?: string;
};

type GoogleSearchItem = {
  title?: string;
  link?: string;
  snippet?: string;
  pagemap?: {
    metatags?: Array<{ "article:published_time"?: string; "og:updated_time"?: string }>;
  };
};

type GoogleSearchResponse = {
  items?: GoogleSearchItem[];
  searchInformation?: { totalResults?: string };
};

function getSearchConfig() {
  const apiKey = (process.env.GOOGLE_SEARCH_API_KEY ?? "").trim();
  const engineId = (process.env.GOOGLE_SEARCH_ENGINE_ID ?? "").trim();
  if (!apiKey || !engineId) return null;
  return { apiKey, engineId };
}

function extractSource(url: string): string {
  try {
    const host = new URL(url).hostname.replace("www.", "");
    return host;
  } catch {
    return "";
  }
}

function extractPublishedDate(item: GoogleSearchItem): string | undefined {
  const meta = item.pagemap?.metatags?.[0];
  return meta?.["article:published_time"] ?? meta?.["og:updated_time"] ?? undefined;
}

function dateRangeToParam(range?: string): string | undefined {
  if (!range) return undefined;
  const match = range.match(/^(\d+)(d|w|m)$/);
  if (!match) return undefined;
  const [, num, unit] = match;
  const n = Number(num);
  const days = unit === "d" ? n : unit === "w" ? n * 7 : n * 30;
  const d = new Date();
  d.setDate(d.getDate() - days);
  return `date:r:${d.toISOString().slice(0, 10).replace(/-/g, "")}:`;
}

/**
 * Execute a single Google Custom Search query.
 */
export async function webSearch(
  query: string,
  options?: {
    siteFilter?: string[];
    dateRange?: string;
    maxResults?: number;
    language?: string;
  },
): Promise<SearchResult[]> {
  const config = getSearchConfig();
  if (!config) {
    console.warn("[webSearch] Missing GOOGLE_SEARCH_API_KEY or GOOGLE_SEARCH_ENGINE_ID");
    return [];
  }

  const { siteFilter, dateRange, maxResults = 10, language = "lang_ko" } = options ?? {};

  // Build query with site filter
  let q = query;
  if (siteFilter?.length) {
    const siteQ = siteFilter.map((s) => `site:${s}`).join(" OR ");
    q = `${query} (${siteQ})`;
  }

  const params = new URLSearchParams({
    key: config.apiKey,
    cx: config.engineId,
    q,
    num: String(Math.min(maxResults, 10)),
    lr: language,
  });

  const sort = dateRangeToParam(dateRange);
  if (sort) params.set("sort", sort);

  const url = `https://www.googleapis.com/customsearch/v1?${params.toString()}`;

  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(10_000) });
    if (!res.ok) {
      console.error(`[webSearch] HTTP ${res.status}: ${await res.text().catch(() => "")}`);
      return [];
    }

    const data = (await res.json()) as GoogleSearchResponse;
    return (data.items ?? []).map((item) => ({
      title: item.title ?? "",
      url: item.link ?? "",
      snippet: item.snippet ?? "",
      publishedAt: extractPublishedDate(item),
      source: extractSource(item.link ?? ""),
    }));
  } catch (err) {
    console.error("[webSearch] fetch error:", err instanceof Error ? err.message : String(err));
    return [];
  }
}

/**
 * Execute multiple search queries in parallel.
 * Returns a map of query → results.
 */
export async function parallelSearch(
  queries: string[],
  options?: {
    siteFilter?: string[];
    dateRange?: string;
    maxResults?: number;
  },
): Promise<Map<string, SearchResult[]>> {
  const results = new Map<string, SearchResult[]>();
  const promises = queries.map(async (q) => {
    const r = await webSearch(q, options);
    results.set(q, r);
  });
  await Promise.all(promises);
  return results;
}

/**
 * Deduplicate search results by URL.
 */
export function deduplicateResults(results: SearchResult[]): SearchResult[] {
  const seen = new Set<string>();
  return results.filter((r) => {
    if (seen.has(r.url)) return false;
    seen.add(r.url);
    return true;
  });
}
