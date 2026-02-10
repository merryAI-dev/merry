import type { FundDetail, FundSnapshot, FundSummary } from "@/lib/funds";
import type { CompanyDetail, CompanySummary } from "@/lib/companies";

type AirtableRecord = {
  id: string;
  createdTime?: string;
  fields: Record<string, unknown>;
};

type AirtableListResponse = {
  records: AirtableRecord[];
  offset?: string;
};

type AirtableMetaField = {
  id: string;
  name: string;
  type?: string;
};

type AirtableMetaTable = {
  id: string;
  name: string;
  primaryFieldId?: string;
  fields?: AirtableMetaField[];
};

type AirtableMetaTablesResponse = {
  tables?: AirtableMetaTable[];
};

export type AirtableConfig = {
  token: string;
  baseId: string;
  fundsTable: string;
  fundsView?: string;
  companiesTable?: string;
  snapshotsTable?: string;
  snapshotsView?: string;
  snapshotFundLinkField: string;
  snapshotDateField: string;
};

function getEnv(name: string): string | undefined {
  const v = process.env[name];
  if (!v) return undefined;
  const trimmed = v.trim();
  return trimmed ? trimmed : undefined;
}

export function getAirtableConfig(): AirtableConfig | null {
  const token = getEnv("AIRTABLE_API_TOKEN") ?? getEnv("AIRTABLE_API_KEY");
  const baseId = getEnv("AIRTABLE_BASE_ID");
  if (!token || !baseId) return null;

  // Support both the new canonical env name and legacy variants.
  // Prefer table ID over name for stability when Airtable table names change.
  const fundsTableId = getEnv("AIRTABLE_FUND_TABLE_ID");
  const fundsTableName = getEnv("AIRTABLE_FUND_TABLE_NAME");
  const fundsTableLegacy = getEnv("AIRTABLE_FUNDS_TABLE");
  let fundsTable = fundsTableId ?? fundsTableName ?? fundsTableLegacy ?? "Funds";
  const fundsView = getEnv("AIRTABLE_FUNDS_VIEW");

  const companiesTable =
    getEnv("AIRTABLE_COMPANIES_TABLE_ID") ??
    getEnv("AIRTABLE_COMPANY_TABLE_ID") ??
    getEnv("AIRTABLE_COMPANIES_TABLE_NAME") ??
    getEnv("AIRTABLE_COMPANY_TABLE_NAME") ??
    getEnv("AIRTABLE_TABLE_NAME") ??
    getEnv("AIRTABLE_TABLE_ID");

  // Common misconfiguration: set fund table ID to the company table ID.
  // If we can detect this, fall back to the fund table *name* (if provided).
  const companiesTableIdEnv =
    getEnv("AIRTABLE_COMPANIES_TABLE_ID") ??
    getEnv("AIRTABLE_COMPANY_TABLE_ID") ??
    getEnv("AIRTABLE_TABLE_ID");
  const fundsTableFallback = fundsTableName ?? fundsTableLegacy;
  const looksMisconfigured =
    Boolean(fundsTableFallback) &&
    ((fundsTableId && companiesTableIdEnv && fundsTableId === companiesTableIdEnv) ||
      (companiesTable && fundsTable === companiesTable));
  if (looksMisconfigured && fundsTableFallback && fundsTableFallback !== fundsTable) {
    fundsTable = fundsTableFallback;
  }

  const snapshotsTable = getEnv("AIRTABLE_SNAPSHOTS_TABLE") ?? "Fund Snapshots";
  const snapshotsView = getEnv("AIRTABLE_SNAPSHOTS_VIEW");
  const snapshotFundLinkField = getEnv("AIRTABLE_SNAPSHOT_FUND_LINK_FIELD") ?? "Fund";
  const snapshotDateField = getEnv("AIRTABLE_SNAPSHOT_DATE_FIELD") ?? "Date";

  // Allow disabling snapshots entirely.
  const disableSnapshots = (getEnv("AIRTABLE_DISABLE_SNAPSHOTS") ?? "").toLowerCase() === "1";

  return {
    token,
    baseId,
    fundsTable,
    fundsView,
    companiesTable,
    snapshotsTable: disableSnapshots ? undefined : snapshotsTable,
    snapshotsView,
    snapshotFundLinkField,
    snapshotDateField,
  };
}

