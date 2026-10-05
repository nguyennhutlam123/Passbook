(function (global) {
    "use strict";

    function escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, (character) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[character]));
    }

    function statusBadge(status, label = status) {
        const safeStatus = String(status || "unknown").toLowerCase().replace(/[^a-z0-9_-]/g, "");
        return `<span class="badge badge-status badge-status--${safeStatus}">${escapeHtml(label || "—")}</span>`;
    }

    function loadingState(label = "Đang tải...") {
        return `<p class="loading-state" role="status">${escapeHtml(label)}</p>`;
    }

    function loadingStateElement(label = "Đang tải...") {
        const element = document.createElement("p");
        element.className = "loading-state";
        element.setAttribute("role", "status");
        element.textContent = label;
        return element;
    }

    function emptyState(label, detail = "") {
        return `<div class="empty-state"><strong>${escapeHtml(label)}</strong>${detail ? `<span>${escapeHtml(detail)}</span>` : ""}</div>`;
    }

    function emptyStateElement(label, detail = "") {
        const element = document.createElement("div");
        element.className = "empty-state";
        const heading = document.createElement("strong");
        heading.textContent = label;
        element.append(heading);
        if (detail) {
            const description = document.createElement("span");
            description.textContent = detail;
            element.append(description);
        }
        return element;
    }

    function pagination({previous, next, onPrevious, onNext}) {
        const controls = document.createElement("div");
        controls.className = "component-pagination";
        if (previous) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "button button-outline";
            button.textContent = "Trước";
            button.addEventListener("click", onPrevious);
            controls.append(button);
        }
        if (next) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "button button-outline";
            button.textContent = "Sau";
            button.addEventListener("click", onNext);
            controls.append(button);
        }
        return controls;
    }

    function confirmAction(message) {
        return global.confirm(message);
    }

    function notificationItem(item) {
        const button = document.createElement("button");
        button.className = `notification-item ${item.is_read ? "" : "is-unread"}`;
        button.type = "button";
        const title = document.createElement("strong");
        title.textContent = item.title || "";
        const content = document.createElement("span");
        content.textContent = item.content || "";
        const time = document.createElement("time");
        time.textContent = new Date(item.created_at).toLocaleString("vi-VN");
        button.append(title, content, time);
        return button;
    }

    function siteHeader({page, authenticated, user}) {
        const userName = user?.name || "Người dùng";
        const basePath = global.location.pathname.split("/").includes("admin") ? "../" : "";
        const adminPage = global.location.pathname.split("/").includes("admin");
        const adminFile = global.location.pathname.split("/").pop();
        const brand = page === "books.html"
            ? '<span class="brand__icon" aria-hidden="true">📚</span><span class="brand__word">PASS<span>BOOK</span><small>student book market</small></span>'
            : '<span class="brand__icon" aria-hidden="true">📚</span><span>PASSBOOK</span>';
        const detailIsBorrow = page === "book-detail.html"
            && new URLSearchParams(global.location.search).get("listing_type") === "borrow";
        const moreIsActive = [
            "orders.html",
            "workspace.html",
            "cart.html",
            "borrow-tickets.html",
            "favorites.html",
            "notifications.html",
            "profile.html",
            "my-listings.html",
            "messages.html",
            "requests.html",
            "review.html",
        ].includes(page);
        const active = (file) => page === file
            || (file === "books.html" && page === "book-detail.html" && !detailIsBorrow)
            || (file === "borrow.html" && detailIsBorrow);
        const search = adminPage ? "" : `<form class="nav-search" data-nav-search>
            <label class="sr-only" for="nav-search-input">Tìm kiếm sách</label>
            <span aria-hidden="true">⌕</span>
            <input id="nav-search-input" name="q" type="search" placeholder="Tìm sách, môn học..." autocomplete="off" aria-label="Tìm kiếm sách">
            <button type="submit" aria-label="Tìm kiếm">→</button>
        </form>`;
        const publicLinks = `<a class="${active("index.html") ? "is-active" : ""}" href="${basePath}index.html">Trang chủ</a>
            <a class="${active("books.html") ? "is-active" : ""}" href="${basePath}books.html">Danh mục</a>
            <a class="${active("borrow.html") ? "is-active" : ""}" href="${basePath}borrow.html">Mượn sách</a>
            <a class="${active("sell.html") ? "is-active" : ""}" href="${basePath}sell.html">Đăng tin</a>`;
        const adminLinks = `<a class="${adminFile === "index.html" ? "is-active" : ""}" href="${basePath}admin/index.html">Dashboard</a>
            <a class="${adminFile === "users.html" ? "is-active" : ""}" href="${basePath}admin/users.html">Tài khoản</a>
            <a class="${adminFile === "reports.html" ? "is-active" : ""}" href="${basePath}admin/reports.html">Báo cáo</a>`;
        const cartLink = adminPage ? "" : `<a class="nav-icon-link nav-cart" href="${basePath}cart.html" aria-label="Giỏ hàng" title="Giỏ hàng">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h2l2.2 10.2a2 2 0 0 0 2 1.6h8.6a2 2 0 0 0 1.9-1.4L22 8H6"/><circle cx="10" cy="20" r="1"/><circle cx="18" cy="20" r="1"/></svg>
            <span class="nav-icon-link__label">Giỏ hàng</span>
        </a>`;
        const adminAccountActions = authenticated
            ? `<a class="nav-icon-link notification-button ${page === "notifications.html" ? "is-active" : ""}" href="${basePath}notifications.html" aria-label="Thông báo" ${page === "notifications.html" ? 'aria-current="page"' : ""}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg><span class="nav-icon-link__label">Thông báo</span></a>
                <details class="nav-more">
                    <summary aria-label="Tài khoản quản trị"><span class="nav-avatar" aria-hidden="true">${escapeHtml(userName.slice(0, 1).toUpperCase())}</span><span class="nav-profile-label">${escapeHtml(userName)}</span><span aria-hidden="true">⌄</span></summary>
                    <div class="nav-more__panel">
                        <a href="${basePath}admin/index.html">Dashboard</a>
                        <button class="nav-more__logout" type="button" data-logout>Đăng xuất</button>
                    </div>
                </details>`
            : `<a class="nav-login" href="${basePath}login.html">Đăng nhập</a>`;
        const customerAccountActions = authenticated
            ? `<div class="nav-shortcuts">
                <a class="nav-icon-link" href="${basePath}favorites.html" aria-label="Sách yêu thích" title="Sách yêu thích">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 8.7c0 5.1-8.8 10.2-8.8 10.2S3.2 13.8 3.2 8.7A4.2 4.2 0 0 1 11 6.1l1 1 1-1a4.2 4.2 0 0 1 7.8 2.6Z"/></svg><span class="nav-icon-link__label">Yêu thích</span>
                </a>
                <a class="nav-icon-link" href="${basePath}messages.html" aria-label="Tin nhắn" title="Tin nhắn">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5h16v12H9l-5 3v-15Z"/><path d="M8 10h8M8 13.5h5"/></svg><span class="nav-icon-link__label">Tin nhắn</span>
                </a>
                <a class="nav-icon-link notification-button ${page === "notifications.html" ? "is-active" : ""}" href="${basePath}notifications.html" aria-label="Thông báo" ${page === "notifications.html" ? 'aria-current="page"' : ""}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg><span class="nav-icon-link__label">Thông báo</span></a>
            </div>
            <details class="nav-more">
                <summary class="${moreIsActive ? "is-active" : ""}" aria-label="Tài khoản" ${moreIsActive ? 'aria-current="page"' : ""}>
                    <span class="nav-avatar" aria-hidden="true">${escapeHtml(userName.slice(0, 1).toUpperCase())}</span>
                    <span class="nav-profile-label">${escapeHtml(userName)}</span><span aria-hidden="true">⌄</span>
                </summary>
                <div class="nav-more__panel">
                    <a href="${basePath}profile.html">Hồ sơ</a>
                    <a href="${basePath}orders.html">Đơn hàng</a>
                    <a href="${basePath}borrow-tickets.html">Phiếu mượn</a>
                    <a href="${basePath}my-listings.html">Tin đăng của tôi</a>
                    <a href="${basePath}requests.html">Yêu cầu sách</a>
                    ${user?.role?.toUpperCase() === "ADMIN" ? `<a href="${basePath}admin/index.html">Quản trị</a>` : ""}
                    <button class="nav-more__logout" type="button" data-logout>Đăng xuất</button>
                </div>
            </details>`
            : `<a class="nav-login" href="${basePath}login.html">Đăng nhập</a>
                <a class="button button-primary nav-register" href="${basePath}register.html">Đăng ký</a>`;
        const accountActions = adminPage ? adminAccountActions : customerAccountActions;
        return `<nav class="navbar ${adminPage ? "navbar--admin" : ""}" aria-label="${adminPage ? "Điều hướng quản trị" : "Điều hướng chính"}">
            <a class="brand" href="${basePath}index.html">${brand}</a>
            ${search}
            ${cartLink}
            <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">
                <span aria-hidden="true">☰</span><span class="sr-only" data-nav-toggle-label>Mở menu</span>
            </button>
            <div class="nav-menu" id="site-nav">
                <div class="nav-links">${adminPage ? adminLinks : publicLinks}</div>
                <div class="nav-actions">${accountActions}</div>
            </div>
        </nav>`;
    }

    function siteFooter() {
        const basePath = global.location.pathname.split("/").includes("admin") ? "../" : "";
        return `<div class="page-shell footer-grid">
            <div><h2>PASSBOOK</h2><p>Mua bán giáo trình trong cùng trường.</p></div>
            <div><h3>Liên kết</h3><div class="footer-links">
                <a href="${basePath}index.html">Trang chủ</a><a href="${basePath}books.html">Mua giáo trình</a><a href="${basePath}borrow.html">Mượn giáo trình</a><a href="${basePath}sell.html">Đăng tin</a>
            </div></div>
            <div><h3>Hỗ trợ</h3><div class="footer-links">
                <a href="${basePath}index.html#guide">Hướng dẫn</a><a href="${basePath}index.html#terms">Điều khoản</a><a href="${basePath}index.html#privacy">Chính sách</a>
            </div></div>
        </div><div class="footer-bottom"><div class="page-shell">© 2026 PassBook</div></div>`;
    }

    global.PassbookCommonComponents = Object.freeze({
        escapeHtml,
        statusBadge,
        loadingState,
        loadingStateElement,
        emptyState,
        emptyStateElement,
        pagination,
        confirmAction,
        notificationItem,
        siteHeader,
        siteFooter,
    });
})(window);
