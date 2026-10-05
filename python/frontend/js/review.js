document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-review-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const orderId = new URLSearchParams(location.search).get("order_id");
    const orderSummary = page.querySelector("[data-review-order]");
    const form = page.querySelector("[data-review-form]");
    const ratingInput = form.elements.rating;
    const comment = form.elements.comment;
    const error = page.querySelector("[data-review-error]");
    const history = page.querySelector("[data-review-history]");
    let order;

    const renderReviews = (reviews) => {
        history.replaceChildren();
        const heading = document.createElement("h2");
        heading.textContent = "Đánh giá giao dịch";
        history.append(heading);
        if (!reviews.length) {
            history.append(PassbookCommonComponents.emptyStateElement("Chưa có đánh giá."));
            return;
        }
        reviews.forEach((review) => {
            const card = document.createElement("article");
            card.className = "review-card";
            const title = document.createElement("strong");
            title.textContent = `${"★".repeat(review.rating)}${"☆".repeat(5 - review.rating)} · ${review.reviewer?.name || "Người dùng"}`;
            const text = document.createElement("p");
            text.textContent = review.comment || "Không có nhận xét.";
            const date = document.createElement("time");
            date.dateTime = review.created_at;
            date.textContent = new Date(review.created_at).toLocaleString("vi-VN");
            card.append(title, text, date);
            history.append(card);
        });
    };

    const updateStars = (rating) => {
        ratingInput.value = String(rating || "");
        form.querySelectorAll("[data-rating]").forEach((button) => {
            const selected = Number(button.dataset.rating) <= rating;
            button.textContent = selected ? "★" : "☆";
            button.setAttribute("aria-pressed", String(Number(button.dataset.rating) === rating));
        });
        form.querySelector("[data-rating-value]").textContent = rating
            ? `${rating} / 5 sao`
            : "Chọn số sao";
    };
    form.querySelectorAll("[data-rating]").forEach((button) =>
        button.addEventListener("click", () => updateStars(Number(button.dataset.rating))),
    );
    form.querySelector("[data-rating-options]").addEventListener("keydown", (event) => {
        const current = Number(event.target.dataset.rating);
        const next = event.key === "ArrowRight" || event.key === "ArrowUp"
            ? Math.min(5, current + 1)
            : event.key === "ArrowLeft" || event.key === "ArrowDown"
                ? Math.max(1, current - 1)
                : event.key === "Home"
                    ? 1
                    : event.key === "End"
                        ? 5
                        : null;
        if (next === null) return;
        event.preventDefault();
        const target = form.querySelector(`[data-rating="${next}"]`);
        target.focus();
        updateStars(next);
    });

    const load = async () => {
        if (!orderId) {
            orderSummary.replaceChildren(PassbookCommonComponents.emptyStateElement("Thiếu mã đơn hàng."));
            return;
        }
        try {
            order = await OrdersAPI.get(orderId);
            const title = document.createElement("strong");
            title.textContent = `${order.order_code} · ${(order.items || []).map((item) => item.title).join(", ")}`;
            const status = document.createElement("p");
            status.textContent = `Trạng thái giao dịch: ${order.status}`;
            orderSummary.replaceChildren(title, status);
            renderReviews(order.reviews || []);
            if (order.status !== "COMPLETED") {
                orderSummary.append(PassbookCommonComponents.emptyStateElement(
                    "Đơn hàng chưa đủ điều kiện đánh giá.",
                    "Bạn chỉ có thể gửi đánh giá sau khi giao dịch hoàn tất.",
                ));
                return;
            }
            const currentUserId = Number(PassbookAuth.getCurrentUser()?.id);
            const existing = (order.reviews || []).find(
                (review) => Number(review.reviewer?.id) === currentUserId,
            );
            if (existing) {
                updateStars(existing.rating);
                comment.value = existing.comment || "";
                form.querySelector("[data-review-submit]").textContent = "Cập nhật đánh giá";
                form.querySelector("[data-review-editing]").hidden = false;
            }
            form.hidden = false;
        } catch (requestError) {
            orderSummary.replaceChildren(PassbookCommonComponents.emptyStateElement(
                "Không thể kiểm tra điều kiện đánh giá.",
                requestError.message,
            ));
        }
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const rating = Number(ratingInput.value);
        if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
            error.textContent = "Vui lòng chọn từ 1 đến 5 sao.";
            return;
        }
        error.textContent = "";
        const submit = form.querySelector("button[type=submit]");
        submit.disabled = true;
        try {
            await OrdersAPI.createReview(order.id, {rating, comment: comment.value.trim()});
            order = await OrdersAPI.get(order.id);
            renderReviews(order.reviews || []);
            form.querySelector("[data-review-submit]").textContent = "Cập nhật đánh giá";
            form.querySelector("[data-review-editing]").hidden = false;
            showToast("Đánh giá đã được lưu.");
        } catch (requestError) {
            error.textContent = requestError.message;
        } finally {
            submit.disabled = false;
        }
    });
    void load();
});
