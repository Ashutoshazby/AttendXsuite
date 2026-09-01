export const API_BASE = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8070`;

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
