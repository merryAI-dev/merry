/**
 * Post-Generation Verification Layer
 *
 * LLM 응답 생성 후, 출처 없는 숫자를 자동으로 [확인 필요]로 교체.
 * 프롬프트가 아닌 코드로 강제 — LLM이 무시할 수 없음.
 *
 * 전략:
 * 1. 응답에서 모든 숫자 표현 추출
 * 2. "신뢰할 수 있는 숫자 풀" (AssumptionPack, ComputeSnapshot, 첨부 문서)과 대조
 * 3. 풀에 없는 숫자가 포함된 주장 → [확인 필요] 태그 추가
 */

export type TrustedNumberPool = {
  /** Raw numbers from AssumptionPack, ComputeSnapshot, file contexts. */
  numbers: Set<number>;
  /** String patterns that are known-safe (e.g., dates, section numbers). */
  safePatterns: Set<string>;
};

/**
 * Extract numbers from AssumptionPack summary text.
 */
export function extractNumbersFromText(text: string): Set<number> {
  const nums = new Set<number>();
  if (!text) return nums;

  // Match various Korean/English number formats
  const patterns = [
    /[\d,]+(?:\.\d+)?/g,                     // 300,000,000 or 3.14
    /([\d.]+)\s*[조억만천백]/g,              // 300억, 2.8조
    /\$([\d,.]+)\s*[BMTbmt]?/g,              // $200B, $3.5M
    /([\d.]+)\s*%/g,                          // 28.5%
    /([\d.]+)\s*[xX배]/g,                    // 3.2x, 10배
  ];

  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(text)) !== null) {
      const raw = (match[1] ?? match[0]).replace(/,/g, "");
      const n = parseFloat(raw);
      if (Number.isFinite(n) && n !== 0) {
        nums.add(n);
        // Also add common transformations
        if (n >= 1) nums.add(Math.round(n));
        // Handle Korean units: 억 = 1e8, 만 = 1e4, 조 = 1e12
        const fullMatch = match[0];
        if (fullMatch.includes("조")) nums.add(n * 1e12);
        if (fullMatch.includes("억")) nums.add(n * 1e8);
        if (fullMatch.includes("만")) nums.add(n * 1e4);
      }
    }
  }

  return nums;
}

/**
 * Build a trusted number pool from all available context.
 */
export function buildTrustedPool(sources: {
  assumptionPackSummary?: string;
  computeSnapshotSummary?: string;
  fileContextTexts?: string[];
  userMessages?: string[];
}): TrustedNumberPool {
  const numbers = new Set<number>();
  const safePatterns = new Set<string>();

  // Extract from each source
  for (const text of [
    sources.assumptionPackSummary,
    sources.computeSnapshotSummary,
    ...(sources.fileContextTexts ?? []),
    ...(sources.userMessages ?? []),
  ]) {
    if (!text) continue;
    for (const n of extractNumbersFromText(text)) {
      numbers.add(n);
    }
  }

  // Safe patterns: dates, section numbers, common constants
  const currentYear = new Date().getFullYear();
  for (let y = 2020; y <= 2035; y++) {
    safePatterns.add(String(y));
    numbers.add(y);
  }
  // Section numbers, list numbers
  for (let i = 1; i <= 20; i++) {
    numbers.add(i);
  }
  // Common percentages that are definitional
  numbers.add(100);
  numbers.add(50);
  numbers.add(0);

  return { numbers, safePatterns };
}

/**
 * Check if a number is in the trusted pool (with tolerance).
 */
function isNumberTrusted(n: number, pool: TrustedNumberPool, tolerance = 0.05): boolean {
  if (pool.numbers.has(n)) return true;
  if (pool.numbers.has(Math.round(n))) return true;

  // Check with tolerance (5%)
  for (const trusted of pool.numbers) {
    if (trusted === 0) continue;
    if (Math.abs(n - trusted) / Math.abs(trusted) < tolerance) return true;
  }

  return false;
}

type UnverifiedClaim = {
  sentence: string;
  numbers: number[];
  startIndex: number;
};

/**
 * Find sentences containing unverified numbers.
 */
export function findUnverifiedClaims(text: string, pool: TrustedNumberPool): UnverifiedClaim[] {
  const claims: UnverifiedClaim[] = [];

  // Split into sentences (Korean + English)
  const sentences = text.split(/(?<=[.!?\n])\s+|(?<=다[.]\s)|(?<=요[.]\s)|(?<=함[.]\s)|(?<=음[.]\s)/);

  let offset = 0;
  for (const sentence of sentences) {
    const trimmed = sentence.trim();
    if (!trimmed || trimmed.length < 10) {
      offset += sentence.length;
      continue;
    }

    // Skip table headers, markdown formatting
    if (trimmed.startsWith("|") || trimmed.startsWith("#") || trimmed.startsWith("-") && trimmed.length < 30) {
      offset += sentence.length;
      continue;
    }

    const numsInSentence = extractNumbersFromText(trimmed);
    const unverified: number[] = [];

    for (const n of numsInSentence) {
      // Skip small numbers (likely list items, sections)
      if (n <= 20 && Number.isInteger(n)) continue;
      // Skip years
      if (n >= 2020 && n <= 2035) continue;
      // Skip percentages that are round (0%, 50%, 100%)
      if (n === 0 || n === 50 || n === 100) continue;

      if (!isNumberTrusted(n, pool)) {
        unverified.push(n);
      }
    }

    if (unverified.length > 0) {
      claims.push({
        sentence: trimmed,
        numbers: unverified,
        startIndex: offset,
      });
    }

    offset += sentence.length;
  }

  return claims;
}

/**
 * Annotate unverified claims in the response text.
 * Adds [확인 필요] tags inline.
 */
export function annotateUnverifiedClaims(text: string, pool: TrustedNumberPool): {
  annotated: string;
  claimCount: number;
} {
  const claims = findUnverifiedClaims(text, pool);
  if (claims.length === 0) return { annotated: text, claimCount: 0 };

  let result = text;
  let addedLength = 0;
  const tag = " [확인 필요]";

  // Process from end to start to preserve indices
  const sorted = [...claims].sort((a, b) => b.startIndex - a.startIndex);

  for (const claim of sorted) {
    // Find the sentence in the current result text
    const idx = result.indexOf(claim.sentence);
    if (idx === -1) continue;

    // Check if already tagged (in the sentence itself or immediately after)
    if (claim.sentence.includes("[확인 필요]")) continue;
    const after = result.slice(idx + claim.sentence.length, idx + claim.sentence.length + 20);
    if (after.includes("[확인 필요]")) continue;

    // Find end of sentence and insert tag
    const endIdx = idx + claim.sentence.length;
    // Insert before the period/newline if present
    const lastChar = claim.sentence[claim.sentence.length - 1];
    if (lastChar === "." || lastChar === "다" || lastChar === "요" || lastChar === "함") {
      result = result.slice(0, endIdx) + tag + result.slice(endIdx);
    } else {
      result = result.slice(0, endIdx) + tag + result.slice(endIdx);
    }
  }

  return { annotated: result, claimCount: claims.length };
}
