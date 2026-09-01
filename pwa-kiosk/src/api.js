const params = new URLSearchParams(window.location.search);
const queryApi = params.get("api");
if (queryApi) localStorage.setItem("attendxsuite_api", queryApi.replace(/\/$/, ""));

export const API_BASE =
  localStorage.getItem("attendxsuite_api") ||
  import.meta.env.VITE_API_URL ||
  (["localhost", "127.0.0.1"].includes(window.location.hostname) || window.location.hostname.startsWith("192.168."))
    ? `${window.location.protocol}//${window.location.hostname}:8060`
    : "";

export const request = async (path, { token, ...options } = {}) => {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });
  const body = await response.json().catch(() => ({}));
  const detail = Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join(", ") : body.detail;
  if (!response.ok) throw new Error(detail || body.message || `Request failed: ${response.status}`);
  return body;
};
