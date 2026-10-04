(function (global) {
    "use strict";

    const routes = Object.freeze({
        "index.html": {access: "public"},
        "books.html": {access: "public"},
        "book-detail.html": {access: "public"},
        "login.html": {access: "guest"},
        "register.html": {access: "guest"},
        "cart.html": {access: "authenticated"},
        "orders.html": {access: "authenticated"},
        "favorites.html": {access: "authenticated"},
        "messages.html": {access: "authenticated"},
        "borrow-tickets.html": {access: "authenticated"},
        "review.html": {access: "authenticated"},
        "my-listings.html": {access: "authenticated"},
        "sell.html": {access: "authenticated"},
        "profile.html": {access: "authenticated"},
        "workspace.html": {access: "authenticated"},
        "admin.html": {access: "role", role: "ADMIN"},
        "notifications.html": {access: "authenticated"},
        "requests.html": {access: "authenticated"},
        "admin/index.html": {access: "role", role: "ADMIN"},
        "admin/users.html": {access: "role", role: "ADMIN"},
        "admin/reports.html": {access: "role", role: "ADMIN"},
    });

    function fileName() {
        return global.location.pathname.split("/").filter(Boolean).join("/") || "index.html";
    }

    function routeFor(path = fileName()) {
        const normalized = String(path).replace(/^\/+|\/+$/g, "");
        if (normalized === "admin") return routes["admin/index.html"];
        return routes[normalized] || {access: "public"};
    }

    function navigate(path) {
        const normalized = String(path);
        const fromAdmin = global.location.pathname.split("/").includes("admin");
        const target = fromAdmin && !normalized.startsWith(".")
            && !normalized.startsWith("/") && !normalized.startsWith("admin/")
            ? `../${normalized}`
            : fromAdmin && !normalized.startsWith(".") && normalized.startsWith("admin/")
                ? `../${normalized}`
                : normalized;
        global.location.assign(target);
    }

    function loginUrl() {
        const current = `${fileName()}${global.location.search}`;
        const fromAdmin = global.location.pathname.split("/").includes("admin");
        return `${fromAdmin ? "../" : ""}login.html?next=${encodeURIComponent(current)}`;
    }

    function redirectAfterLogin(fallback = "books.html") {
        const next = new URLSearchParams(global.location.search).get("next");
        const allowed = Object.keys(routes).concat("admin");
        const requested = next && allowed.includes(next.split("?")[0]) ? next : fallback;
        const fromAdmin = global.location.pathname.split("/").includes("admin");
        const target = fromAdmin && !requested.startsWith("../")
            ? `../${requested}`
            : requested;
        navigate(target);
    }

    global.PassbookRouter = Object.freeze({
        routes,
        fileName,
        routeFor,
        navigate,
        loginUrl,
        redirectAfterLogin,
    });
})(window);
