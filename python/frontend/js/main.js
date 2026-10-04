function isLoggedIn() {
    return PassbookAuth.isLoggedIn();
}

function getCurrentPage() {
    return window.location.pathname.split("/").pop() || "index.html";
}

function formatPrice(price) {
    return `${new Intl.NumberFormat("vi-VN").format(price)}đ`;
}

function safeImageUrl(url) {
    try {
        const parsed = new URL(url);
        return parsed.protocol === "https:"
            ? parsed.href
            : "https://placehold.co/640x480/e2e8f0/475569?text=PASSBOOK";
    } catch (_error) {
        return "https://placehold.co/640x480/e2e8f0/475569?text=PASSBOOK";
    }
}

function attachImageFallbacks(root = document) {
    root.querySelectorAll(".book-card__image[data-fallback]").forEach((image) => image.addEventListener("error", () => {
        image.src = image.dataset.fallback;
        image.removeAttribute("data-fallback");
    }, {once: true}));
}

let favoriteBookIds = new Set();
let favoriteBookIdsPromise = null;

async function loadFavoriteBookIds() {
    if (!isLoggedIn()) {
        favoriteBookIds = new Set();
        favoriteBookIdsPromise = null;
        return favoriteBookIds;
    }
    if (!favoriteBookIdsPromise) {
        favoriteBookIdsPromise = FavoritesAPI.list({page_size: 50})
            .then((data) => {
                favoriteBookIds = new Set((data.results || []).map((item) => Number(item.book?.id || item.book_id)));
                return favoriteBookIds;
            })
            .catch((error) => {
                favoriteBookIdsPromise = null;
                throw error;
            });
    }
    return favoriteBookIdsPromise;
}

function isFavoriteBook(bookId) {
    return favoriteBookIds.has(Number(bookId));
}

function closeModal() {
    document.querySelector(".modal-backdrop")?.remove();
}

function showModal(content) {
    closeModal();
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `<div class="modal" role="dialog" aria-modal="true">${content}</div>`;
    document.body.appendChild(backdrop);
    backdrop.addEventListener("click", (event) => {
        if (event.target === backdrop || event.target.closest("[data-modal-close]")) closeModal();
    });
}

function showToast(message) {
    document.querySelector(".toast")?.remove();
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.setAttribute("role", "status");
    toast.textContent = message;
    document.body.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3000);
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[character]));
}

async function openConversationModal(conversationId) {
    if (!isLoggedIn()) {
        window.location.href = "login.html";
        return;
    }
    showModal(`<div class="conversation-modal">
        <button class="modal-close" type="button" data-modal-close>Đóng</button>
        <div data-conversation-heading>Đang tải cuộc hội thoại...</div>
        <div class="conversation-messages" data-conversation-messages></div>
        <form data-message-form>
            <label class="form-label" for="message-content">Tin nhắn</label>
            <textarea id="message-content" maxlength="5000" required></textarea>
            <div class="modal-actions"><button class="button button-primary" type="submit">Gửi</button></div>
        </form>
    </div>`);
    const heading = document.querySelector("[data-conversation-heading]");
    const messages = document.querySelector("[data-conversation-messages]");
    const form = document.querySelector("[data-message-form]");
    const loadMessages = async () => {
        const data = await MessagingAPI.messages(conversationId);
        const currentUserId = Number(PassbookAuth.getCurrentUser()?.id);
        messages.innerHTML = "";
        (data.results || []).forEach((message) => {
            messages.appendChild(PassbookMessagingComponents.messageItem(message, currentUserId));
        });
        messages.scrollTop = messages.scrollHeight;
    };
    try {
        const conversation = await MessagingAPI.getConversation(conversationId);
        const contextTitle = conversation.book?.title
            || (conversation.order?.order_code
                ? `Đơn hàng ${conversation.order.order_code}`
                : "Cuộc hội thoại");
        const participants = [conversation.buyer?.name, conversation.seller?.name]
            .filter(Boolean)
            .map(escapeHtml)
            .join(" ↔ ");
        heading.innerHTML = `<strong>${escapeHtml(contextTitle)}</strong>${participants ? `<span class="caption">${participants}</span>` : ""}`;
        await loadMessages();
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const input = form.querySelector("textarea");
            const content = input.value.trim();
            if (!content) return;
            try {
                await MessagingAPI.sendMessage(conversationId, {content});
                input.value = "";
                await loadMessages();
            } catch (error) {
                showToast(error.message);
            }
        });
    } catch (error) {
        heading.textContent = error.message;
        form.hidden = true;
    }
}

