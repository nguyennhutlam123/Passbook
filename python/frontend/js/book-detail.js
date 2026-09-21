document.addEventListener("DOMContentLoaded", async () => {
    const container = document.querySelector("[data-book-detail]");
    if (!container) return;
    const id = new URLSearchParams(location.search).get("id");
    if (!id) {
        container.innerHTML = '<div class="empty-state"><strong>Không tìm thấy mã giáo trình.</strong><a class="button button-primary" href="books.html">Về danh sách</a></div>';
        return;
    }
    try {
        const [book] = await Promise.all([api.get(`/books/${id}/`), loadFavoriteBookIds()]);
        const images = book.images || [];
        const mainImage = container.querySelector("[data-detail-main-image]");
        mainImage.src = safeImageUrl((images.find((item) => item.is_primary) || images[0])?.image_url);
        mainImage.alt = `Ảnh ${book.title}`;
        mainImage.addEventListener("error", () => {
            mainImage.src = `https://placehold.co/640x860/f0e5d7/263b4a?text=${encodeURIComponent(book.subject?.name || "PASSBOOK")}`;
        }, {once: true});
        container.querySelector("[data-detail-thumbs]").innerHTML = images.map((image, index) => `<button class="gallery-thumb ${index === 0 ? "is-active" : ""}" type="button" data-image="${safeImageUrl(image.image_url)}"><img src="${safeImageUrl(image.image_url)}" alt="Ảnh ${index + 1}"></button>`).join("");
        container.querySelectorAll("[data-image]").forEach((thumb) => thumb.addEventListener("click", () => { mainImage.src = thumb.dataset.image; }));
        container.querySelector("[data-detail-status]").innerHTML = `<span class="badge badge-success">${book.condition_label || book.condition_status}</span>`;
        container.querySelector("[data-detail-title]").textContent = book.title;
        const favoriteButton = document.createElement("button");
        favoriteButton.className = "button button-outline";
        favoriteButton.type = "button";
        const favorite = isFavoriteBook(book.id);
        favoriteButton.className = `button button-outline ${favorite ? "is-favorite" : ""}`;
        favoriteButton.setAttribute("aria-pressed", String(favorite));
        favoriteButton.textContent = favorite ? "♥ Đã lưu" : "♡ Lưu giáo trình";
        favoriteButton.dataset.favorite = String(book.id);
        favoriteButton.addEventListener("click", () => toggleFavorite(book.id, favoriteButton));
        container.querySelector("[data-detail-title]").after(favoriteButton);
        container.querySelector("[data-detail-price]").textContent = formatPrice(Number(book.price));
        container.querySelector("[data-detail-meta]").innerHTML = `<div><dt>Môn học</dt><dd>${book.subject?.name || "—"}</dd></div><div><dt>Mã môn</dt><dd>${book.subject?.code || "—"}</dd></div><div><dt>Danh mục</dt><dd>${book.category?.name || "—"}</dd></div><div><dt>Năm xuất bản</dt><dd>${book.publication_year || "—"}</dd></div>`;
        container.querySelector("[data-detail-description]").textContent = book.description || "Chưa có mô tả.";
        container.querySelector("[data-detail-seller]").innerHTML = `<div class="seller-line"><span class="avatar">${(book.seller?.name || "?").slice(0, 2).toUpperCase()}</span><strong>${book.seller?.name || "Người bán"}</strong></div>`;
        container.querySelector("[data-detail-location]").textContent = book.pickup_location?.name || "—";
        const actions = container.querySelector("[data-detail-actions]");
        actions.innerHTML = "";
        if (book.status === "available" && Number(book.seller?.id) !== Number(JSON.parse(localStorage.getItem("currentUser") || "{}").id)) {
            const messageButton = document.createElement("button");
            messageButton.className = "button button-primary";
            messageButton.type = "button";
            messageButton.textContent = "Nhắn tin người bán";
            messageButton.addEventListener("click", async () => {
                if (!isLoggedIn()) {
                    window.location.href = "login.html";
                    return;
                }
                try {
                    const conversation = await api.post(`/books/${book.id}/conversations/`, {});
                    await openConversationModal(conversation.id);
                } catch (error) {
                    showToast(error.message);
                }
            });
            actions.appendChild(messageButton);
        }
        const reportButton = document.createElement("button");
        reportButton.className = "button button-outline";
        reportButton.type = "button";
        reportButton.textContent = "Báo cáo";
        reportButton.addEventListener("click", () => {
            if (!isLoggedIn()) {
                window.location.href = "login.html";
                return;
            }
            showModal(`<form data-report-form><button class="modal-close" type="button" data-modal-close>Đóng</button><h2>Báo cáo giáo trình</h2><label class="form-label" for="report-reason">Lý do</label><input id="report-reason" required maxlength="255"><label class="form-label" for="report-description">Mô tả</label><textarea id="report-description" required maxlength="5000"></textarea><div class="modal-actions"><button class="button button-primary" type="submit">Gửi báo cáo</button></div></form>`);
            document.querySelector("[data-report-form]").addEventListener("submit", async (event) => {
                event.preventDefault();
                const reason = document.querySelector("#report-reason").value.trim();
                const description = document.querySelector("#report-description").value.trim();
                if (!reason || !description) return;
                try {
                    await api.post("/reports/", {book_id: book.id, reason, description});
                    closeModal();
                    showToast("Đã gửi báo cáo.");
                } catch (error) {
                    showToast(error.message);
                }
            });
        });
        actions.appendChild(reportButton);
        container.querySelector("[data-contact-seller]")?.remove();
    } catch (error) {
        container.innerHTML = `<div class="empty-state"><strong>${error.message}</strong><a class="button button-primary" href="books.html">Về danh sách</a></div>`;
    }
});
