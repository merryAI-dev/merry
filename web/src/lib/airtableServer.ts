import type { FundDetail, FundSnapshot, FundSummary } from "@/lib/funds";

type AirtableRecord = {
  id: string;
  createdTime?: string;
  fields: Record<string, unknown>;
};

type AirtableListResponse = {
  records: AirtableRecord[];
  offset?: string;
};

export type AirtableConfig = {
  token: string;
  baseId: string;
  fundsTable: string;
  fundsView?: string;
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

  const fundsTable = getEnv("AIRTABLE_FUNDS_TABLE") ?? "Funds";
  const fundsView = getEnv("AIRTABLE_FUNDS_VIEW");

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
  return undefined;
}

function pickField(fields: Record<string, unknown>, candidates: string[]): unknown {
  for (const k of candidates) {
    if (k in fields) return fields[k];
  }
  return undefined;
}

function pickString(fields: Record<string, unknown>, candidates: string[]): string | undefined {
  return toString(pickField(fields, candidates));
}

function pickNumber(fields: Record<string, unknown>, candidates: string[]): number | undefined {
  return toNumber(pickField(fields, candidates));
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

function fundFromRecord(rec: AirtableRecord): FundSummary {
  const f = rec.fields ?? {};

  const name =
    pickString(f, ["Name", "name", "Fund", "Fund Name", "펀드명", "펀드 이름", "펀드"]) ??
    `Fund ${rec.id.slice(-6)}`;

  const vintage = pickString(f, ["Vintage", "vintage", "빈티지", "연도"]);
  const currency = pickString(f, ["Currency", "currency", "통화"]);

  const committed = pickNumber(f, ["Committed", "Commitment", "Committed Capital", "약정액", "총약정", "AUM"]);
  const called = pickNumber(f, ["Called", "Paid In", "Called Capital", "납입액", "납입", "투입"]);
  const distributed = pickNumber(f, ["Distributed", "Returned", "Distributions", "회수액", "분배액", "회수", "분배"]);
  const nav = pickNumber(f, ["NAV", "Net Asset Value", "평가액", "순자산"]);

  const tvpi = pickNumber(f, ["TVPI", "tvpi"]);
  const dpi = pickNumber(f, ["DPI", "dpi"]);
  const irr = pickNumber(f, ["IRR", "irr"]);

  const updatedAt = pickString(f, ["Updated At", "updatedAt", "updated_at", "Last Updated", "수정일"]) ?? rec.createdTime;

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

function fundDetailFromRecord(rec: AirtableRecord): FundDetail {
  const base = fundFromRecord(rec);
  const f = rec.fields ?? {};
  const manager = pickString(f, ["Manager", "GP", "운용사", "매니저", "manager"]);
  const strategy = pickString(f, ["Strategy", "전략", "strategy"]);
  const notes = pickString(f, ["Notes", "Memo", "메모", "비고", "notes"]);
  return { ...base, manager, strategy, notes };
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
    const res = await fetch(url, {
      method: "GET",
      headers: {
        authorization: `Bearer ${cfg.token}`,
        "content-type": "application/json",
      },
      cache: "no-store",
      signal: controller.signal,
    });
    const json = (await res.json().catch(() => ({}))) as unknown;
    if (!res.ok) {
      const msg =
        json && typeof json === "object" && "error" in (json as Record<string, unknown>)
          ? JSON.stringify((json as Record<string, unknown>)["error"])
          : `HTTP_${res.status}`;
      throw new Error(`AIRTABLE_${msg}`);
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

export async function listFunds(cfg: AirtableConfig): Promise<FundSummary[]> {
  const recs = await listAllRecords(cfg, cfg.fundsTable, { view: cfg.fundsView, max: 300 });
  return recs.map(fundFromRecord);
}

export async function getFundDetail(cfg: AirtableConfig, fundId: string): Promise<{ fund: FundDetail; snapshots: FundSnapshot[]; warnings: string[] }> {
  const warnings: string[] = [];

  const fundRec = await airtableGetJson<AirtableRecord>(
    cfg,
    `${encodeURIComponent(cfg.fundsTable)}/${encodeURIComponent(fundId)}`,
  );
  const fund = fundDetailFromRecord(fundRec);

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

  return { fund, snapshots, warnings };
}

