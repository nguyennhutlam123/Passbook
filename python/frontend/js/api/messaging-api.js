(function (global) {
    "use strict";

    const client = global.api;
    const path = (id) => encodeURIComponent(id);
    global.MessagingAPI = Object.freeze({
        createForBook: (bookId) => client.post(`/books/${path(bookId)}/conversations/`, {}),
        conversations: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/conversations/", query)),
        getConversation: (conversationId) =>
            client.get(`/conversations/${path(conversationId)}/`),
        messages: (conversationId, query = {}) =>
            client.get(global.PassbookApiUtils.withQuery(
                `/conversations/${path(conversationId)}/messages/`,
                query,
            )),
        sendMessage: (conversationId, data) =>
            client.post(`/conversations/${path(conversationId)}/messages/`, data),
    });
})(window);
