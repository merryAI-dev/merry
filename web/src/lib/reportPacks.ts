export type FactSource =
  | { kind: "job_artifact"; jobId: string; artifactId: string; fileId?: string }
  | { kind: "pdf_evidence_line"; jobId: string; fileId?: string; page: number; text: string }
  | { kind: "manual"; note?: string };

export type Fact = {
  factId: string; // uuid
  key: string;
  valueType: "number" | "string";
  numberValue?: number;
  stringValue?: string;
  unit?: string; // "KRW", "%", "shares", "x", "year", ...
  asOf?: string; // YYYY-MM-DD
  year?: number;
  source: FactSource;
  confidence?: "high" | "medium" | "low";
};

export type FactPack = {
  factPackId: string; // uuid
  sessionId: string; // report_<slug>
  createdAt: string;
  createdBy: string;
  inputs: { jobIds: string[]; fileIds: string[] };
  facts: Fact[];
  warnings: string[];
};

export type AssumptionEvidenceRef = { factId: string } | { note: string };

export type Assumption = {
  key: string;
  valueType: "number" | "string" | "number_array";
  numberValue?: number;
  stringValue?: string;
  numberArrayValue?: number[];
  unit?: string;
  required: boolean;
  evidence: AssumptionEvidenceRef[];
};

export type Scenario = {
  key: "base" | "bull" | "bear";
  title: string;
  overrides: Array<Omit<Assumption, "required" | "evidence"> & { evidence?: AssumptionEvidenceRef[] }>;
};

export type AssumptionPack = {
  packId: string; // uuid
  sessionId: string;
  companyName: string;
  fundName?: string;
  createdAt: string;
  createdBy: string;
  status: "draft" | "validated" | "locked";
  lineage?: { parentPackId?: string; reason?: "mutation" | "crossover" | "manual" };
  factPackId?: string;
  assumptions: Assumption[];
  scenarios: Scenario[];
};

export type ComputeSnapshot = {
  snapshotId: string;
  sessionId: string;
  packId: string;
  jobId: string;
  createdAt: string;
  createdBy: string;
  derivedSummary?: Record<string, unknown>;
};

export type ValidationStatus = "pass" | "warn" | "fail";

export type CheckResult = {
  check: string;
  status: ValidationStatus;
  message: string;
};

