(function (global) {
    "use strict";

    const client = global.api;
    const path = (id) => encodeURIComponent(id);
    global.ReservationsAPI = Object.freeze({
        list: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/book-reservations/", query)),
        forBook: (bookId) => client.get(`/books/${path(bookId)}/reservations/`),
        create: (bookId, data) => client.post(`/books/${path(bookId)}/reservations/`, data),
        action: (reservationId, action) =>
            client.post(`/book-reservations/${path(reservationId)}/${encodeURIComponent(action)}/`, {}),
    });
})(window);