function toNumber(v: unknown): number | undefined {
  if (typeof v === "number") return Number.isFinite(v) ? v : undefined;
  if (typeof v === "string") {
    const raw = v.trim();
    if (!raw) return undefined;
    const cleaned = raw
      .replaceAll(",", "")
      .replaceAll("$", "")
      .replaceAll("₩", "")
      .replaceAll("%", "")
      .replaceAll("원", "")
      .trim();
    if (!cleaned) return undefined;
    const n = Number(cleaned);
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
}

function toString(v: unknown): string | undefined {
  if (typeof v === "string") {
    const s = v.trim();
    return s ? s : undefined;
  }
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : undefined;
  if (Array.isArray(v)) {
    const parts = v
      .map((x) => {
        if (typeof x === "string") return x.trim();
        if (typeof x === "number") return Number.isFinite(x) ? String(x) : "";
        return "";
      })
      .filter(Boolean);
    return parts.length ? parts.join(", ") : undefined;
  }
  return undefined;
}

function toStringArray(v: unknown): string[] {
  if (Array.isArray(v)) {
    return v.map((x) => (typeof x === "string" ? x.trim() : "")).filter(Boolean);
  }
  if (typeof v === "string") {
    const s = v.trim();
    return s ? [s] : [];
  }
  return [];
}

const normalizedFieldKeyCache = new WeakMap<object, Map<string, string>>();

function normalizeFieldKey(key: string): string {
  // Airtable field names often include spaces/newlines/parentheses.
  // Normalize both candidates and actual keys so mapping is resilient.
  return key.toLowerCase().replace(/[^0-9a-zA-Z가-힣]+/g, "");
}

function getNormalizedFieldIndex(fields: Record<string, unknown>): Map<string, string> {
  const cached = normalizedFieldKeyCache.get(fields);
  if (cached) return cached;

  const idx = new Map<string, string>();
  for (const k of Object.keys(fields)) {
    const norm = normalizeFieldKey(k);
    if (!norm || idx.has(norm)) continue;
    idx.set(norm, k);
  }

  normalizedFieldKeyCache.set(fields, idx);
  return idx;
}

function pickField(fields: Record<string, unknown>, candidates: string[]): unknown {
  for (const k of candidates) {
    if (k in fields) return fields[k];
  }

  const idx = getNormalizedFieldIndex(fields);
  for (const c of candidates) {
    const norm = normalizeFieldKey(c);
    if (!norm) continue;
    const actual = idx.get(norm);
    if (actual && actual in fields) return fields[actual];
  }

  return undefined;
}

function pickString(fields: Record<string, unknown>, candidates: string[]): string | undefined {
  return toString(pickField(fields, candidates));
}

function pickNumber(fields: Record<string, unknown>, candidates: string[]): number | undefined {
  return toNumber(pickField(fields, candidates));
}

function pickStringArray(fields: Record<string, unknown>, candidates: string[]): string[] {
  return toStringArray(pickField(fields, candidates));
}

const airtableMetaTablesCache = new Map<string, { ts: number; tables: AirtableMetaTable[] }>();

async function getAirtableMetaTables(cfg: AirtableConfig): Promise<AirtableMetaTable[]> {
  const cached = airtableMetaTablesCache.get(cfg.baseId);
  const ttlMs = 10 * 60 * 1000;
  if (cached && Date.now() - cached.ts < ttlMs) return cached.tables;

  const url = `https://api.airtable.com/v0/meta/bases/${encodeURIComponent(cfg.baseId)}/tables`;
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        authorization: `Bearer ${cfg.token}`,
        "content-type": "application/json",
      },
      cache: "no-store",
    });
    const json = (await res.json().catch(() => ({}))) as AirtableMetaTablesResponse;
    if (!res.ok) return [];
    const tables = Array.isArray(json.tables) ? json.tables : [];
    airtableMetaTablesCache.set(cfg.baseId, { ts: Date.now(), tables });
    return tables;
  } catch {
    return [];
  }
}

async function getAirtableMetaTable(cfg: AirtableConfig, table: string): Promise<AirtableMetaTable | null> {
  const tables = await getAirtableMetaTables(cfg);
  if (!tables.length) return null;
  return tables.find((t) => t.id === table || t.name === table) ?? null;
}

