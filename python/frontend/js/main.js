function isLoggedIn() {
    return Boolean(localStorage.getItem("accessToken"));
}

function getCurrentPage() {
    return window.location.pathname.split("/").pop() || "index.html";
}

function formatPrice(price) {
    return `${new Intl.NumberFormat("vi-VN").format(price)}đ`;
}

function safeImageUrl(url) {
    return typeof url === "string" && /^https?:\/\//i.test(url)
        ? url
        : "https://placehold.co/640x480/e2e8f0/475569?text=PASSBOOK";
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
        favoriteBookIdsPromise = api.get("/favorites/?page_size=50")
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
        const data = await api.get(`/conversations/${conversationId}/messages/`);
        messages.innerHTML = "";
        (data.results || []).forEach((message) => {
            const item = document.createElement("div");
            item.className = `conversation-message ${Number(message.sender_id) === Number(JSON.parse(localStorage.getItem("currentUser") || "{}").id) ? "is-mine" : ""}`;
            item.innerHTML = `<p>${escapeHtml(message.content)}</p><time>${new Date(message.created_at).toLocaleString("vi-VN")}</time>`;
            messages.appendChild(item);
        });
        messages.scrollTop = messages.scrollHeight;
    };
    try {
        const conversation = await api.get(`/conversations/${conversationId}/`);
        heading.innerHTML = `<strong>${escapeHtml(conversation.book.title)}</strong><span class="caption">${escapeHtml(conversation.buyer.name)} ↔ ${escapeHtml(conversation.seller.name)}</span>`;
        await loadMessages();
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const input = form.querySelector("textarea");
            const content = input.value.trim();
            if (!content) return;
            try {
                await api.post(`/conversations/${conversationId}/messages/`, {content});
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
        menu.innerHTML = results.length ? results.map((item) => `<button class="notification-item ${item.is_read ? "" : "is-unread"}" type="button" data-notification-id="${item.id}" data-reference-id="${item.reference_id || ""}">
            <strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.content)}</span><time>${new Date(item.created_at).toLocaleString("vi-VN")}</time>
        </button>`).join("") : '<p class="caption">Không có thông báo.</p>';
        menu.querySelectorAll("[data-notification-id]").forEach((item) => item.addEventListener("click", async () => {
            try {
                await api.patch(`/notifications/${item.dataset.notificationId}/read/`, {});
                item.classList.remove("is-unread");
                if (item.dataset.referenceId) window.location.href = `book-detail.html?id=${item.dataset.referenceId}`;
            } catch (error) {
                showToast(error.message);
            }
        }));
    };
    button.addEventListener("click", async () => {
        menu.hidden = !menu.hidden;
        if (!loaded) {
            try {
                render(await api.get("/notifications/?page_size=50"));
                loaded = true;
            } catch (error) {
                menu.innerHTML = `<p class="caption">${escapeHtml(error.message)}</p>`;
            }
        }
    });
}

function renderBookCard(book) {
    if (book.seller && Array.isArray(book.images)) {
        const image = book.images?.find((item) => item.is_primary) || book.images?.[0];
        const isFavorite = isFavoriteBook(book.id);
        const statusLabel = {sold: "Đã bán", reserved: "Đã giữ", hidden: "Đã ẩn", deleted: "Đã xóa"}[book.status];
        const badge = statusLabel
            ? `<span class="badge badge-danger">${statusLabel}</span>`
            : `<span class="badge badge-success">${book.condition_label || book.condition_status}</span>`;
        return `<article class="book-card"><a href="book-detail.html?id=${book.id}"><img class="book-card__image" src="${safeImageUrl(image?.image_url)}" alt="${book.title}" loading="lazy"></a><div class="book-card__body"><button class="favorite-button ${isFavorite ? "is-favorite" : ""}" type="button" data-favorite="${book.id}" aria-label="${isFavorite ? "Bỏ lưu" : "Lưu"} ${book.title}" aria-pressed="${isFavorite}">${isFavorite ? "♥" : "♡"}</button>${badge}<h3 class="book-card__title"><a href="book-detail.html?id=${book.id}">${book.title}</a></h3><p class="caption">${book.subject?.name || ""}</p><strong class="price">${formatPrice(Number(book.price))}</strong><div class="seller-line">${book.seller?.name || "Người bán"}</div></div></article>`;
    }
    const favorites = JSON.parse(localStorage.getItem("favoriteBookIds") || "[]");
    const isFavorite = favorites.includes(book.id);
    const status = book.status === "sold"
        ? '<span class="badge badge-danger">Đã bán</span>'
        : `<span class="badge ${book.condition === "Như mới" ? "badge-success" : "badge-warning"}">${book.condition}</span>`;
    const verified = book.seller.verified ? '<span class="verified" title="Người bán đã xác minh">✓</span>' : "";

    return `
        <article class="book-card">
            <a href="book-detail.html?id=${book.id}" aria-label="Xem ${book.title}">
                <img class="book-card__image" src="${book.images[0]}" alt="Ảnh bìa ${book.title}" loading="lazy">
            </a>
            <div class="book-card__body">
                <button class="favorite-button ${isFavorite ? "is-favorite" : ""}" type="button" data-favorite="${book.id}" aria-label="${isFavorite ? "Bỏ lưu" : "Lưu"} ${book.title}" aria-pressed="${isFavorite}">${isFavorite ? "♥" : "♡"}</button>
                ${status}
                <h3 class="book-card__title"><a href="book-detail.html?id=${book.id}">${book.title}</a></h3>
                <p class="caption">${book.subject} · ${book.subjectCode}</p>
                <p class="caption">${book.school}</p>
                <strong class="price">${formatPrice(book.price)}</strong>
                <div class="seller-line"><span class="avatar" aria-hidden="true">${book.seller.name.slice(4, 6)}</span><span>${book.seller.name} ${verified}</span></div>
            </div>
        </article>`;
}

