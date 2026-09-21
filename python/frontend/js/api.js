const productionApiUrl = "https://passbook-backend-6o0s.onrender.com/api";
const API_BASE_URL = window.PASSBOOK_API_URL || productionApiUrl;

function getAccessToken() {
    return localStorage.getItem("accessToken");
}

function clearAuth() {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("currentUser");
    localStorage.removeItem("isLoggedIn");
}

function formatApiError(payload) {
    if (!payload || typeof payload !== "object") return "";
    if (typeof payload.detail === "string") return payload.detail;
    return Object.entries(payload)
        .map(([field, value]) => {
            const message = Array.isArray(value) ? value.join(" ") : String(value);
            return `${field}: ${message}`;
        })
        .filter(Boolean)
        .join(" ");
}

async function apiRequest(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(`${API_BASE_URL}${path}`, {...options, headers});
    let payload = null;
    try { payload = await response.json(); } catch (_) { payload = null; }
    if (response.status === 401) {
        const hadToken = Boolean(token);
        clearAuth();
        if (hadToken && !options.skipAuth) {
            return apiRequest(path, {...options, skipAuth: true});
        }
    }
    if (!response.ok) {
        const error = new Error(formatApiError(payload) || "Có lỗi xảy ra khi gọi API.");
        error.status = response.status;
        error.payload = payload;
        throw error;
    }
    return payload;
}

const api = {
    get: (path) => apiRequest(path),
    post: (path, body) => apiRequest(path, {method: "POST", body: JSON.stringify(body)}),
    patch: (path, body) => apiRequest(path, {method: "PATCH", body: JSON.stringify(body)}),
    delete: (path) => apiRequest(path, {method: "DELETE"}),
};