async function getAirtablePrimaryFieldName(cfg: AirtableConfig, table: string): Promise<string | null> {
  const meta = await getAirtableMetaTable(cfg, table);
  if (!meta || !meta.primaryFieldId || !Array.isArray(meta.fields)) return null;
  const pf = meta.fields.find((f) => f.id === meta.primaryFieldId);
  return pf?.name ?? null;
}

function pickLikelyFundLinkField(meta: AirtableMetaTable): string | null {
  const fields = Array.isArray(meta.fields) ? meta.fields : [];
  if (!fields.length) return null;

  let best: { score: number; name: string } | null = null;
  for (const f of fields) {
    const key = normalizeFieldKey(f.name || "");
    if (!key) continue;

    let score = 0;
    const t = (f.type || "").toLowerCase();
    if (t.includes("recordlink")) score += 10;
    if (key.includes("fund")) score += 18;
    if (key.includes("portfolio")) score += 14;
    if (key.includes("펀드")) score += 22;
    if (key.includes("조합")) score += 20;
    if (key.includes("투자조합")) score += 22;
    if (key.includes("id") || key.includes("code") || key.includes("코드")) score -= 12;
    if (key.includes("url")) score -= 8;

    if (score <= 0) continue;
    if (!best || score > best.score) best = { score, name: f.name };
  }
  return best?.name ?? null;
}

function toIsoDate(v: unknown): string | undefined {
  if (!v) return undefined;
  if (typeof v === "string") {
    const s = v.trim();
    if (!s) return undefined;
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return s;
    // Prefer YYYY-MM-DD for charts.
    return d.toISOString().slice(0, 10);
  }
  if (v instanceof Date && !Number.isNaN(v.getTime())) return v.toISOString().slice(0, 10);
  return undefined;
}

function yearFromDateLike(v: unknown): string | undefined {
  const iso = toIsoDate(v);
  if (!iso) return undefined;
  const m = iso.match(/^(\d{4})/);
  return m ? m[1] : undefined;
}

function guessDisplayNameFromFields(fields: Record<string, unknown>): string | undefined {
  // Airtable field names vary wildly (newlines, parentheses, Korean/English mixes).
  // If canonical candidates don't match, pick the best-looking string field by key hints.
  let best: { score: number; value: string } | null = null;
  for (const [rawKey, rawValue] of Object.entries(fields)) {
    const value = toString(rawValue);
    if (!value) continue;

    const key = normalizeFieldKey(rawKey);
    if (!key) continue;

    let score = 0;
    if (key.includes("name")) score += 10;
    if (key.includes("fund")) score += 12;
    if (key.includes("펀드")) score += 14;
    if (key.includes("조합")) score += 14;
    if (key.includes("펀드명")) score += 20;
    if (key.includes("조합명")) score += 20;
    if (key.includes("투자조합")) score += 18;
    if (key.includes("code") || key.includes("코드") || key.includes("id")) score -= 10;
    if (key.includes("url")) score -= 8;
    if (key.includes("관리보수") || key.includes("성과보수")) score -= 14;

    const len = value.length;
    if (len >= 2 && len <= 40) score += 4;
    if (len > 90) score -= 4;

    if (score <= 0) continue;
    if (!best || score > best.score) best = { score, value };
  }
  return best?.value;
}

