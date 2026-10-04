(function (global) {
    "use strict";

    const client = global.api;
    const path = (id) => encodeURIComponent(id);
    global.ReturnsAPI = Object.freeze({
        create: (orderId, data) => client.post(`/orders/${path(orderId)}/returns/`, data),
        action: (returnId, action, data = {}) =>
            client.post(`/returns/${path(returnId)}/${encodeURIComponent(action)}/`, data),
        refund: (orderId, data) => client.post(`/orders/${path(orderId)}/refunds/`, data),
        fakeRefundTransition: (refundId, status) =>
            client.post(`/admin/fake-refunds/${path(refundId)}/transition/`, {status}),
    });
})(window);
