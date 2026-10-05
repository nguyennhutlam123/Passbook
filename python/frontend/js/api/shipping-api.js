(function (global) {
    "use strict";

    const client = global.api;
    const path = (id) => encodeURIComponent(id);
    global.ShippingAPI = Object.freeze({
        create: (orderId, data) => client.post(`/orders/${path(orderId)}/shipments/`, data),
        addTracking: (shipmentId, data) =>
            client.post(`/shipments/${path(shipmentId)}/tracking/`, data),
    });
})(window);
