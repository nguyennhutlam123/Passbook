(function (global) {
    "use strict";

    const client = global.api;
    const path = (id) => encodeURIComponent(id);
    global.OrdersAPI = Object.freeze({
        cart: () => client.get("/cart/"),
        addCartItem: (data) => client.post("/cart/items/", data),
        updateCartItem: (itemId, data) =>
            client.patch(`/cart/items/${path(itemId)}/`, data),
        removeCartItem: (itemId) => client.delete(`/cart/items/${path(itemId)}/`),
        clearCart: () => client.delete("/cart/items/"),
        checkoutQuote: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/checkout/", query)),
        checkout: (data) => client.post("/checkout/", data),
        list: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/orders/", query)),
        get: (orderId) => client.get(`/orders/${path(orderId)}/`),
        cancel: (orderId) => client.post(`/orders/${path(orderId)}/cancel/`, {}),
        borrowOrders: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/borrow-orders/", query)),
        borrowAction: (borrowId, action) =>
            client.post(`/borrow-orders/${path(borrowId)}/${encodeURIComponent(action)}/`, {}),
        requestBorrowReturn: (borrowId, data) =>
            client.post(`/borrow-orders/${path(borrowId)}/return-request/`, data),
        addShipmentTracking: (shipmentId, data) =>
            client.post(`/shipments/${path(shipmentId)}/tracking/`, data),
        lendListings: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/lend-listings/", query)),
        createLendListing: (data) => client.post("/lend-listings/", data),
        createReview: (orderId, data) => client.post(`/orders/${path(orderId)}/reviews/`, data),
    });
})(window);
