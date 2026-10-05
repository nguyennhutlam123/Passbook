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
        if (Number(message.sender_id) === Number(currentUserId)) {
            const receipt = document.createElement("span");
            receipt.className = "conversation-message__receipt";
            receipt.textContent = message.is_read ? "Đã xem" : "Đã gửi";
            item.append(receipt);
        } else {
            const reportButton = document.createElement("button");
            reportButton.className = "conversation-message__report";
            reportButton.type = "button";
            reportButton.dataset.reportMessageId = String(message.id);
            reportButton.setAttribute("aria-expanded", "false");
            reportButton.textContent = "Báo cáo tin nhắn";
            const reportForm = document.createElement("form");
            reportForm.className = "conversation-message__report-form";
            reportForm.hidden = true;
            const reason = document.createElement("select");
            reason.name = "reason";
            reason.required = true;
            [
                ["INAPPROPRIATE_CONTENT", "Nội dung không phù hợp"],
                ["SPAM", "Spam"],
                ["SCAM", "Lừa đảo"],
                ["POLICY_VIOLATION", "Vi phạm chính sách"],
                ["OTHER", "Lý do khác"],
            ].forEach(([value, label]) => {
                const option = document.createElement("option");
                option.value = value;
                option.textContent = label;
                reason.append(option);
            });
            const description = document.createElement("textarea");
            description.name = "description";
            description.maxLength = 5000;
            description.placeholder = "Mô tả thêm (không bắt buộc)";
            const submit = document.createElement("button");
            submit.className = "button button-outline";
            submit.type = "submit";
            submit.textContent = "Gửi báo cáo";
            reportForm.append(reason, description, submit);
            item.append(reportButton, reportForm);
        }
        return item;
    }

    function conversationItem(conversation) {
        const button = document.createElement("button");
        button.className = "conversation-list-item";
        button.type = "button";
        button.dataset.conversationId = String(conversation.id);
        const title = document.createElement("strong");
        title.textContent = conversation.other_user?.name || "Cuộc hội thoại";
        const preview = document.createElement("span");
        preview.textContent = conversation.last_message?.content || "Bắt đầu trò chuyện";
        const time = document.createElement("time");
        const activityAt = conversation.last_message?.created_at || conversation.updated_at;
        time.textContent = new Date(activityAt).toLocaleString("vi-VN");
        button.append(title, preview, time);
        return button;
    }

    global.PassbookMessagingComponents = Object.freeze({messageItem, conversationItem});
})(window);
