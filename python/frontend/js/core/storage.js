(function (global) {
    "use strict";

    const KEYS = Object.freeze({
        access: "accessToken",
        refresh: "refreshToken",
        user: "currentUser",
        loggedIn: "isLoggedIn",
    });

    function readUser() {
        try {
            const value = global.localStorage.getItem(KEYS.user);
            return value ? JSON.parse(value) : null;
        } catch (_error) {
            global.localStorage.removeItem(KEYS.user);
            return null;
        }
    }

    function setSession(session) {
        if (!session?.access || !session?.refresh || !session?.user) {
            throw new TypeError("A complete Passbook session is required.");
        }
        global.localStorage.setItem(KEYS.access, session.access);
        global.localStorage.setItem(KEYS.refresh, session.refresh);
        global.localStorage.setItem(KEYS.user, JSON.stringify(session.user));
        global.localStorage.setItem(KEYS.loggedIn, "true");
    }

    function updateTokens(tokens) {
        if (tokens?.access) global.localStorage.setItem(KEYS.access, tokens.access);
        if (tokens?.refresh) global.localStorage.setItem(KEYS.refresh, tokens.refresh);
    }

    function setUser(user) {
        if (!user || typeof user !== "object") {
            throw new TypeError("A valid Passbook user is required.");
        }
        global.localStorage.setItem(KEYS.user, JSON.stringify(user));
    }

    function clearSession() {
        Object.values(KEYS).forEach((key) => global.localStorage.removeItem(key));
    }

    global.PassbookStorage = Object.freeze({
        keys: KEYS,
        getAccessToken: () => global.localStorage.getItem(KEYS.access),
        getRefreshToken: () => global.localStorage.getItem(KEYS.refresh),
        getUser: readUser,
        isAuthenticated: () => Boolean(global.localStorage.getItem(KEYS.access)),
        setSession,
        setUser,
        updateTokens,
        clearSession,
    });
})(window);
