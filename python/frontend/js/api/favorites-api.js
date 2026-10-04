(function (global) {
    "use strict";

    const client = global.api;
    global.FavoritesAPI = Object.freeze({
        list: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/favorites/", query)),
        add: (bookId) => client.post(`/books/${encodeURIComponent(bookId)}/favorite/`, {}),
        remove: (bookId) => client.delete(`/books/${encodeURIComponent(bookId)}/favorite/`),
    });
})(window);
