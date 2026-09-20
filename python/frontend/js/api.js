const localApiUrl = "http://127.0.0.1:8000/api";
const productionApiUrl = "https://passbook-backend-6o0s.onrender.com/api";
const isLocalFrontend = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_BASE_URL = window.PASSBOOK_API_URL
    || (isLocalFrontend ? localApiUrl : productionApiUrl);

function getAccessToken() {
    return localStorage.getItem("accessToken");
}

function clearAuth() {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("currentUser");
    localStorage.removeItem("isLoggedIn");
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
        const error = new Error(payload?.detail || "Có lỗi xảy ra khi gọi API.");
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
