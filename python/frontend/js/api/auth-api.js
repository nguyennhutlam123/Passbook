(function (global) {
    "use strict";

    const client = global.api;

    async function login(credentials) {
        const result = await client.post("/auth/login/", credentials);
        if (result?.access && result?.refresh && result?.user) {
            global.PassbookAuth.setSession(result);
        }
        return result;
    }

    async function logout() {
        const refresh = global.PassbookAuth.getRefreshToken();
        try {
            if (refresh) await client.post("/auth/logout/", {refresh});
        } finally {
            global.PassbookAuth.clearSession();
        }
    }

    async function currentUser() {
        const result = await client.get("/auth/authenticated-user/");
        if (result?.user) global.PassbookAuth.updateUser(result.user);
        return result?.user || null;
    }

    global.AuthAPI = Object.freeze({
        login,
        register: (data) => client.post("/auth/register/", data),
        logout,
        refresh: (refresh) => client.post("/auth/token/refresh/", {refresh}),
        currentUser,
        profile: () => client.get("/auth/profile/"),
        updateProfile: (data) => client.patch("/auth/profile/", data),
        changePassword: (data) => client.post("/auth/change-password/", data),
        verifyOtp: (data) => client.post("/auth/verify-otp/", data),
        resendOtp: (data) => client.post("/auth/resend-otp/", data),
        forgotPassword: (data) => client.post("/auth/forgot-password/", data),
        resetPassword: (data) => client.post("/auth/reset-password/", data),
        requestContactChange: (channel, data) =>
            client.post(`/auth/change-${channel}/request/`, data),
    });
})(window);
