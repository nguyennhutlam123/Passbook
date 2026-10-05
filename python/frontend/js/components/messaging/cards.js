(function (global) {
    "use strict";

    function messageItem(message, currentUserId) {
        const item = document.createElement("div");
        item.className = `conversation-message ${Number(message.sender_id) === Number(currentUserId) ? "is-mine" : ""}`;
        const content = document.createElement("p");
        content.textContent = message.content || "";
        const time = document.createElement("time");
        time.textContent = new Date(message.created_at).toLocaleString("vi-VN");
        item.append(content, time);
        return item;
    }

    function conversationItem(conversation) {
        const button = document.createElement("button");
        button.className = "conversation-list-item";
        button.type = "button";
        button.dataset.conversationId = String(conversation.id);
        const title = document.createElement("strong");
        title.textContent = conversation.book?.title || "Cuộc hội thoại";
        const members = document.createElement("span");
        members.textContent = `${conversation.buyer?.name || ""} ↔ ${conversation.seller?.name || ""}`;
        const time = document.createElement("time");
        time.textContent = new Date(conversation.updated_at).toLocaleString("vi-VN");
        button.append(title, members, time);
        return button;
    }

    global.PassbookMessagingComponents = Object.freeze({messageItem, conversationItem});
})(window);
