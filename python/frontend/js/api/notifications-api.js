(function (global) {
    "use strict";

    const client = global.api;
    global.NotificationsAPI = Object.freeze({
        list: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/notifications/", query)),
        markRead: (notificationId) =>
            client.patch(`/notifications/${encodeURIComponent(notificationId)}/read/`, {}),
        markAllRead: () => client.patch("/notifications/read-all/", {}),
    });
})(window);