function guessFallbackLabelFromFields(fields: Record<string, unknown>): string | undefined {
  // Last-resort fallback when we can't identify a name-like field.
  // Prefer a short, human-readable string and avoid obvious IDs/URLs.
  let best: { score: number; value: string } | null = null;
  for (const [rawKey, rawValue] of Object.entries(fields)) {
    const value = toString(rawValue);
    if (!value) continue;

    const trimmed = value.trim();
    if (!trimmed) continue;
    if (/^https?:\/\//i.test(trimmed)) continue;
    if (/^rec[a-zA-Z0-9]{10,20}$/.test(trimmed)) continue;

    const key = normalizeFieldKey(rawKey);
    let score = 0;

    const len = trimmed.length;
    if (len >= 2 && len <= 50) score += 6;
    if (len > 80) score -= 4;

    if (/[가-힣]/.test(trimmed)) score += 3;
    if (/[a-zA-Z]/.test(trimmed)) score += 1;
    if (/^\d+$/.test(trimmed)) score -= 3;
    if (/%/.test(trimmed)) score -= 2;

    if (key.includes("id") || key.includes("code") || key.includes("코드")) score -= 4;
    if (key.includes("url") || key.includes("link")) score -= 3;

    if (score <= 0) continue;
    if (!best || score > best.score) best = { score, value: trimmed };
  }
  return best?.value;
}

function fundFromRecord(rec: AirtableRecord, hints: { primaryNameField?: string | null } = {}): FundSummary {
  const f = rec.fields ?? {};

  const canonicalName = pickString(f, [
    "Name",
    "name",
    "Fund",
    "Fund Name",
    "펀드명",
    "펀드 이름",
    "펀드",
    "조합명",
    "투자 조합명",
    "투자조합명",
    "투자조합",
    "조합",
    "조합(펀드)",
    "펀드명(한글)",
  ]);
  const primaryName = hints.primaryNameField ? pickString(f, [hints.primaryNameField]) : undefined;
  const name =
    canonicalName ??
    primaryName ??
    guessDisplayNameFromFields(f) ??
    guessFallbackLabelFromFields(f) ??
    `Fund ${rec.id.slice(-6)}`;

  const vintage =
    pickString(f, ["Vintage", "vintage", "빈티지", "연도", "결성연도", "결성년도"]) ??
    yearFromDateLike(pickField(f, ["등록일", "결성일", "설립일", "Date"]));
  const currency = pickString(f, ["Currency", "currency", "통화"]);

  const committed = pickNumber(f, ["Committed", "Commitment", "Committed Capital", "약정총액", "약정액", "총약정", "AUM"]);
  const called = pickNumber(f, ["Called", "Paid In", "Called Capital", "총 투자금액(누적)", "총투자금액(누적)", "납입액", "납입", "투입"]);

  const returnedPrincipal = pickNumber(f, ["Return of Capital", "Returned Capital", "회수원금", "회수 원금"]);
  const returnedProfit = pickNumber(f, ["Return", "Profit", "회수수익", "회수 수익"]);
  const distributedRaw = pickNumber(f, ["Distributed", "Returned", "Distributions", "회수액", "분배액", "회수", "분배"]);
  const distributed =
    distributedRaw ??
    (returnedPrincipal != null || returnedProfit != null
      ? (returnedPrincipal ?? 0) + (returnedProfit ?? 0)
      : undefined);

  const nav = pickNumber(f, ["NAV", "Net Asset Value", "미회수투자자산 평가금액", "미회수투자자산", "평가액", "순자산"]);

  const tvpi = pickNumber(f, ["TVPI", "tvpi", "multiple(x) (투자수익배수)", "투자수익배수", "multiple(x)", "multiple"]);
  const dpiRaw = pickNumber(f, ["DPI", "dpi"]);
  const dpi =
    dpiRaw ??
    (typeof distributed === "number" && typeof called === "number" && called > 0
      ? distributed / called
      : undefined);
  const irr = pickNumber(f, ["IRR", "irr"]);

  const updatedAt =
    pickString(f, ["Updated At", "updatedAt", "updated_at", "Last Updated", "수정일", "등록일"]) ??
    rec.createdTime;

  return {
    fundId: rec.id,
    name,
    vintage,
    currency,
    committed,
    called,
    distributed,
    nav,
    tvpi,
    dpi,
    irr,
    updatedAt,
  };
}

function fundDetailFromRecord(rec: AirtableRecord, hints: { primaryNameField?: string | null } = {}): FundDetail {
  const base = fundFromRecord(rec, hints);
  const f = rec.fields ?? {};
  const manager = pickString(f, ["Manager", "GP", "운용사", "매니저", "manager", "대표펀드매니저", "대표 펀드매니저"]);
  const strategy = pickString(f, ["Strategy", "전략", "strategy", "구분"]);
  const notes = pickString(f, ["Notes", "Memo", "메모", "비고", "notes"]);
  const dealCount = pickNumber(f, ["Deal Count", "투자건수", "투자 건수"]);
  const availableCapital = pickNumber(f, ["Available Capital", "투자가용금액", "투자가용 금액"]);
  const myscCommitment = pickNumber(f, ["MYSC 출자약정금액", "MYSC Commitment"]);
  const myscRatio = pickNumber(f, ["MYSC 출자비율", "MYSC Ratio"]);
  const lifeTerm = pickString(f, ["존속기간", "Life", "Life Term"]);
  const investmentTerm = pickString(f, ["투자기간", "Investment Period", "Investment Term"]);
  return { ...base, manager, strategy, notes, dealCount, availableCapital, myscCommitment, myscRatio, lifeTerm, investmentTerm };
}

function companyFromRecord(rec: AirtableRecord, hints: { primaryNameField?: string | null } = {}): CompanySummary {
  const f = rec.fields ?? {};

  const canonicalName = pickString(f, ["Company", "Name", "기업명", "회사명"]);
  const primaryName = hints.primaryNameField ? pickString(f, [hints.primaryNameField]) : undefined;
  const name = canonicalName ?? primaryName ?? guessFallbackLabelFromFields(f) ?? `Company ${rec.id.slice(-6)}`;
  const investedAt = toIsoDate(pickField(f, ["투자일", "Investment Date", "investedAt", "Date"]));
  const stage = pickString(f, ["투자단계", "Stage"]);
  const investmentType = pickString(f, ["투자유형", "Type"]);
  const category = pickString(f, ["카테고리1", "Category", "Sector"]);
  const categories = pickStringArray(f, ["카테고리2", "Categories"]);

  const investedAmount = pickNumber(f, ["투자금액", "Investment Amount", "투자 금액"]);
  const returnedPrincipal = pickNumber(f, ["회수원금", "회수 원금", "Returned Capital"]);
  const returnedProfit = pickNumber(f, ["회수수익", "회수 수익", "Returned Profit"]);
  const nav = pickNumber(f, ["평가금액(미회수투자자산)", "평가금액", "NAV", "Net Asset Value"]);
  const multiple = pickNumber(f, [
    "Multiple(x)\n(투자수익배수)",
    "Multiple(x) (투자수익배수)",
    "multiple(x) (투자수익배수)",
    "TVPI",
    "multiple(x)",
  ]);

  return {
    companyId: rec.id,
    name,
    investedAt,
    stage,
    investmentType,
    category,
    categories: categories.length ? categories : undefined,
    investedAmount,
    returnedPrincipal,
    returnedProfit,
    nav,
    multiple,
  };
}

function companyDetailFromRecord(rec: AirtableRecord, hints: { primaryNameField?: string | null } = {}): CompanyDetail {
  const base = companyFromRecord(rec, hints);
  const f = rec.fields ?? {};

  const products = pickString(f, ["제품/서비스", "Product", "Service", "제품", "서비스"]);
  const location = pickString(f, ["본점 소재지", "Location"]);
  const foundedAt = toIsoDate(pickField(f, ["회사설립일", "설립일", "Founded"]));
  const ceo = pickString(f, ["대표자명", "CEO", "대표자"]);
  const contact = pickString(f, ["연락처", "Contact", "담당자 연락처", "담당자 연락처2"]);
  const investmentPoint = pickString(f, ["투자포인트", "Investment Point"]);
  const exitPlan = pickString(f, ["Exit방안", "Exit Plan"]);
  const exitExpectation = pickString(f, ["Exit예상시기/금액", "Exit 예상시기/금액"]);

  return { ...base, products, location, foundedAt, ceo, contact, investmentPoint, exitPlan, exitExpectation };
}

function snapshotFromRecord(rec: AirtableRecord, dateField: string): FundSnapshot | null {
  const f = rec.fields ?? {};
  const date = toIsoDate(f[dateField] ?? pickField(f, ["Date", "date", "As of", "기준일", "일자"]));
  if (!date) return null;

  const nav = pickNumber(f, ["NAV", "Net Asset Value", "평가액", "순자산"]);
  const called = pickNumber(f, ["Called", "Paid In", "납입액", "납입"]);
  const distributed = pickNumber(f, ["Distributed", "Returned", "회수액", "분배액", "회수", "분배"]);
  const tvpi = pickNumber(f, ["TVPI", "tvpi"]);
  const dpi = pickNumber(f, ["DPI", "dpi"]);
  const irr = pickNumber(f, ["IRR", "irr"]);

  return { date, nav, called, distributed, tvpi, dpi, irr };
}

async function airtableGetJson<T>(cfg: AirtableConfig, path: string, params?: URLSearchParams): Promise<T> {
  const qs = params && params.toString() ? `?${params.toString()}` : "";
  const url = `https://api.airtable.com/v0/${encodeURIComponent(cfg.baseId)}/${path}${qs}`;

  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 12_000);
  try {
    let res: Response;
    try {
      res = await fetch(url, {
        method: "GET",
        headers: {
          authorization: `Bearer ${cfg.token}`,
          "content-type": "application/json",
        },
        cache: "no-store",
        signal: controller.signal,
      });
    } catch (err) {
      const name = err && typeof err === "object" && "name" in err ? String((err as any).name) : "";
      if (name === "AbortError") throw new Error("AIRTABLE_TIMEOUT");
      throw err;
    }

    const json = (await res.json().catch(() => ({}))) as unknown;
    if (!res.ok) {
      const errorRaw =
        json && typeof json === "object" && "error" in (json as Record<string, unknown>)
          ? (json as Record<string, unknown>)["error"]
          : undefined;

      // Airtable error format is typically { error: { type, message } }.
      let code = "";
      if (typeof errorRaw === "string") code = errorRaw;
      else if (errorRaw && typeof errorRaw === "object") {
        const type = (errorRaw as Record<string, unknown>)["type"];
        if (typeof type === "string" && type.trim()) code = type.trim();
      }

      if (!code) {
        if (res.status === 401 || res.status === 403) code = "UNAUTHORIZED";
        else if (res.status === 404) code = "NOT_FOUND";
        else if (res.status === 429) code = "RATE_LIMITED";
        else code = `HTTP_${res.status}`;
      }

      throw new Error(`AIRTABLE_${code}`);
    }

    return json as T;
  } finally {
    clearTimeout(t);
  }
}

