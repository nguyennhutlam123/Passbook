(function (global) {
    "use strict";

    const client = global.api;
    global.ReportsAPI = Object.freeze({
        create: (data) => client.post("/reports/", data),
        mine: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/reports/my/", query)),
    });
})(window);
