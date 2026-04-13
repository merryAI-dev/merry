import { DiagnosisSessionDetailPage } from "@/components/diagnosis/DiagnosisSessionDetailPage";

export default async function DiagnosisSessionDetailRoute({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <DiagnosisSessionDetailPage sessionId={sessionId} />;
}
