// Optional frontend helper for the static RV&S dashboard when using the HTTPS gateway.
// Place as frontend/static/rvs-gateway-client.js if you want to call the API directly.

export async function getCurrentUser(apiBase = "") {
  const res = await fetch(`${apiBase}/auth/me`, { credentials: "include" });
  if (!res.ok) return null;
  return res.json();
}

export async function loadRvsDashboard(apiBase = "", query = "Find Liv Projects All My Work") {
  const url = `${apiBase}/api/rvs/dashboard?query=${encodeURIComponent(query)}`;
  const res = await fetch(url, { credentials: "include", headers: { Accept: "application/json" } });
  if (res.status === 401) {
    window.location.href = `${apiBase}/auth/login`;
    return null;
  }
  if (!res.ok) throw new Error(`Dashboard request failed: ${res.status}`);
  return res.json();
}

export async function logout(apiBase = "") {
  await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" });
  window.location.href = `${apiBase}/auth/login`;
}
