export type DiagnosisSessionStatus = "uploaded" | "processing" | "ready" | "failed";

export type DiagnosisRunStatus = "queued" | "running" | "succeeded" | "failed";

export type DiagnosisEventType =
  | "session_created"
  | "upload_recorded"
  | "context_document_added"
  | "run_started"
  | "run_succeeded"
  | "run_failed";

export type DiagnosisDocumentRole = "primary" | "context";

export type DiagnosisSourceFormat = "xlsx" | "xls" | "pdf" | "docx" | "pptx";

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

export type DiagnosisSessionDetail = DiagnosisSessionSummary & {
  uploads: DiagnosisUploadRecord[];
  runs: DiagnosisRunRecord[];
  events: DiagnosisHistoryEvent[];
  contextDocuments: DiagnosisContextDocumentSummary[];
};
