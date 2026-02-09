export type CompanySummary = {
  companyId: string;
  name: string;
  investedAt?: string; // ISO date (YYYY-MM-DD recommended)
  stage?: string;
  investmentType?: string;
  category?: string;
  categories?: string[];
  investedAmount?: number;
  returnedPrincipal?: number;
  returnedProfit?: number;
  nav?: number;
  multiple?: number;
};

export type CompanyDetail = CompanySummary & {
  products?: string;
  location?: string;
  foundedAt?: string;
  ceo?: string;
  contact?: string;
  investmentPoint?: string;
  exitPlan?: string;
  exitExpectation?: string;
};

