import type { LiveRunState } from "../types/mcp";

export function connectSSE(
  onMessage: (msg: LiveRunState) => void
) {
  const interval = setInterval(() => {
    onMessage({
      updated: new Date().toISOString()
    });
  }, 2000);

  return () => clearInterval(interval);
}