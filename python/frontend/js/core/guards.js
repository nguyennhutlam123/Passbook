(function (global) {
    "use strict";

    function requireAuth() {
        if (global.PassbookAuth.isLoggedIn()) return true;
        global.PassbookRouter.navigate(global.PassbookRouter.loginUrl());
        return false;
    }

    function requireGuest() {
        if (!global.PassbookAuth.isLoggedIn()) return true;
        global.PassbookRouter.navigate("books.html");
        return false;
    }

    function requireRole(role) {
        if (!requireAuth()) return false;
        const user = global.PassbookAuth.getCurrentUser();
        if (String(user?.role || "").toUpperCase() === String(role).toUpperCase()) return true;
        global.PassbookRouter.navigate(user ? "books.html" : global.PassbookRouter.loginUrl());
        return false;
    }

    const currentRoute = global.PassbookRouter.routeFor();
    if (currentRoute.access === "guest") requireGuest();
    else if (currentRoute.access === "authenticated") requireAuth();
    else if (currentRoute.access === "role") requireRole(currentRoute.role);

    global.PassbookGuards = Object.freeze({requireAuth, requireGuest, requireRole});
})(window);
