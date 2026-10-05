document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-notification-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const list = page.querySelector("[data-notification-list]");
    const pagination = page.querySelector("[data-notification-pagination]");
    const error = page.querySelector("[data-notification-error]");
    const markAll = page.querySelector("[data-mark-all]");
    let currentPage = 1;
    let unreadCount = 0;

    const notificationTarget = (notification) => {
        const entityId = Number(notification.reference_id);
        if (!Number.isSafeInteger(entityId) || entityId < 1) return null;
        if (notification.entity_type === "ORDER") {
            return `orders.html?order_id=${encodeURIComponent(entityId)}`;
        }
        if (notification.entity_type === "BORROW_ORDER") {
            return `borrow-tickets.html?borrow_id=${encodeURIComponent(entityId)}`;
        }
        if (notification.entity_type === "CONVERSATION") {
            return `messages.html?conversation_id=${encodeURIComponent(entityId)}`;
        }
        if (notification.entity_type === "REPORT") {
            return `profile.html#reports`;
        }
        return null;
    };

    const load = async () => {
        list.replaceChildren(PassbookCommonComponents.loadingState());
        pagination.replaceChildren();
        error.textContent = "";
        try {
            const currentData = await NotificationsAPI.list({page: currentPage, page_size: 10});
            const notifications = currentData.results || [];
            unreadCount = Number(currentData.unread_count);
            if (!Number.isSafeInteger(unreadCount) || unreadCount < 0) {
                unreadCount = notifications.filter((item) => !item.is_read).length;
            }
            const nodes = notifications.map((notification) => {
                const item = PassbookCommonComponents.notificationItem(notification);
                item.addEventListener("click", async () => {
                    item.disabled = true;
                    try {
                        if (!notification.is_read) {
                            await NotificationsAPI.markRead(notification.id);
                            notification.is_read = true;
                            unreadCount = Math.max(0, unreadCount - 1);
                            item.classList.remove("is-unread");
                            markAll.hidden = unreadCount === 0;
                        }
                        const target = notificationTarget(notification);
                        if (target) global.location.assign(target);
                    } catch (requestError) {
                        error.textContent = requestError.message;
                    } finally {
                        item.disabled = false;
                    }
                });
                return item;
            });
            if (nodes.length) {
                list.replaceChildren(...nodes);
            } else {
                list.replaceChildren(
                    PassbookCommonComponents.emptyStateElement(
                        "Bạn chưa có thông báo nào.",
                    ),
                );
            }
            const controls = PassbookCommonComponents.pagination({
                previous: currentData.previous,
                next: currentData.next,
                onPrevious: () => { currentPage = Math.max(1, currentPage - 1); void load(); },
                onNext: () => { currentPage += 1; void load(); },
            });
            pagination.replaceChildren(controls);
            markAll.hidden = unreadCount === 0;
        } catch (requestError) {
            const failure = PassbookCommonComponents.emptyStateElement(
                "Không thể tải thông báo.",
                "Kiểm tra kết nối rồi thử lại.",
            );
            const retry = document.createElement("button");
            retry.className = "button button-outline";
            retry.type = "button";
            retry.textContent = "Thử lại";
            retry.addEventListener("click", () => void load());
            failure.append(retry);
            list.replaceChildren(failure);
            error.textContent = requestError.message;
        }
    };

    markAll.addEventListener("click", async () => {
        markAll.disabled = true;
        try {
            await NotificationsAPI.markAllRead();
            unreadCount = 0;
            await load();
        } catch (requestError) {
            error.textContent = requestError.message;
        } finally {
            markAll.disabled = false;
        }
    });
    void load();
});
