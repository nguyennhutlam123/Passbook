(function (global) {
    "use strict";

    const client = global.api;
    const path = (id) => encodeURIComponent(id);
    global.PaymentsAPI = Object.freeze({
        listForOrder: (orderId) => client.get(`/orders/${path(orderId)}/payments/`),
        createIntent: (orderId, data) =>
            client.post(`/orders/${path(orderId)}/payments/`, data),
        fakeTransition: (paymentId, status) =>
            client.post(`/admin/fake-payments/${path(paymentId)}/transition/`, {status}),
        fakeRefundTransition: (refundId, status) =>
            client.post(`/admin/fake-refunds/${path(refundId)}/transition/`, {status}),
    });
})(window);
