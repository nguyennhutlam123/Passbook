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

function openBorrowReservationDialog({bookId, listingId, title, onCreated}) {
    if (!PassbookGuards.requireAuth()) return;
    const formatLocalDateTime = (date) =>
        new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
            .toISOString()
            .slice(0, 16);
    const minimumExpiry = formatLocalDateTime(new Date());
    const defaultExpiry = formatLocalDateTime(
        new Date(Date.now() + 24 * 60 * 60 * 1000),
    );
    showModal(`<form data-borrow-reservation-form>
        <button class="modal-close" type="button" data-modal-close>Đóng</button>
        <h2>Đặt mượn sách</h2>
        <p><strong>${escapeHtml(title || "Giáo trình")}</strong></p>
        <label class="form-label" for="borrow-request-expiry">Yêu cầu có hiệu lực đến</label>
        <input class="form-control" id="borrow-request-expiry" name="expires_at" type="datetime-local" min="${minimumExpiry}" value="${defaultExpiry}" required>
        <p class="caption">Đây là thời hạn phản hồi yêu cầu theo schema; ngày bắt đầu và ngày trả chưa được lưu trong BookReservation.</p>
        <p class="form-error" data-borrow-reservation-error></p>
        <div class="modal-actions">
            <button class="button button-outline" type="button" data-modal-close>Hủy</button>
            <button class="button button-primary" type="submit">Xác nhận đặt mượn</button>
        </div>
    </form>`);
    const form = document.querySelector("[data-borrow-reservation-form]");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const submit = form.querySelector("button[type='submit']");
        const error = form.querySelector("[data-borrow-reservation-error]");
        submit.disabled = true;
        error.textContent = "";
        try {
            const expiresAt = new Date(
                new FormData(form).get("expires_at").toString(),
            );
            const reservation = await ReservationsAPI.create(bookId, {
                expires_at: expiresAt.toISOString(),
            });
            onCreated?.(reservation);
            showModal(`<section class="borrow-request-success">
                <button class="modal-close" type="button" data-modal-close>Đóng</button>
                <span class="success-panel__icon" aria-hidden="true">✓</span>
                <h2>Đã gửi yêu cầu mượn</h2>
                <p>Phiếu mượn #${Number(reservation.id)} đã được tạo.</p>
                <a class="button button-primary" href="borrow-tickets.html?reservation_id=${encodeURIComponent(reservation.id)}">Xem phiếu mượn mới</a>
            </section>`);
        } catch (requestError) {
            error.textContent = requestError.message;
        } finally {
            submit.disabled = false;
        }
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
                        window.location.href = notification.entity_type === "ORDER"
                            ? `orders.html?order_id=${encodeURIComponent(notification.reference_id)}`
                            : `book-detail.html?id=${encodeURIComponent(notification.reference_id)}`;
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
    const borrowGrid = document.querySelector("[data-home-borrow]");
    if (!newGrid || !collections || !borrowGrid) return;
    BooksAPI.lendListings({page_size: 4}).then((data) => {
        const listings = data.results || [];
        const books = listings.map((listing) => ({
            ...listing.book,
            id: listing.book_id,
            title: listing.title,
            description: listing.description,
            price: listing.rental_fee,
            condition_status: listing.condition_status,
            primary_image: listing.primary_image
                ? {image_url: listing.primary_image}
                : null,
            seller: listing.seller,
            listing_type: "BORROW",
            listing_id: listing.id,
            borrow_terms: listing.borrow_terms,
            deposit_amount: listing.deposit_amount,
        }));
        borrowGrid.replaceChildren(...(
            books.length
                ? books.map((book) => {
                    const wrapper = document.createElement("div");
                    wrapper.innerHTML = renderBookCard(book);
                    return wrapper.firstElementChild;
                })
                : [PassbookCommonComponents.emptyStateElement(
                    "Chưa có sách cho mượn.",
                    "Quay lại sau để xem các tin mượn mới.",
                )]
        ));
        attachImageFallbacks(borrowGrid);
    }).catch((error) => {
        borrowGrid.replaceChildren(PassbookCommonComponents.emptyStateElement(
            "Không thể tải sách cho mượn.",
            error.message,
        ));
    });
    const categorySections = [
        {name: "Tiểu thuyết", slug: "tieu-thuyet", description: "Những câu chuyện và thế giới giàu cảm xúc.", tone: "blue"},
        {name: "Thơ", slug: "tho", description: "Tuyển tập thơ và những vần điệu đáng nhớ.", tone: "orange"},
        {name: "Kịch", slug: "kich", description: "Tác phẩm sân khấu và kịch bản.", tone: "green"},
        {name: "Sách giáo khoa", slug: "sach-giao-khoa", description: "Sách học tập theo chương trình giáo dục.", tone: "purple"},
        {name: "Giáo trình", slug: "giao-trinh", description: "Giáo trình và sách chuyên ngành.", tone: "pink"},
        {name: "Tài liệu", slug: "tai-lieu", description: "Tài liệu tham khảo và học tập.", tone: "blue"},
        {name: "Truyện tranh", slug: "truyen-tranh", description: "Truyện tranh cho nhiều lứa tuổi.", tone: "orange"},
    ];
    const renderCollection = (section, books) => {
        if (!books.length) return "";
        const query = encodeURIComponent(section.slug);
        return `<section class="page-shell collection-section collection-section--${section.tone}" aria-labelledby="collection-${section.slug}">
            <div class="collection-heading"><div><span class="eyebrow">${section.name}</span><h2 id="collection-${section.slug}">${section.name}</h2><p>${section.description}</p></div><a class="text-link" href="books.html?category_slug=${query}">Xem tất cả <span>→</span></a></div>
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
        collections.innerHTML = categorySections.map((section) => renderCollection(
            section,
            books.filter((book) => book.category?.name === section.name),
        )).join("");
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
    document.querySelector(".nav-more")?.addEventListener("click", (event) => {
        if (event.target.closest("a, button")) event.currentTarget.open = false;
    });
    document.addEventListener("click", (event) => {
        const details = document.querySelector(".nav-more");
        if (details?.open && !details.contains(event.target)) details.open = false;
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
