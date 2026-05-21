export type MCPRequest = {
  tool: string;
  input: Record<string, unknown>;
};

export async function invokeMCP(request: MCPRequest) {
  const tokenResponse = await fetch(
    `${import.meta.env.VITE_TOKEN_BROKER_URL}/tokens/github-app`,
    {
      method: "POST",
      credentials: "include"
    }
  );

  if (!tokenResponse.ok) {
    throw new Error("Failed to get GitHub App token");
  }

  const { token } = await tokenResponse.json();

  const response = await fetch(
    `https://api.github.com/repos/${import.meta.env.VITE_OWNER}/${import.meta.env.VITE_REPO}/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        event_type: "mcp.invoke",
        client_payload: request
      })
    }
  );

  if (!response.ok) {
    throw new Error("Failed to dispatch MCP request");
  }

  return true;
}

export async function refreshCodebeamerDashboard(query: string) {
  return invokeMCP({
    tool: "cdyp7.cb.dashboard.refresh",
    input: {
      query
    }
  });
}