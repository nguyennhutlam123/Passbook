(function (global) {
    "use strict";

    const client = global.api;
    const path = (id) => encodeURIComponent(id);
    global.AdminAPI = Object.freeze({
        dashboard: () => client.get("/admin/dashboard/"),
        users: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/admin/users/", query)),
        reports: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/admin/reports/", query)),
        updateReport: (reportId, data) =>
            client.patch(`/admin/reports/${path(reportId)}/`, data),
        setUserStatus: (userId, data) =>
            client.patch(`/admin/users/${path(userId)}/status/`, data),
        violations: (userId, query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                `/admin/users/${path(userId)}/violations/`,
                query,
            )),
        addViolation: (userId, data) =>
            client.post(`/admin/users/${path(userId)}/violations/`, data),
        updateViolation: (violationId, data) =>
            client.patch(`/admin/violations/${path(violationId)}/`, data),
        deleteViolation: (violationId) =>
            client.delete(`/admin/violations/${path(violationId)}/`),
    });
})(window);
