import { getJob } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";
// Prevent Next.js from buffering the response.
export const dynamic = "force-dynamic";

const POLL_MS = 2000;
const HEARTBEAT_MS = 15_000; // Send heartbeat every 15s to keep connection alive.
const MAX_DURATION_MS = 10 * 60 * 1000; // 10 minutes max SSE connection.

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  let ws: { teamId: string };
  try {
    ws = await requireWorkspaceFromCookies();
  } catch {
    return new Response("Unauthorized", { status: 401 });
  }

  const { jobId } = await params;

  const encoder = new TextEncoder();
  const start = Date.now();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (data: unknown) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      };

      const sendHeartbeat = () => {
        // SSE comment line — keeps connection alive through proxies/LBs.
        controller.enqueue(encoder.encode(": heartbeat\n\n"));
      };

      let lastHash = "";
      let lastHeartbeat = Date.now();
      let terminated = false;

      // Send initial heartbeat so client knows connection is established.
      sendHeartbeat();

      while (!terminated && Date.now() - start < MAX_DURATION_MS) {
        try {
          const job = await getJob(ws.teamId, jobId);
          if (!job) {
            send({ error: "NOT_FOUND" });
            break;
          }

          // Build a quick hash to detect any state change.
          const hash = `${job.status}:${job.processedCount ?? 0}:${job.failedCount ?? 0}:${job.fanoutStatus ?? ""}`;
          if (hash !== lastHash) {
            lastHash = hash;
            lastHeartbeat = Date.now();
            send({
              status: job.status,
              fanout: job.fanout ?? false,
              totalTasks: job.totalTasks ?? 0,
              processedCount: job.processedCount ?? 0,
              failedCount: job.failedCount ?? 0,
              fanoutStatus: job.fanoutStatus ?? null,
              artifacts: job.artifacts ?? [],
              metrics: job.metrics ?? {},
              error: job.error ?? null,
            });
          } else if (Date.now() - lastHeartbeat >= HEARTBEAT_MS) {
            // Send keepalive comment when no data changes.
            sendHeartbeat();
            lastHeartbeat = Date.now();
          }

          // Terminal states.
          if (job.status === "succeeded" || job.status === "failed") {
            terminated = true;
            break;
          }

          await new Promise((r) => setTimeout(r, POLL_MS));
        } catch {
          // Connection likely closed by client.
          break;
        }
      }

      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
