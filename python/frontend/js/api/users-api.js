(function (global) {
    "use strict";

    const client = global.api;
    global.UsersAPI = Object.freeze({
        sellerProfile: (userId) => client.get(`/users/${encodeURIComponent(userId)}/profile/`),
        publicListings: (userId, query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                `/users/${encodeURIComponent(userId)}/listings/`,
                query,
            )),
        addresses: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/users/addresses/", query)),
        createAddress: (data) => client.post("/users/addresses/", data),
        updateAddress: (addressId, data) =>
            client.patch(`/users/addresses/${encodeURIComponent(addressId)}/`, data),
        deleteAddress: (addressId) =>
            client.delete(`/users/addresses/${encodeURIComponent(addressId)}/`),
        violations: (query) =>
            client.get(global.PassbookApiUtils.withQuery("/users/violations/", query)),
    });
})(window);