async function listAllRecords(cfg: AirtableConfig, table: string, opts: { view?: string; max?: number; sort?: { field: string; direction?: "asc" | "desc" }; filterByFormula?: string } = {}) {
  const records: AirtableRecord[] = [];
  let offset: string | undefined = undefined;
  const max = Math.max(1, Math.min(opts.max ?? 200, 2000));

  for (let page = 0; page < 20; page += 1) {
    const params = new URLSearchParams();
    params.set("pageSize", "100");
    if (opts.view) params.set("view", opts.view);
    if (offset) params.set("offset", offset);
    if (opts.filterByFormula) params.set("filterByFormula", opts.filterByFormula);
    if (opts.sort?.field) {
      params.set("sort[0][field]", opts.sort.field);
      params.set("sort[0][direction]", opts.sort.direction ?? "asc");
    }

    const json = await airtableGetJson<AirtableListResponse>(cfg, encodeURIComponent(table), params);
    records.push(...(json.records ?? []));
    if (!json.offset) break;
    offset = json.offset;
    if (records.length >= max) break;
  }

  return records.slice(0, max);
}

function orderedUniqueIds(ids: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of ids) {
    const id = raw.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(id);
  }
  return out;
}

async function listRecordsByIds(cfg: AirtableConfig, table: string, recordIds: string[]): Promise<AirtableRecord[]> {
  const ids = orderedUniqueIds(recordIds);
  if (!ids.length) return [];

  const all: AirtableRecord[] = [];
  for (let i = 0; i < ids.length; i += 25) {
    const batch = ids.slice(i, i + 25);
    const parts = batch.map((id) => `RECORD_ID()='${id}'`);
    const formula = parts.length === 1 ? parts[0] : `OR(${parts.join(",")})`;
    const recs = await listAllRecords(cfg, table, { max: batch.length + 10, filterByFormula: formula });
    all.push(...recs);
  }

  const byId = new Map(all.map((r) => [r.id, r]));
  return ids.map((id) => byId.get(id)).filter(Boolean) as AirtableRecord[];
}

