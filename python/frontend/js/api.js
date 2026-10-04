(function (global) {
    "use strict";

    const LOCAL_API_URL = "http://127.0.0.1:8000/api";
    const PRODUCTION_API_URL = "https://passbook-backend-6o0s.onrender.com/api";
    const isLocal = ["localhost", "127.0.0.1"].includes(global.location.hostname);
    const API_BASE_URL = (
        global.PASSBOOK_API_URL || (isLocal ? LOCAL_API_URL : PRODUCTION_API_URL)
    ).replace(/\/+$/, "");
    const authPaths = new Set([
        "/auth/login/",
        "/auth/register/",
        "/auth/token/refresh/",
        "/auth/verify-otp/",
        "/auth/resend-otp/",
        "/auth/forgot-password/",
        "/auth/reset-password/",
    ]);
    const timeoutMs = 30000;
    let refreshPromise = null;

    function urlFor(path) {
        if (/^https?:\/\//i.test(path)) return path;
        return `${API_BASE_URL}/${String(path).replace(/^\/+/, "")}`;
    }

    async function parseResponse(response) {
        if (response.status === 204) return null;
        const text = await response.text();
        if (!text) return null;
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("json")) {
            try {
                return JSON.parse(text);
            } catch (_error) {
                throw new global.PassbookErrors.ApiError(
                    "Máy chủ trả về dữ liệu không hợp lệ.",
                    {status: response.status, code: "invalid_response"},
                );
            }
        }
        return text;
    }

    async function rawRequest(url, options = {}) {
        const controller = new AbortController();
        const timeout = global.setTimeout(() => controller.abort(), timeoutMs);
        try {
            return await global.fetch(url, {...options, signal: controller.signal});
        } catch (error) {
            const timedOut = error?.name === "AbortError";
            throw new global.PassbookErrors.ApiError(
                timedOut
                    ? "Yêu cầu mất quá nhiều thời gian."
                    : "Không thể kết nối máy chủ.",
                {status: 0, code: timedOut ? "timeout" : "network_error"},
            );
        } finally {
            global.clearTimeout(timeout);
        }
    }

    async function refreshAccessToken() {
        if (refreshPromise) return refreshPromise;
        const refresh = global.PassbookAuth.getRefreshToken();
        if (!refresh) throw new global.PassbookErrors.ApiError(
            "Không còn phiên đăng nhập hợp lệ.",
            {status: 401, code: "session_expired"},
        );

        refreshPromise = (async () => {
            const response = await rawRequest(urlFor("/auth/token/refresh/"), {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({refresh}),
            });
            const payload = await parseResponse(response);
            if (!response.ok || !payload?.access) {
                throw new global.PassbookErrors.ApiError(
                    global.PassbookErrors.messageFor({
                        status: response.status,
                        payload,
                    }),
                    {status: response.status || 401, payload, code: "refresh_failed"},
                );
            }
            global.PassbookStorage.updateTokens(payload);
            return payload.access;
        })();

        try {
            return await refreshPromise;
        } finally {
            refreshPromise = null;
        }
    }

    function onSessionExpired() {
        global.PassbookAuth.clearSession("refresh_failed");
        const route = global.PassbookRouter.routeFor();
        if (route.access === "authenticated" || route.access === "role") {
            global.PassbookRouter.navigate(global.PassbookRouter.loginUrl());
        }
    }

    async function request(path, options = {}) {
        const url = urlFor(path);
        const method = (options.method || "GET").toUpperCase();
        const body = options.body;
        const requestUrl = new URL(url);
        const apiBaseUrl = new URL(API_BASE_URL);
        const apiBasePath = apiBaseUrl.pathname.replace(/\/+$/, "");
        const isApiRequest = requestUrl.origin === apiBaseUrl.origin
            && requestUrl.pathname.startsWith(`${apiBasePath}/`);
        const headers = new Headers(options.headers || {});
        const isFormData = body instanceof FormData;
        if (body !== undefined && body !== null && !isFormData && !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
        }
        const useAuth = options.auth !== false && isApiRequest;
        const hasAccess = useAuth && Boolean(global.PassbookAuth.getAccessToken());
        if (hasAccess && !headers.has("Authorization")) {
            headers.set("Authorization", `Bearer ${global.PassbookAuth.getAccessToken()}`);
        }
        const init = {...options, method, headers};
        delete init.timeout;
        delete init.auth;
        delete init._retried;
        if (body !== undefined && body !== null && !isFormData && typeof body !== "string") {
            init.body = JSON.stringify(body);
        }

        let response = await rawRequest(url, init);
        const apiPath = isApiRequest
            ? requestUrl.pathname.slice(apiBasePath.length) || "/"
            : "";
        if (
            response.status === 401
            && hasAccess
            && !options._retried
            && !authPaths.has(apiPath)
        ) {
            let access;
            try {
                access = await refreshAccessToken();
            } catch (error) {
                onSessionExpired();
                throw error;
            }
            const retryHeaders = new Headers(headers);
            retryHeaders.set("Authorization", `Bearer ${access}`);
            response = await rawRequest(url, {...init, headers: retryHeaders});
        }

        const payload = await parseResponse(response);
        if (!response.ok) {
            throw new global.PassbookErrors.ApiError(
                global.PassbookErrors.messageFor({status: response.status, payload}),
                {status: response.status, payload, code: "http_error"},
            );
        }
        return payload;
    }

    const api = Object.freeze({
        request,
        get: (path, options = {}) => request(path, {...options, method: "GET"}),
        post: (path, body, options = {}) => request(path, {...options, method: "POST", body}),
        put: (path, body, options = {}) => request(path, {...options, method: "PUT", body}),
        patch: (path, body, options = {}) => request(path, {...options, method: "PATCH", body}),
        delete: (path, options = {}) => request(path, {...options, method: "DELETE"}),
    });

    global.API_BASE_URL = API_BASE_URL;
    global.api = api;
    global.apiRequest = request;
    global.formatApiError = global.PassbookErrors.messageFor;
})(window);
