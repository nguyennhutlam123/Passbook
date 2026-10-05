(function (global) {
    "use strict";

    function cartItem(item, {onRemove, onBuy} = {}) {
        const card = document.createElement("article");
        card.className = "report-item";
        card.dataset.cartItem = String(item.id);
        card.dataset.listingId = String(item.listing_id);
        card.dataset.listingType = item.listing_type || "";
        const cover = document.createElement("div");
        cover.className = "cart-item-cover";
        if (item.primary_image?.image_url) {
            const image = document.createElement("img");
            image.src = item.primary_image.image_url;
            image.alt = `Ảnh ${item.title || "sách"}`;
            image.loading = "lazy";
            cover.append(image);
        } else {
            cover.setAttribute("role", "img");
            cover.setAttribute("aria-label", `Chưa có ảnh bìa cho ${item.title || "sách"}`);
            cover.textContent = "📘";
        }
        card.append(cover);
        const title = document.createElement("strong");
        title.textContent = item.title || "Sách";
        const meta = document.createElement("span");
        meta.textContent = `${item.listing_type === "BORROW" ? "Mượn" : "Mua"} · ${global.formatPrice(Number(item.unit_price) || 0)} · SL 1`;
        const seller = document.createElement("span");
        seller.textContent = [
            item.seller?.name,
            item.condition_status,
        ].filter(Boolean).join(" · ");
        card.append(title, meta);
        if (item.listing_type === "BORROW") {
            const pricing = document.createElement("span");
            pricing.textContent = [
                `Phí mượn: ${global.formatPrice(Number(item.rental_fee) || 0)}`,
                Number(item.deposit_amount) > 0
                    ? `Đặt cọc: ${global.formatPrice(Number(item.deposit_amount))}`
                    : "Không cần đặt cọc",
                item.borrow_terms?.max_days
                    ? `Tối đa ${item.borrow_terms.max_days} ngày`
                    : "",
            ].filter(Boolean).join(" · ");
            card.append(pricing);
        }
        if (seller.textContent) card.append(seller);
        if (item.listing_type === "BORROW") {
            const dates = document.createElement("div");
            dates.className = "borrow-date-fields";
            const formatLocalDateTime = (date) =>
                new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
                    .toISOString()
                    .slice(0, 16);
            const start = new Date(Date.now() + 60 * 60 * 1000);
            const maxDays = Math.max(1, Number(item.borrow_terms?.max_days) || 7);
            const durationDays = Math.min(maxDays, 7);
            const end = new Date(start.getTime() + durationDays * 24 * 60 * 60 * 1000);
            for (const [key, label] of [
                ["expected_start_at", "Bắt đầu mượn"],
                ["expected_return_at", "Dự kiến trả"],
            ]) {
                const field = document.createElement("label");
                field.className = "form-group";
                field.textContent = label;
                const input = document.createElement("input");
                input.className = "form-control";
                input.type = "datetime-local";
                input.required = true;
                input.min = formatLocalDateTime(new Date());
                input.value = formatLocalDateTime(
                    key === "expected_start_at" ? start : end,
                );
                input.dataset.borrowListing = String(item.listing_id);
                input.dataset.cartItem = String(item.id);
                input.dataset.borrowField = key;
                field.append(input);
                dates.append(field);
            }
            const startInput = dates.querySelector('[data-borrow-field="expected_start_at"]');
            const returnInput = dates.querySelector('[data-borrow-field="expected_return_at"]');
            returnInput.min = startInput.value;
            startInput.addEventListener("change", () => {
                returnInput.min = startInput.value;
                if (returnInput.value <= startInput.value) {
                    const newReturn = new Date(
                        new Date(startInput.value).getTime() + 24 * 60 * 60 * 1000,
                    );
                    returnInput.value = formatLocalDateTime(newReturn);
                }
            });
            card.append(dates);
        }
        const remove = document.createElement("button");
        remove.className = "button button-outline";
        remove.type = "button";
        remove.textContent = "Xóa";
        remove.addEventListener("click", onRemove || (() => {}));
        const buy = document.createElement("button");
        buy.className = "button button-primary";
        buy.type = "button";
        buy.textContent = item.listing_type === "BORROW" ? "Đặt mượn" : "Mua";
        buy.dataset.cartBuy = "";
        buy.addEventListener("click", onBuy || (() => {}));
        card.append(remove, buy);
        return card;
    }

    function orderCard(order, {onDetails} = {}) {
        const card = document.createElement("article");
        card.className = "report-item";
        const title = document.createElement("strong");
        title.textContent = `${order.order_code} · ${order.order_type}${order.item_titles?.length ? ` · ${order.item_titles.join(", ")}` : ""}`;
        const status = document.createElement("span");
        const orderedAt = order.created_at
            ? new Date(order.created_at).toLocaleString("vi-VN")
            : "";
        status.textContent = [
            `Đơn: ${order.status}`,
            `Thanh toán: ${order.payment_status || "—"}`,
            `Tổng: ${global.formatPrice(Number(order.total_amount) || 0)}`,
            order.recipient_name ? `Người nhận: ${order.recipient_name}` : "",
            orderedAt,
        ].filter(Boolean).join(" · ");
        const details = document.createElement("button");
        details.className = "button button-outline";
        details.type = "button";
        details.textContent = "Chi tiết / thao tác";
        if (onDetails) details.addEventListener("click", onDetails);
        card.append(title, status, details);
        return {element: card, detailsButton: details};
    }

    global.PassbookCommerceComponents = Object.freeze({cartItem, orderCard});
})(window);
