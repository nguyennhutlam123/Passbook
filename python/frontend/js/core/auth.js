(function (global) {
    "use strict";

    const storage = global.PassbookStorage;

    function updateUser(user) {
        storage.setUser(user);
        global.dispatchEvent(new CustomEvent("passbook:user-updated", {detail: user}));
    }

    function setSession(session) {
        storage.setSession(session);
        global.dispatchEvent(new CustomEvent("passbook:login", {detail: session.user}));
    }

    function clearSession(reason = "logout") {
        storage.clearSession();
        global.dispatchEvent(new CustomEvent("passbook:logout", {detail: {reason}}));
    }

    function isDemoMode() {
        const url = new URL(global.location.href);
        const demo = url.searchParams.get("demo") || global.localStorage.getItem("demoProfile");
        return ["1", "true", "yes"].includes(String(demo || "").trim().toLowerCase());
    }

    function demoUser() {
        return {
            id: "demo-profile",
            name: "Nguyễn Lâm",
            email: "lam.passbook@gmail.com",
            university: {name: "HCMUE"},
            is_verified: true,
            role: "USER",
            bio: "Khám phá sách hay, kết nối cộng đồng và quản lý tài khoản một cách tiện lợi.",
        };
    }

    function getCurrentUser() {
        const user = storage.getUser();
        if (user) return user;
        if (isDemoMode()) {
            const demo = demoUser();
            storage.setUser(demo);
            return demo;
        }
        return null;
    }

    function isLoggedIn() {
        if (storage.isAuthenticated()) return true;
        if (isDemoMode()) {
            const demo = demoUser();
            storage.setUser(demo);
            return true;
        }
        return false;
    }

    global.PassbookAuth = Object.freeze({
        getAccessToken: storage.getAccessToken,
        getRefreshToken: storage.getRefreshToken,
        getCurrentUser,
        isLoggedIn,
        setSession,
        updateUser,
        clearSession,
    });
    global.getAccessToken = storage.getAccessToken;
    global.clearAuth = clearSession;
    global.isLoggedIn = isLoggedIn;
})(window);
