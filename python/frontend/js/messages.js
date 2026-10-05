document.addEventListener("DOMContentLoaded", async () => {
    const page = document.querySelector("[data-messages-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const list = page.querySelector("[data-conversation-list]");
    const error = page.querySelector("[data-messages-error]");
    const moreButton = page.querySelector("[data-conversation-more]");
    let nextPage = 1;
    let hasMore = false;
    let requestedConversationOpened = false;
    list.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải hội thoại..."));

    const appendConversations = (conversations) => {
        list.append(...conversations.map((conversation) =>
            PassbookMessagingComponents.conversationItem(conversation)));
        list.querySelectorAll("[data-conversation-id]:not([data-listener-attached])")
            .forEach((item) => {
                item.dataset.listenerAttached = "true";
                item.addEventListener("click", () => {
                    void openConversationModal(item.dataset.conversationId);
                });
            });
    };

    const loadConversations = async (pageNumber) => {
        const response = await MessagingAPI.conversations({
            page: pageNumber,
            page_size: 50,
        });
        const conversations = Array.isArray(response) ? response : response.results || [];
        if (!conversations.length && pageNumber === 1) {
            const empty = PassbookCommonComponents.emptyStateElement(
                "Chưa có cuộc hội thoại.",
                "Khi bạn liên hệ người bán hoặc người mua, cuộc trò chuyện riêng sẽ xuất hiện tại đây.",
            );
            const browse = document.createElement("a");
            browse.className = "button button-primary";
            browse.href = "books.html";
            browse.textContent = "Khám phá sách";
            empty.append(browse);
            list.replaceChildren(empty);
        } else {
            appendConversations(conversations);
        }
        hasMore = Boolean(response.next);
        nextPage = pageNumber + 1;
        moreButton.hidden = !hasMore;
        error.textContent = "";
        const requestedId = new URLSearchParams(location.search).get("conversation_id");
        if (requestedId) {
            const requestedConversation = list.querySelector(
                `[data-conversation-id="${CSS.escape(requestedId)}"]`,
            );
            if (requestedConversation) {
                requestedConversation.scrollIntoView({
                    behavior: "smooth",
                    block: "center",
                });
                if (!requestedConversationOpened) {
                    requestedConversationOpened = true;
                    void openConversationModal(requestedId);
                }
            }
        }
    };

    moreButton.addEventListener("click", async () => {
        if (!hasMore) return;
        moreButton.disabled = true;
        try {
            await loadConversations(nextPage);
        } catch (requestError) {
            error.textContent = requestError.message;
        } finally {
            moreButton.disabled = false;
        }
    });

    try {
        await loadConversations(1);
    } catch (requestError) {
        error.textContent = requestError.message;
        list.replaceChildren(PassbookCommonComponents.emptyStateElement(
            "Không thể tải tin nhắn.",
            requestError.message,
        ));
    }
});
