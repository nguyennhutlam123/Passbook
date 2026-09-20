document.addEventListener("DOMContentLoaded", async () => {
    if (!document.querySelector("[data-profile-page]")) return;
    if (!isLoggedIn()) {
        window.location.href = "login.html";
        return;
    }
    const grid = document.querySelector("[data-profile-grid]");
    const empty = document.querySelector("[data-profile-empty]");
    const user = JSON.parse(localStorage.getItem("currentUser") || "{}");
    document.querySelector("[data-profile-name]").firstChild.textContent = `${user.name || "Người dùng"} `;
    document.querySelector("[data-profile-school]").textContent = user.email || "";
    let activeTab = "available";
    let books = [];

    const render = () => {
        const visible = activeTab === "saved"
            ? books
            : books.filter((book) => activeTab === "sold" ? book.status === "sold" : activeTab === "available" ? book.status === "available" : true);
        empty.hidden = visible.length > 0;
        grid.hidden = !visible.length;
        grid.innerHTML = visible.map((book) => `${renderBookCard(book)}<div class="listing-actions">
            <button class="button button-outline" data-edit="${book.id}">Sửa</button>
            <button class="button button-outline" data-delete="${book.id}">Xóa</button>
            ${book.status === "available" ? `<button class="button button-outline" data-sold="${book.id}">Đánh dấu đã bán</button>` : ""}
        </div>`).join("");
        grid.querySelectorAll("[data-edit]").forEach((button) => button.addEventListener("click", () => {
            const book = books.find((item) => item.id === Number(button.dataset.edit));
            localStorage.setItem("editingListing", JSON.stringify(book));
            window.location.href = "sell.html";
        }));
        grid.querySelectorAll("[data-delete]").forEach((button) => button.addEventListener("click", async () => {
            if (!window.confirm("Bạn có chắc muốn xóa tin đăng này?")) return;
            try { await api.delete(`/books/${button.dataset.delete}/`); await loadBooks(); showToast("Đã xóa tin đăng."); }
            catch (error) { showToast(error.message); }
        }));
        grid.querySelectorAll("[data-sold]").forEach((button) => button.addEventListener("click", async () => {
            try { await api.patch(`/books/${button.dataset.sold}/sold/`, {}); await loadBooks(); showToast("Đã đánh dấu đã bán."); }
            catch (error) { showToast(error.message); }
        }));
        bindFavoriteButtons(grid);
    };
    const loadBooks = async () => {
        try {
            const data = await api.get("/my-books/?page_size=50");
            books = data.results;
            render();
        } catch (error) { grid.innerHTML = `<div class="empty-state">${error.message}</div>`; }
    };
    document.querySelectorAll("[data-profile-tab]").forEach((tab) => tab.addEventListener("click", async () => {
        activeTab = tab.dataset.profileTab;
        document.querySelectorAll("[data-profile-tab]").forEach((item) => {
            item.className = item === tab ? "button is-active" : "button button-outline";
            item.setAttribute("aria-selected", String(item === tab));
        });
        if (activeTab === "saved") {
            try {
                const data = await api.get("/favorites/?page_size=50");
                books = data.results.map((item) => item.book);
            } catch (error) { showToast(error.message); }
        } else await loadBooks();
        render();
    }));
    await loadFavoriteBookIds();
    await loadBooks();
    const conversationList = document.querySelector("[data-conversation-list]");
    try {
        const conversations = await api.get("/conversations/");
        conversationList.innerHTML = conversations.length ? conversations.map((conversation) => `<button class="conversation-list-item" type="button" data-conversation-id="${conversation.id}"><strong>${escapeHtml(conversation.book.title)}</strong><span>${escapeHtml(conversation.buyer.name)} ↔ ${escapeHtml(conversation.seller.name)}</span><time>${new Date(conversation.updated_at).toLocaleString("vi-VN")}</time></button>`).join("") : '<p class="caption">Chưa có cuộc hội thoại.</p>';
        conversationList.querySelectorAll("[data-conversation-id]").forEach((item) => item.addEventListener("click", () => openConversationModal(item.dataset.conversationId)));
    } catch (error) {
        conversationList.innerHTML = `<p class="caption">${escapeHtml(error.message)}</p>`;
    }
    const reportList = document.querySelector("[data-report-list]");
    try {
        const reports = await api.get("/reports/my/?page_size=50");
        reportList.innerHTML = reports.results?.length ? reports.results.map((report) => `<article class="report-item"><strong>${escapeHtml(report.reason)}</strong><span>Sách #${report.book_id || "—"} · ${escapeHtml(report.status)}</span><time>${new Date(report.created_at).toLocaleString("vi-VN")}</time></article>`).join("") : '<p class="caption">Chưa có báo cáo.</p>';
    } catch (error) {
        reportList.innerHTML = `<p class="caption">${escapeHtml(error.message)}</p>`;
    }
});
