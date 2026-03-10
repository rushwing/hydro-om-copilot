import type { DiagnosisRequest, SSEStatusPayload, SSETokenPayload, DiagnosisResult, SSEErrorPayload } from "@/types/diagnosis";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface DiagnosisCallbacks {
  onStatus?: (payload: SSEStatusPayload) => void;
  onToken?: (payload: SSETokenPayload) => void;
  onResult?: (payload: DiagnosisResult) => void;
  onError?: (payload: SSEErrorPayload) => void;
  onDone?: () => void;
}

/**
 * Streams a diagnosis request via fetch + ReadableStream (avoids EventSource
 * limitations with POST bodies).
 */
export async function streamDiagnosis(
  request: DiagnosisRequest,
  callbacks: DiagnosisCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/diagnosis/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok || !response.body) {
    callbacks.onError?.({ message: `HTTP ${response.status}: ${response.statusText}` });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      if (!part.trim()) continue;
      const eventMatch = part.match(/^event: (\w+)\ndata: (.+)$/s);
      if (!eventMatch) continue;

      const [, eventType, dataStr] = eventMatch;
      try {
        const data = JSON.parse(dataStr);
        switch (eventType) {
          case "status":
            callbacks.onStatus?.(data as SSEStatusPayload);
            break;
          case "token":
            callbacks.onToken?.(data as SSETokenPayload);
            break;
          case "result":
            callbacks.onResult?.(data as DiagnosisResult);
            break;
          case "error":
            callbacks.onError?.(data as SSEErrorPayload);
            break;
        }
      } catch {
        // Malformed JSON — ignore
      }
    }
  }

  callbacks.onDone?.();
}