async function toggleFavorite(bookId, button) {
    if (!isLoggedIn()) {
        window.location.href = "login.html";
        return;
    }
    const isFavorite = button.getAttribute("aria-pressed") === "true";
    try {
        if (isFavorite) await api.delete(`/books/${bookId}/favorite/`);
        else await api.post(`/books/${bookId}/favorite/`, {});
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
    const grid = document.querySelector("[data-featured-books]");
    if (!grid) return;
    Promise.all([api.get("/books/?page_size=6"), loadFavoriteBookIds()]).then(([data]) => {
        grid.innerHTML = data.results.map(renderBookCard).join("");
        bindFavoriteButtons(grid);
    }).catch((error) => { grid.innerHTML = `<div class="empty-state">${error.message}</div>`; });

    document.querySelector("[data-home-search]")?.addEventListener("submit", (event) => {
        event.preventDefault();
        const query = new FormData(event.currentTarget).get("q")?.toString().trim();
        window.location.href = query ? `books.html?q=${encodeURIComponent(query)}` : "books.html";
    });
}

function renderSiteChrome() {
    const page = getCurrentPage();
    const authenticated = isLoggedIn();
    const user = JSON.parse(localStorage.getItem("currentUser") || "{}");
    const userName = user.name || "Nguyễn Lâm";
    const header = document.querySelector("[data-site-header]");
    const footer = document.querySelector("[data-site-footer]");

    if (header) {
        header.innerHTML = `
            <nav class="navbar" aria-label="Điều hướng chính">
                <a class="brand" href="index.html">
                    <span class="brand__icon" aria-hidden="true">📚</span>
                    <span>PASSBOOK</span>
                </a>
                <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">
                    <span aria-hidden="true">☰</span>
                    <span class="sr-only">Mở menu</span>
                </button>
                <div class="nav-menu" id="site-nav">
                    <div class="nav-links">
                        <a class="${page === "index.html" ? "is-active" : ""}" href="index.html">Trang chủ</a>
                        <a class="${page === "books.html" ? "is-active" : ""}" href="books.html">Tìm giáo trình</a>
                        <a class="${page === "sell.html" ? "is-active" : ""}" href="sell.html">Đăng bán</a>
                    </div>
                    <div class="nav-actions">
                        ${authenticated
                            ? `<button class="notification-button" type="button" data-notifications aria-label="Thông báo">🔔</button><a class="nav-user" href="profile.html"><span class="avatar" aria-hidden="true">${userName.slice(0, 2).toUpperCase()}</span><span>${userName}</span></a>
                               <button class="button button-outline" type="button" data-logout>Đăng xuất</button>`
                            : `<a href="login.html">Đăng nhập</a><a class="button button-primary" href="register.html">Đăng ký</a>`}
                    </div>
                </div>
            </nav>`;
    }

    if (footer) {
        footer.innerHTML = `
            <div class="page-shell footer-grid">
                <div>
                    <h2>PASSBOOK</h2>
                    <p>Mua bán giáo trình trong cùng trường.</p>
                </div>
                <div>
                    <h3>Liên kết</h3>
                    <div class="footer-links">
                        <a href="index.html">Trang chủ</a>
                        <a href="books.html">Tìm giáo trình</a>
                        <a href="sell.html">Đăng bán</a>
                    </div>
                </div>
                <div>
                    <h3>Hỗ trợ</h3>
                    <div class="footer-links">
                        <a href="index.html#guide">Hướng dẫn</a>
                        <a href="index.html#terms">Điều khoản</a>
                        <a href="index.html#privacy">Chính sách</a>
                    </div>
                </div>
            </div>
            <div class="footer-bottom">
                <div class="page-shell">© 2026 PassBook</div>
            </div>`;
    }

    const toggle = document.querySelector(".nav-toggle");
    const menu = document.querySelector(".nav-menu");
    toggle?.addEventListener("click", () => {
        const isOpen = menu.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", String(isOpen));
    });

    document.querySelector("[data-logout]")?.addEventListener("click", () => {
        clearAuth();
        window.location.reload();
    });
    setupNotifications();
}

document.addEventListener("DOMContentLoaded", () => {
    document.documentElement.classList.add("js-ready");
    renderSiteChrome();
    if (getAccessToken()) {
        api.get("/auth/authenticated-user/")
            .then((data) => {
                localStorage.setItem("currentUser", JSON.stringify(data.user));
                localStorage.setItem("isLoggedIn", "true");
                renderSiteChrome();
            })
            .catch(() => {
                clearAuth();
                renderSiteChrome();
            });
    }
    renderHomepage();
});
