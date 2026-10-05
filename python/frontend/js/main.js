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
let navOutsideClickRegistered = false;

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

async function addBorrowListingToCart(listingId, button) {
    if (!PassbookGuards.requireAuth()) return;
    if (button) button.disabled = true;
    try {
        const id = Number(listingId);
        await OrdersAPI.addCartItem({listing_type: "BORROW", listing_id: id});
        window.location.assign(`cart.html?buy_now=${encodeURIComponent(id)}`);
    } catch (error) {
        showToast(error.message);
    } finally {
        if (button) button.disabled = false;
    }
}

async function addSaleListingToCart(listingId, button, {buyNow = false} = {}) {
    if (!PassbookGuards.requireAuth()) return;
    const id = Number(listingId);
    if (!Number.isSafeInteger(id) || id < 1) {
        showToast("Không tìm thấy tin bán hợp lệ cho sách này.");
        return;
    }
    if (button) button.disabled = true;
    try {
        await OrdersAPI.addCartItem({listing_type: "SALE", listing_id: id});
        if (buyNow) {
            window.location.assign(`cart.html?buy_now=${encodeURIComponent(id)}`);
            return;
        }
        showToast("Đã thêm sách vào giỏ hàng.");
    } catch (error) {
        showToast(error.message);
    } finally {
        if (button) button.disabled = false;
    }
}

function bindSaleButtons(root = document) {
    root.querySelectorAll("[data-sale-add-to-cart]").forEach((button) => {
        button.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            void addSaleListingToCart(button.dataset.saleAddToCart, button);
        });
    });
}

function bindBorrowButtons(root = document) {
    root.querySelectorAll("[data-borrow-request]").forEach((button) => {
        button.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            void addBorrowListingToCart(button.dataset.borrowRequest, button);
        });
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

function fallbackBookImage(book) {
    const subject = book.subject?.name || book.subject || "PASSBOOK";
    const encoded = encodeURIComponent(subject.slice(0, 24));
    return `https://placehold.co/640x860/f0e5d7/263b4a?text=${encoded}`;
}

function renderBookCard(book) {
    return PassbookBookComponents.bookCard(book, {favorite: isFavoriteBook(book.id)});
}

function syncFavoriteButtons(root) {
    root.querySelectorAll("[data-favorite]").forEach((button) => {
        const favorite = isFavoriteBook(button.dataset.favorite);
        const title = button.getAttribute("aria-label").replace(/^(Lưu|Bỏ lưu) /, "");
        button.classList.toggle("is-favorite", favorite);
        button.setAttribute("aria-pressed", String(favorite));
        button.setAttribute("aria-label", `${favorite ? "Bỏ lưu" : "Lưu"} ${title}`);
        button.textContent = favorite ? "♥" : "♡";
        button.disabled = false;
    });
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
    const borrowGrid = document.querySelector("[data-home-borrow]");
    if (!newGrid || !borrowGrid) return;
    const favoritesPromise = isLoggedIn()
        ? loadFavoriteBookIds().then(() => null, (error) => error)
        : Promise.resolve(null);

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
        bindBorrowButtons(borrowGrid);
        attachImageFallbacks(borrowGrid);
    }).catch((error) => {
        const failure = PassbookCommonComponents.emptyStateElement(
            "Không thể tải sách cho mượn.",
            "Vui lòng thử lại sau hoặc xem các tin đăng mượn sách.",
        );
        const browse = document.createElement("a");
        browse.className = "button button-outline";
        browse.href = "borrow.html";
        browse.textContent = "Xem sách cho mượn";
        failure.append(browse);
        borrowGrid.replaceChildren(failure);
        console.error("Không thể tải sách cho mượn trên trang chủ.", error);
    });

    BooksAPI.list({page_size: 4, sort: "newest"}).then((data) => {
        const books = data.results || [];
        if (books.length) {
            newGrid.innerHTML = books.map(renderBookCard).join("");
            bindSaleButtons(newGrid);
            if (isLoggedIn()) {
                newGrid.querySelectorAll("[data-favorite]").forEach((button) => {
                    button.disabled = true;
                });
            }
        } else {
            const empty = PassbookCommonComponents.emptyStateElement(
                "Chưa có sách mới đăng.",
                "Khám phá danh mục để tìm cuốn sách phù hợp.",
            );
            const browse = document.createElement("a");
            browse.className = "button button-outline";
            browse.href = "books.html";
            browse.textContent = "Khám phá sách";
            empty.append(browse);
            newGrid.replaceChildren(empty);
        }
        bindFavoriteButtons(newGrid);
        attachImageFallbacks(newGrid);
        if (isLoggedIn()) {
            favoritesPromise.then((error) => {
                if (error) {
                    newGrid.querySelectorAll("[data-favorite]").forEach((button) => {
                        button.disabled = false;
                    });
                    showToast(error.message);
                    return;
                }
                syncFavoriteButtons(newGrid);
            });
        }
    }).catch((error) => {
        const failure = PassbookCommonComponents.emptyStateElement(
            "Không thể tải sách mới.",
            "Kiểm tra kết nối rồi thử tải lại.",
        );
        const retry = document.createElement("button");
        retry.className = "button button-outline";
        retry.type = "button";
        retry.textContent = "Thử lại";
        retry.addEventListener("click", () => window.location.reload());
        failure.append(retry);
        newGrid.replaceChildren(failure);
        console.error("Không thể tải sách mới trên trang chủ.", error);
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
        const label = toggle.querySelector("[data-nav-toggle-label]");
        if (label) label.textContent = isOpen ? "Đóng menu" : "Mở menu";
    });
    document.querySelector(".nav-more")?.addEventListener("click", (event) => {
        if (event.target.closest("a, button")) event.currentTarget.open = false;
    });
    if (!navOutsideClickRegistered) {
        document.addEventListener("click", (event) => {
            const details = document.querySelector(".nav-more");
            if (details?.open && !details.contains(event.target)) details.open = false;
            const navMenu = document.querySelector(".nav-menu");
            const navToggle = document.querySelector(".nav-toggle");
            if (navMenu?.classList.contains("is-open")
                && !navMenu.contains(event.target)
                && !navToggle?.contains(event.target)) {
                navMenu.classList.remove("is-open");
                navToggle.setAttribute("aria-expanded", "false");
                const label = navToggle.querySelector("[data-nav-toggle-label]");
                if (label) label.textContent = "Mở menu";
            }
        });
        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape") return;
            document.querySelector(".nav-more")?.removeAttribute("open");
            const navMenu = document.querySelector(".nav-menu");
            const navToggle = document.querySelector(".nav-toggle");
            navMenu?.classList.remove("is-open");
            navToggle?.setAttribute("aria-expanded", "false");
            const label = navToggle?.querySelector("[data-nav-toggle-label]");
            if (label) label.textContent = "Mở menu";
        });
        navOutsideClickRegistered = true;
    }

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
}

document.addEventListener("DOMContentLoaded", () => {
    document.documentElement.classList.add("js-ready");
    const headerIdentity = (user) => JSON.stringify([
        user?.name || "",
        String(user?.role || "").toUpperCase(),
    ]);
    const initialHeaderIdentity = headerIdentity(PassbookAuth.getCurrentUser());
    renderSiteChrome();
    if (getAccessToken()) {
        AuthAPI.currentUser()
            .then((user) => {
                if (headerIdentity(user) !== initialHeaderIdentity) renderSiteChrome();
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