function setupNotifications() {
    const button = document.querySelector("[data-notifications]");
    if (!button || !isLoggedIn()) return;
    let loaded = false;
    const menu = document.createElement("div");
    menu.className = "notification-menu";
    menu.hidden = true;
    button.parentElement.appendChild(menu);
    const render = (data) => {
        const results = data.results || [];
        menu.replaceChildren();
        if (!results.length) {
            menu.append(PassbookCommonComponents.emptyState("Không có thông báo."));
        }
        results.forEach((notification) => {
            const item = PassbookCommonComponents.notificationItem(notification);
            item.addEventListener("click", async () => {
                try {
                    await NotificationsAPI.markRead(notification.id);
                    notification.is_read = true;
                    item.classList.remove("is-unread");
                    const count = button.querySelector("[data-notification-count]");
                    if (count) {
                        const unread = results.filter((entry) => !entry.is_read).length;
                        count.textContent = String(unread);
                        count.hidden = unread === 0;
                    }
                    if (notification.reference_id) {
                        window.location.href = `book-detail.html?id=${encodeURIComponent(notification.reference_id)}`;
                    } else {
                        window.location.href = "notifications.html";
                    }
                } catch (error) {
                    showToast(error.message);
                }
            });
            menu.append(item);
        });
        const viewAll = document.createElement("a");
        viewAll.className = "notification-view-all";
        viewAll.href = "notifications.html";
        viewAll.textContent = "Xem tất cả thông báo";
        menu.append(viewAll);
        const unread = results.filter((item) => !item.is_read).length;
        const count = button.querySelector("[data-notification-count]");
        if (count) {
            count.textContent = String(unread);
            count.hidden = unread === 0;
        }
        if (unread) {
            const markAll = document.createElement("button");
            markAll.className = "notification-mark-all";
            markAll.type = "button";
            markAll.textContent = "Đánh dấu tất cả đã đọc";
            markAll.addEventListener("click", async () => {
                markAll.disabled = true;
                try {
                    await NotificationsAPI.markAllRead();
                    results.forEach((item) => { item.is_read = true; });
                    render({results});
                } catch (error) {
                    showToast(error.message);
                } finally {
                    markAll.disabled = false;
                }
            });
            menu.append(markAll);
        }
    };
    button.addEventListener("click", async () => {
        menu.hidden = !menu.hidden;
        if (!loaded) {
            try {
                render(await NotificationsAPI.list({page_size: 10}));
                loaded = true;
            } catch (error) {
                menu.replaceChildren(PassbookCommonComponents.emptyState(error.message));
            }
        }
    });
}

function fallbackBookImage(book) {
    const subject = book.subject?.name || book.subject || "PASSBOOK";
    const encoded = encodeURIComponent(subject.slice(0, 24));
    return `https://placehold.co/640x860/f0e5d7/263b4a?text=${encoded}`;
}

function renderBookCard(book) {
    return PassbookBookComponents.bookCard(book, {favorite: isFavoriteBook(book.id)});
}

async function toggleFavorite(bookId, button) {
    if (!isLoggedIn()) {
        window.location.href = "login.html";
        return;
    }
    const isFavorite = button.getAttribute("aria-pressed") === "true";
    try {
        if (isFavorite) await FavoritesAPI.remove(bookId);
        else await FavoritesAPI.add(bookId);
        if (isFavorite) favoriteBookIds.delete(Number(bookId));
        else favoriteBookIds.add(Number(bookId));
        button.classList.toggle("is-favorite", !isFavorite);
        button.setAttribute("aria-pressed", String(!isFavorite));
        button.textContent = isFavorite ? "♡" : "♥";
        showToast(isFavorite ? "Đã bỏ lưu giáo trình" : "Đã lưu giáo trình");
    } catch (error) {
        showToast(error.message);
    }
}

function bindFavoriteButtons(root = document) {
    root.querySelectorAll("[data-favorite]").forEach((button) => button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleFavorite(Number(button.dataset.favorite), button);
    }));
}

