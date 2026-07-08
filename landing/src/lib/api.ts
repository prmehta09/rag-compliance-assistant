/**
 * Talks to the FastAPI compliance-audit backend (see ../../../api.py).
 *
 * The audit endpoint streams Server-Sent Events over a POST response, which
 * the browser's built-in EventSource can't do (it's GET-only). So instead we
 * open the request with fetch(), read the response body as a byte stream,
 * and parse the "event: ...\ndata: ...\n\n" frames by hand.
 */

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type FindingStatus = "Addressed" | "Partially Addressed" | "Gap" | "Not Applicable";

export interface Verification {
  verdict: string;
  confidence: string;
  reason: string;
}

export interface Finding {
  checkpoint: string;
  status: FindingStatus;
  citation: string;
  explanation: string;
  verification: Verification | null;
  flagged: boolean;
}

export async function getDocuments(): Promise<string[]> {
  const response = await fetch(`${API_URL}/documents`);
  if (!response.ok) {
    throw new Error(`Failed to load documents (HTTP ${response.status}).`);
  }
  return response.json();
}

interface AuditStreamOptions {
  verify?: boolean;
  rerank?: boolean;
}

interface AuditStreamCallbacks {
  onStart?: (payload: { total: number; document: string }) => void;
  onFinding?: (finding: Finding) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
}

interface AuditStreamHandle {
  cancel: () => void;
}

interface SSEFrame {
  event: string;
  data: string;
}

/** Parses one raw "event: x\ndata: y" block (no trailing blank line) into its parts. */
function parseSSEFrame(raw: string): SSEFrame | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // Response body wasn't JSON - fall through to the generic message.
  }
  return `Audit request failed (HTTP ${response.status}).`;
}

/**
 * Starts a streaming audit and fires the given callbacks as events arrive.
 * Returns a handle whose cancel() aborts the underlying fetch - call it if
 * the component unmounts or the user navigates away mid-audit.
 */
export function auditStream(
  document: string,
  options: AuditStreamOptions,
  callbacks: AuditStreamCallbacks,
): AuditStreamHandle {
  const controller = new AbortController();
  const { verify = true, rerank = true } = options;

  function dispatch(frame: SSEFrame) {
    const payload = JSON.parse(frame.data);
    if (frame.event === "start") callbacks.onStart?.(payload);
    else if (frame.event === "finding") callbacks.onFinding?.(payload as Finding);
    else if (frame.event === "done") callbacks.onDone?.();
    else if (frame.event === "error") callbacks.onError?.(payload.message ?? "Audit failed.");
  }

  (async () => {
    let response: Response;
    try {
      response = await fetch(`${API_URL}/audit/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document, verify, rerank }),
        signal: controller.signal,
      });
    } catch {
      if (!controller.signal.aborted) {
        callbacks.onError?.(`Couldn't reach the audit server at ${API_URL}. Is it running?`);
      }
      return;
    }

    if (!response.ok || !response.body) {
      callbacks.onError?.(await readErrorDetail(response));
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let boundary = buffer.indexOf("\n\n");
        while (boundary !== -1) {
          const rawFrame = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const frame = parseSSEFrame(rawFrame);
          if (frame) dispatch(frame);
          boundary = buffer.indexOf("\n\n");
        }
      }
    } catch {
      if (!controller.signal.aborted) {
        callbacks.onError?.("Lost connection to the audit stream partway through.");
      }
    }
  })();

  return { cancel: () => controller.abort() };
}
