import { useRef, useCallback } from "react";
import { streamDiagnosis } from "@/services/diagnosisApi";
import { useDiagnosisStore } from "@/store/diagnosisStore";
import type { DiagnosisRequest } from "@/types/diagnosis";

/**
 * Hook that manages the full SSE diagnosis lifecycle:
 * - Resets state before each run
 * - Pipes SSE events into the Zustand store
 * - Exposes abort capability
 */
export function useSSEDiagnosis() {
  const abortRef = useRef<AbortController | null>(null);
  const { reset, setPhase, appendToken, setResult, setError, setSessionId } =
    useDiagnosisStore();

  const run = useCallback(
    async (request: DiagnosisRequest) => {
      // Cancel any in-flight request
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      reset();
      setPhase("symptom_parser");

      await streamDiagnosis(
        request,
        {
          onStatus: ({ node, phase }) => {
            if (phase === "start") {
              setPhase(node as Parameters<typeof setPhase>[0]);
            }
          },
          onToken: ({ text }) => appendToken(text),
          onResult: (result) => {
            setSessionId(result.session_id);
            setResult(result);
          },
          onError: ({ message }) => setError(message),
          onDone: () => {
            useDiagnosisStore.getState().phase !== "done" && setPhase("done");
          },
        },
        abortRef.current.signal,
      );
    },
    [reset, setPhase, appendToken, setResult, setError, setSessionId],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    setPhase("idle");
  }, [setPhase]);

  return { run, abort };
}