function renderHomepage() {
    const newGrid = document.querySelector("[data-new-books]");
    const collections = document.querySelector("[data-subject-collections]");
    if (!newGrid || !collections) return;
    const subjectSections = [
        {key: "Công nghệ thông tin", title: "Công nghệ thông tin", description: "Giáo trình lập trình, dữ liệu và công nghệ.", tone: "blue"},
        {key: "Vật lý", title: "Vật lý", description: "Tài liệu nền tảng cho những khám phá tự nhiên.", tone: "orange"},
        {key: "Toán", title: "Toán học", description: "Từ giải tích đến xác suất và tư duy logic.", tone: "green"},
        {key: "Hóa học", title: "Hóa học", description: "Giáo trình và tài liệu thực hành.", tone: "purple"},
        {key: "Ngoại ngữ", title: "Ngoại ngữ", description: "Mở rộng vốn từ, mở rộng thế giới.", tone: "pink"},
    ];
    const renderCollection = (section, books) => {
        if (!books.length) return "";
        const query = encodeURIComponent(section.key);
        return `<section class="page-shell collection-section collection-section--${section.tone}" aria-labelledby="collection-${section.tone}">
            <div class="collection-heading"><div><span class="eyebrow">${section.key}</span><h2 id="collection-${section.tone}">${section.title}</h2><p>${section.description}</p></div><a class="text-link" href="books.html?q=${query}">Xem tất cả <span>→</span></a></div>
            <div class="book-grid book-grid--storefront">${books.slice(0, 4).map(renderBookCard).join("")}</div>
        </section>`;
    };
    BooksAPI.list({page_size: 24}).then(async (data) => {
        if (isLoggedIn()) {
            try {
                await loadFavoriteBookIds();
            } catch (error) {
                showToast(error.message);
            }
        }
        const books = data.results || [];
        newGrid.innerHTML = books.slice(0, 4).map(renderBookCard).join("");
        collections.innerHTML = subjectSections.map((section) => renderCollection(section, books.filter((book) => (book.subject?.name || book.subject || "").toLowerCase().includes(section.key.toLowerCase())))).join("");
        bindFavoriteButtons(document);
        attachImageFallbacks(document);
    }).catch((error) => {
        newGrid.innerHTML = `<div class="empty-state"><strong>Không thể tải sách</strong><span>${escapeHtml(error.message)}</span></div>`;
    });

    document.querySelector("[data-home-search]")?.addEventListener("submit", (event) => {
        event.preventDefault();
        const query = new FormData(event.currentTarget).get("q")?.toString().trim();
        window.location.href = query ? `books.html?q=${encodeURIComponent(query)}` : "books.html";
    });
}

function renderSiteChrome() {
    const page = getCurrentPage();
    document.body.classList.toggle("books-page", page === "books.html");
    const authenticated = isLoggedIn();
    const user = PassbookAuth.getCurrentUser() || {};
    const userName = user.name || "Người dùng";
    const header = document.querySelector("[data-site-header]");
    const footer = document.querySelector("[data-site-footer]");

    if (header) {
        header.innerHTML = PassbookCommonComponents.siteHeader({page, authenticated, user});
    }

    if (footer) {
        footer.innerHTML = PassbookCommonComponents.siteFooter();
    }

    const toggle = document.querySelector(".nav-toggle");
    const menu = document.querySelector(".nav-menu");
    toggle?.addEventListener("click", () => {
        const isOpen = menu.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", String(isOpen));
    });

    document.querySelector("[data-logout]")?.addEventListener("click", async () => {
        try {
            await AuthAPI.logout();
        } catch (error) {
            showToast(error.message);
        } finally {
            window.location.reload();
        }
    });
    document.querySelector("[data-nav-search]")?.addEventListener("submit", (event) => {
        event.preventDefault();
        const query = new FormData(event.currentTarget).get("q")?.toString().trim();
        const basePath = window.location.pathname.split("/").includes("admin") ? "../" : "";
        window.location.href = query
            ? `${basePath}books.html?q=${encodeURIComponent(query)}`
            : `${basePath}books.html`;
    });
    setupNotifications();
}

document.addEventListener("DOMContentLoaded", () => {
    document.documentElement.classList.add("js-ready");
    renderSiteChrome();
    if (getAccessToken()) {
        AuthAPI.currentUser()
            .then(() => {
                renderSiteChrome();
            })
            .catch((error) => {
                if ([401, 403].includes(error.status)) {
                    clearAuth();
                    renderSiteChrome();
                    showToast(error.message);
                } else if (error.status === 0) {
                    showToast(error.message);
                }
            });
    }
    renderHomepage();
});
