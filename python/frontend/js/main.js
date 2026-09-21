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

function fallbackBookImage(book) {
    const subject = book.subject?.name || book.subject || "PASSBOOK";
    const encoded = encodeURIComponent(subject.slice(0, 24));
    return `https://placehold.co/640x860/f0e5d7/263b4a?text=${encoded}`;
}

function renderBookCard(book) {
    const image = Array.isArray(book.images)
        ? (book.images.find((item) => item.is_primary) || book.images[0])
        : null;
    const title = escapeHtml(book.title || "Giáo trình");
    const subject = escapeHtml(book.subject?.name || book.subject || "Giáo trình");
    const code = escapeHtml(book.subject?.code || book.subjectCode || "");
    const seller = escapeHtml(book.seller?.name || "Người bán");
    const location = escapeHtml(book.pickup_location?.name || "");
    const condition = escapeHtml(book.condition_label || book.condition_status || book.condition || "Đang cập nhật");
    const statusLabel = {sold: "Đã bán", reserved: "Đã giữ", hidden: "Đã ẩn", deleted: "Đã xóa"}[book.status];
    const badge = statusLabel
        ? `<span class="badge badge-danger">${statusLabel}</span>`
        : `<span class="badge badge-success">${condition}</span>`;
    const rawImageUrl = image?.image_url || (Array.isArray(book.images) ? book.images[0]?.image_url : "");
    const imageUrl = rawImageUrl ? safeImageUrl(rawImageUrl) : fallbackBookImage(book);
    const isFavorite = isFavoriteBook(book.id);
    return `<article class="book-card">
        <a class="book-card__cover-link" href="book-detail.html?id=${encodeURIComponent(book.id)}" aria-label="Xem ${title}">
            <div class="book-card__cover">
                <img class="book-card__image" src="${imageUrl}" data-fallback="${fallbackBookImage(book)}" alt="Ảnh bìa ${title}" loading="lazy">
                <button class="favorite-button ${isFavorite ? "is-favorite" : ""}" type="button" data-favorite="${book.id}" aria-label="${isFavorite ? "Bỏ lưu" : "Lưu"} ${title}" aria-pressed="${isFavorite}">${isFavorite ? "♥" : "♡"}</button>
            </div>
        </a>
        <div class="book-card__body">
            ${badge}
            <h3 class="book-card__title"><a href="book-detail.html?id=${encodeURIComponent(book.id)}">${title}</a></h3>
            <p class="book-card__subject">${subject}${code ? ` · ${code}` : ""}</p>
            <strong class="price">${formatPrice(Number(book.price) || 0)}</strong>
            <div class="seller-line"><span>${seller}</span>${location ? `<span class="book-card__location"> · ${location}</span>` : ""}</div>
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
    Promise.all([api.get("/books/?page_size=24"), loadFavoriteBookIds()]).then(([data]) => {
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
    const user = JSON.parse(localStorage.getItem("currentUser") || "{}");
    const userName = user.name || "Nguyễn Lâm";
    const header = document.querySelector("[data-site-header]");
    const footer = document.querySelector("[data-site-footer]");

    if (header) {
        const catalogBrand = page === "books.html"
            ? `<span class="brand__icon" aria-hidden="true">📚</span><span class="brand__word">PASS<span>BOOK</span><small>student book market</small></span>`
            : `<span class="brand__icon" aria-hidden="true">📚</span><span>PASSBOOK</span>`;
        header.innerHTML = `
            <nav class="navbar" aria-label="Điều hướng chính">
                <a class="brand" href="index.html">
                    ${catalogBrand}
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
                    <form class="nav-search" data-nav-search>
                        <label class="sr-only" for="nav-search-input">Tìm kiếm sách</label>
                        <span aria-hidden="true">⌕</span>
                        <input id="nav-search-input" name="q" type="search" placeholder="Tìm sách..." autocomplete="off">
                        <button type="submit" aria-label="Tìm kiếm">→</button>
                    </form>
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
    document.querySelector("[data-nav-search]")?.addEventListener("submit", (event) => {
        event.preventDefault();
        const query = new FormData(event.currentTarget).get("q")?.toString().trim();
        window.location.href = query ? `books.html?q=${encodeURIComponent(query)}` : "books.html";
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
