document.addEventListener("DOMContentLoaded", async () => {
    const page = document.querySelector("[data-messages-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const list = page.querySelector("[data-conversation-list]");
    const error = page.querySelector("[data-messages-error]");
    list.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải hội thoại..."));
    try {
        const response = await MessagingAPI.conversations();
        const conversations = Array.isArray(response) ? response : response.results || [];
        list.replaceChildren(...(conversations.length
            ? conversations.map((conversation) => PassbookMessagingComponents.conversationItem(conversation))
            : [PassbookCommonComponents.emptyStateElement(
                "Chưa có cuộc hội thoại.",
                "Khi nhắn tin với người bán hoặc người mượn, cuộc trò chuyện sẽ xuất hiện tại đây.",
            )]));
        list.querySelectorAll("[data-conversation-id]").forEach((item) => item.addEventListener("click", () => {
            void openConversationModal(item.dataset.conversationId);
        }));
        const requestedId = new URLSearchParams(location.search).get("conversation_id");
        if (requestedId) {
            list.querySelector(`[data-conversation-id="${CSS.escape(requestedId)}"]`)?.scrollIntoView({
                behavior: "smooth",
                block: "center",
            });
        }
    } catch (requestError) {
        error.textContent = requestError.message;
        list.replaceChildren(PassbookCommonComponents.emptyStateElement(
            "Không thể tải tin nhắn.",
            requestError.message,
        ));
    }
});
