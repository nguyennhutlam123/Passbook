(function (global) {
    "use strict";

    function withQuery(path, values = {}) {
        const query = new URLSearchParams();
        Object.entries(values).forEach(([key, value]) => {
            if (value !== undefined && value !== null && value !== "") {
                query.set(key, String(value));
            }
        });
        const encoded = query.toString();
        return encoded ? `${path}?${encoded}` : path;
    }

    global.PassbookApiUtils = Object.freeze({withQuery});
})(window);
