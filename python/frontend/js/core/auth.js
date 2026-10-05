(function (global) {
    "use strict";

    const storage = global.PassbookStorage;

    if (global.localStorage.getItem("demoProfile") === "true") {
        storage.clearSession();
        global.localStorage.removeItem("demoProfile");
    }

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

    function getCurrentUser() {
        return storage.getUser();
    }

    function isLoggedIn() {
        return storage.isAuthenticated();
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
