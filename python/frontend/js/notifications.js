document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-notification-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const list = page.querySelector("[data-notification-list]");
    const pagination = page.querySelector("[data-notification-pagination]");
    const error = page.querySelector("[data-notification-error]");
    const markAll = page.querySelector("[data-mark-all]");
    let currentPage = 1;
    let currentData;

    const load = async () => {
        list.replaceChildren(PassbookCommonComponents.loadingState());
        pagination.replaceChildren();
        error.textContent = "";
        try {
            currentData = await NotificationsAPI.list({page: currentPage, page_size: 10});
            const notifications = currentData.results || [];
            const nodes = notifications.map((notification) => {
                const item = PassbookCommonComponents.notificationItem(notification);
                item.addEventListener("click", async () => {
                    item.disabled = true;
                    try {
                        if (!notification.is_read) {
                            await NotificationsAPI.markRead(notification.id);
                            notification.is_read = true;
                            item.classList.remove("is-unread");
                        }
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
                list.replaceChildren();
            }
            const controls = PassbookCommonComponents.pagination({
                previous: currentData.previous,
                next: currentData.next,
                onPrevious: () => { currentPage = Math.max(1, currentPage - 1); void load(); },
                onNext: () => { currentPage += 1; void load(); },
            });
            pagination.replaceChildren(controls);
            markAll.hidden = !notifications.some((item) => !item.is_read);
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
            await load();
        } catch (requestError) {
            error.textContent = requestError.message;
        } finally {
            markAll.disabled = false;
        }
    });
    void load();
});
