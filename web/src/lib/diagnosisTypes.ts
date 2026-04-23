export type DiagnosisSessionStatus = "uploaded" | "processing" | "ready" | "failed";

export type DiagnosisRunStatus = "queued" | "running" | "succeeded" | "failed";

export type DiagnosisEventType =
  | "session_created"
  | "upload_recorded"
  | "context_document_added"
  | "conversation_started"
  | "artifact_generated"
  | "run_started"
  | "run_succeeded"
  | "run_failed";

export type DiagnosisDocumentRole = "primary" | "context";

export type DiagnosisSourceFormat = "xlsx" | "xls" | "pdf" | "docx" | "pptx";

export type DiagnosisConversationStatus =
  | "awaiting_user"
  | "thinking"
  | "generating_report"
  | "failed";

export type DiagnosisSessionSummary = {
  sessionId: string;
  title: string;
  status: DiagnosisSessionStatus;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  originalFileName?: string;
  latestRunId: string | null;
  legacyJobId: string | null;
  latestArtifactCount: number;
};

export type DiagnosisUploadRecord = {
  uploadId: string;
  sessionId: string;
  fileId: string;
  originalName: string;
  contentType: string;
  sizeBytes?: number;
  s3Bucket: string;
  s3Key: string;
  createdAt: string;
  uploadedAt?: string;
};

export type DiagnosisRunRecord = {
  runId: string;
  sessionId: string;
  legacyJobId: string;
  status: DiagnosisRunStatus;
  createdAt: string;
  updatedAt: string;
  error?: string;
};

export type DiagnosisHistoryEvent = {
  eventId: string;
  sessionId: string;
  sessionTitle?: string;
  type: DiagnosisEventType;
  actor: string;
  createdAt: string;
  description: string;
  legacyJobId?: string;
};

export type DiagnosisMessageRole = "user" | "assistant" | "system";

export type DiagnosisMessageRecord = {
  messageId: string;
  sessionId: string;
  role: DiagnosisMessageRole;
  content: string;
  createdAt: string;
};

export type DiagnosisArtifactRecord = {
  artifactId: string;
  sessionId: string;
  label: string;
  contentType: string;
  createdAt: string;
  s3Bucket: string;
  s3Key: string;
  sizeBytes?: number;
};

export type DiagnosisNormalizedDocument = {
  role: DiagnosisDocumentRole;
  sourceFormat: DiagnosisSourceFormat;
  markdown: string;
  plainText: string;
  warnings: string[];
  metadata: Record<string, unknown>;
};

export type DiagnosisContextDocumentSummary = {
  documentId: string;
  sessionId: string;
  fileId: string;
  originalName: string;
  contentType: string;
  role: DiagnosisDocumentRole;
  sourceFormat: DiagnosisSourceFormat;
  previewText: string;
  createdAt: string;
  createdBy: string;
  warningCount: number;
  markdownChunkCount: number;
  plainTextChunkCount: number;
  metadata: Record<string, unknown>;
};

export type DiagnosisContextDocumentContent = {
  documentId: string;
  markdown: string;
  plainText: string;
};

export type DiagnosisAnalysisScoreCard = {
  category: string;
  score?: number | null;
  yesRatePct?: number | null;
  weight?: number | null;
  yes?: number;
  no?: number;
  total?: number;
};

export type DiagnosisAnalysisGap = {
  module?: string;
  question?: string;
  detail?: string;
};

export type DiagnosisAnalysisSummary = {
  companyName?: string;
  sheets: string[];
  gapCount: number;
  scoreCards: DiagnosisAnalysisScoreCard[];
  sampleGaps: DiagnosisAnalysisGap[];
};

export type DiagnosisSourceFile = {
  fileId: string;
  originalName: string;
};

export type DiagnosisConversationState = {
  status: DiagnosisConversationStatus;
  canGenerateReport: boolean;
  sourceFile?: DiagnosisSourceFile;
  analysisSummary?: DiagnosisAnalysisSummary | null;
};

export type DiagnosisSessionDetail = DiagnosisSessionSummary & {
  uploads: DiagnosisUploadRecord[];
  runs: DiagnosisRunRecord[];
  events: DiagnosisHistoryEvent[];
  contextDocuments: DiagnosisContextDocumentSummary[];
  messages: DiagnosisMessageRecord[];
  artifacts: DiagnosisArtifactRecord[];
  conversationState: DiagnosisConversationState | null;
};
