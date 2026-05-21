import { useEffect, useState } from "react";
import type { LiveRunState } from "../types/mcp";

export function useLiveRunState() {
  const [state, setState] =
    useState<LiveRunState | null>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setState({
        updated: new Date().toISOString()
      });
    }, 2000);

    return () => clearInterval(timer);
  }, []);

  return state;
}