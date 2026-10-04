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

    function emptyState(label, detail = "") {
        return `<div class="empty-state"><strong>${escapeHtml(label)}</strong>${detail ? `<span>${escapeHtml(detail)}</span>` : ""}</div>`;
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
        const avatar = escapeHtml(userName.slice(0, 2).toUpperCase());
        const basePath = global.location.pathname.split("/").includes("admin") ? "../" : "";
        const brand = page === "books.html"
            ? '<span class="brand__icon" aria-hidden="true">📚</span><span class="brand__word">PASS<span>BOOK</span><small>student book market</small></span>'
            : '<span class="brand__icon" aria-hidden="true">📚</span><span>PASSBOOK</span>';
        return `<nav class="navbar" aria-label="Điều hướng chính">
            <a class="brand" href="${basePath}index.html">${brand}</a>
            <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">
                <span aria-hidden="true">☰</span><span class="sr-only">Mở menu</span>
            </button>
            <div class="nav-menu" id="site-nav">
                <div class="nav-links">
                    <a class="${page === "index.html" ? "is-active" : ""}" href="${basePath}index.html">Trang chủ</a>
                    <a class="${page === "books.html" ? "is-active" : ""}" href="${basePath}books.html">Tìm giáo trình</a>
                    <a class="${page === "sell.html" ? "is-active" : ""}" href="${basePath}sell.html">Đăng bán</a>
                </div>
                <form class="nav-search" data-nav-search>
                    <label class="sr-only" for="nav-search-input">Tìm kiếm sách</label>
                    <span aria-hidden="true">⌕</span>
                    <input id="nav-search-input" name="q" type="search" placeholder="Tìm sách..." autocomplete="off">
                    <button type="submit" aria-label="Tìm kiếm">→</button>
                </form>
                <div class="nav-actions">
                    ${authenticated
                        ? `<button class="notification-button" type="button" data-notifications aria-label="Thông báo">🔔<span data-notification-count hidden></span></button><a class="nav-user" href="${basePath}profile.html"><span class="avatar" aria-hidden="true">${avatar}</span><span>${escapeHtml(userName)}</span></a><a href="${basePath}workspace.html">Giao dịch</a><a href="${basePath}requests.html">Yêu cầu sách</a>${user?.role?.toUpperCase() === "ADMIN" ? `<a href="${basePath}admin/">Quản trị</a>` : ""}<button class="button button-outline" type="button" data-logout>Đăng xuất</button>`
                        : `<a href="${basePath}login.html">Đăng nhập</a><a class="button button-primary" href="${basePath}register.html">Đăng ký</a>`}
                </div>
            </div>
        </nav>`;
    }

    function siteFooter() {
        const basePath = global.location.pathname.split("/").includes("admin") ? "../" : "";
        return `<div class="page-shell footer-grid">
            <div><h2>PASSBOOK</h2><p>Mua bán giáo trình trong cùng trường.</p></div>
            <div><h3>Liên kết</h3><div class="footer-links">
                <a href="${basePath}index.html">Trang chủ</a><a href="${basePath}books.html">Tìm giáo trình</a><a href="${basePath}sell.html">Đăng bán</a>
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
        emptyState,
        pagination,
        confirmAction,
        notificationItem,
        siteHeader,
        siteFooter,
    });
})(window);
