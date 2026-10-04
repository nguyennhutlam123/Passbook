(function (global) {
    "use strict";

    const client = global.api;
    const path = (id) => encodeURIComponent(id);
    global.AdminAPI = Object.freeze({
        dashboard: () => client.get("/admin/dashboard/"),
        dashboardSection: (section, query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                `/admin/dashboard/${path(section)}/`,
                query,
            )),
        reservations: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                "/admin/dashboard/reservations/",
                query,
            )),
        reservation: (reservationId, query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                `/admin/dashboard/reservations/${path(reservationId)}/`,
                query,
            )),
        borrowOrders: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                "/admin/dashboard/borrow-orders/",
                query,
            )),
        borrowOrder: (borrowOrderId, query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                `/admin/dashboard/borrow-orders/${path(borrowOrderId)}/`,
                query,
            )),
        orders: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                "/admin/dashboard/orders/",
                query,
            )),
        order: (orderId) =>
            client.get(`/admin/dashboard/orders/${path(orderId)}/`),
        payments: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                "/admin/dashboard/payments/",
                query,
            )),
        payment: (paymentId) =>
            client.get(`/admin/dashboard/payments/${path(paymentId)}/`),
        reviewBankTransfer: (paymentId, data) =>
            client.patch(
                `/admin/dashboard/payments/${path(paymentId)}/bank-transfer-review/`,
                data,
            ),
        shipments: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                "/admin/dashboard/shipping/shipments/",
                query,
            )),
        shipment: (shipmentId) =>
            client.get(`/admin/dashboard/shipping/shipments/${path(shipmentId)}/`),
        updateShipmentStatus: (shipmentId, data) =>
            client.patch(
                `/admin/dashboard/shipping/shipments/${path(shipmentId)}/status/`,
                data,
            ),
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
