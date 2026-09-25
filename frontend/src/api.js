// Small fetch wrapper. The web app and the API share one origin in production;
// set VITE_API_URL only if you host them separately.
const BASE = import.meta.env.VITE_API_URL || "";
export const TZ = -new Date().getTimezoneOffset(); // IST = 330

export function getToken() {
  try { return localStorage.getItem("cc_token"); } catch { return null; }
}
export function setToken(t) {
  try { t ? localStorage.setItem("cc_token", t) : localStorage.removeItem("cc_token"); } catch { /* private mode */ }
}

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

const NO_SERVER = "The app can't reach its server. If you are testing on a computer, check that the API window (uvicorn on port 8000) is running.";

// Turn any error response into one plain sentence.
function messageFor(res, data) {
  if (data && typeof data.detail === "string") return data.detail;
  // FastAPI form errors arrive as a list, e.g. [{ loc: ["body", "password"], msg: "..." }]
  if (data && Array.isArray(data.detail) && data.detail.length) {
    const first = data.detail[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : "";
    if (field === "password") return "The password needs at least 6 characters.";
    if (field === "email") return "Check the email address.";
    if (field === "name") return "Write your name.";
    return first.msg || "Some details are missing. Check the form and try again.";
  }
  // No JSON at all: the dev server answered for an API that isn't running, or a proxy failed.
  if ([500, 502, 503, 504].includes(res.status)) return NO_SERVER;
  return "Something went wrong. Try again.";
}

export async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  let res;
  try {
    res = await fetch(BASE + path, { method, headers, body: payload });
  } catch {
    throw new ApiError("No internet connection. Check your connection and try again.", 0);
  }
  if (res.status === 401 && token) { setToken(null); window.dispatchEvent(new Event("cc:logout")); }
  let data = null;
  if (res.headers.get("content-type")?.includes("json")) {
    try { data = await res.json(); } catch { data = null; }
  }
  if (!res.ok) throw new ApiError(messageFor(res, data), res.status);
  return data;
}

export const mediaUrl = (u) => (u ? BASE + u : null);