export async function listFunds(cfg: AirtableConfig): Promise<FundSummary[]> {
  const primaryNameField = await getAirtablePrimaryFieldName(cfg, cfg.fundsTable);
  const recs = await listAllRecords(cfg, cfg.fundsTable, { view: cfg.fundsView, max: 300 });
  return recs.map((r) => fundFromRecord(r, { primaryNameField }));
}

export async function getFundDetail(cfg: AirtableConfig, fundId: string): Promise<{ fund: FundDetail; snapshots: FundSnapshot[]; companies: CompanySummary[]; warnings: string[] }> {
  const warnings: string[] = [];

  const fundPrimaryNameField = await getAirtablePrimaryFieldName(cfg, cfg.fundsTable);
  const companyPrimaryNameField = cfg.companiesTable ? await getAirtablePrimaryFieldName(cfg, cfg.companiesTable) : null;

  const fundRec = await airtableGetJson<AirtableRecord>(
    cfg,
    `${encodeURIComponent(cfg.fundsTable)}/${encodeURIComponent(fundId)}`,
  );
  const fund = fundDetailFromRecord(fundRec, { primaryNameField: fundPrimaryNameField });

  let companies: CompanySummary[] = [];
  const companyIds = pickStringArray(fundRec.fields ?? {}, [
    "투자기업",
    "투자 기업",
    "투자기업목록",
    "투자기업 목록",
    "투자기업리스트",
    "투자기업 리스트",
    "포트폴리오",
    "portfolio",
    "Portfolio",
    "Companies",
  ]);
  if (companyIds.length && cfg.companiesTable) {
    try {
      const recs = await listRecordsByIds(cfg, cfg.companiesTable, companyIds);
      companies = recs.map((r) => companyFromRecord(r, { primaryNameField: companyPrimaryNameField }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "companies_failed";
      warnings.push(`companies_unavailable:${msg}`);
      companies = [];
    }
  } else if (!companyIds.length && cfg.companiesTable) {
    // Reverse lookup (common Airtable schema): companies table holds the fund link, not vice versa.
    try {
      const meta = await getAirtableMetaTable(cfg, cfg.companiesTable);
      const linkField = meta ? pickLikelyFundLinkField(meta) : null;
      if (linkField) {
        const formula = `FIND("${fundId}", ARRAYJOIN({${linkField}}))`;
        const recs = await listAllRecords(cfg, cfg.companiesTable, { max: 600, filterByFormula: formula });
        companies = recs.map((r) => companyFromRecord(r, { primaryNameField: companyPrimaryNameField }));
        warnings.push("companies_reverse_lookup");
      } else {
        warnings.push("companies_link_field_not_found");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "companies_reverse_failed";
      warnings.push(`companies_reverse_failed:${msg}`);
      companies = [];
    }
  } else if (companyIds.length && !cfg.companiesTable) {
    warnings.push("companies_not_configured");
  }

  let snapshots: FundSnapshot[] = [];
  if (cfg.snapshotsTable) {
    try {
      const linkField = cfg.snapshotFundLinkField;
      const formula = `FIND("${fundId}", ARRAYJOIN({${linkField}}))`;
      const recs = await listAllRecords(cfg, cfg.snapshotsTable, {
        view: cfg.snapshotsView,
        max: 600,
        sort: { field: cfg.snapshotDateField, direction: "asc" },
        filterByFormula: formula,
      });
      snapshots = recs
        .map((r) => snapshotFromRecord(r, cfg.snapshotDateField))
        .filter(Boolean) as FundSnapshot[];
    } catch (err) {
      const msg = err instanceof Error ? err.message : "snapshots_failed";
      warnings.push(`snapshots_unavailable:${msg}`);
      snapshots = [];
    }
  } else {
    warnings.push("snapshots_disabled");
  }

  return { fund, snapshots, companies, warnings };
}

export async function getCompanyDetail(cfg: AirtableConfig, companyId: string): Promise<CompanyDetail> {
  if (!cfg.companiesTable) {
    throw new Error("AIRTABLE_COMPANIES_NOT_CONFIGURED");
  }
  const primaryNameField = await getAirtablePrimaryFieldName(cfg, cfg.companiesTable);
  const rec = await airtableGetJson<AirtableRecord>(
    cfg,
    `${encodeURIComponent(cfg.companiesTable)}/${encodeURIComponent(companyId)}`,
  );
  return companyDetailFromRecord(rec, { primaryNameField });
}
