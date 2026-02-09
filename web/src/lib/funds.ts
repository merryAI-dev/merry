export type FundSummary = {
  fundId: string;
  name: string;
  vintage?: string;
  currency?: string;
  committed?: number;
  called?: number;
  distributed?: number;
  nav?: number;
  tvpi?: number;
  dpi?: number;
  irr?: number;
  updatedAt?: string;
};

export type FundDetail = FundSummary & {
  manager?: string;
  strategy?: string;
  notes?: string;
  dealCount?: number;
  availableCapital?: number;
  myscCommitment?: number;
  myscRatio?: number;
  lifeTerm?: string;
  investmentTerm?: string;
};

export type FundSnapshot = {
  date: string; // ISO string (YYYY-MM-DD recommended)
  nav?: number;
  called?: number;
  distributed?: number;
  tvpi?: number;
  dpi?: number;
  irr?: number;
};
