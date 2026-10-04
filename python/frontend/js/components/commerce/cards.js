(function (global) {
    "use strict";

    function cartItem(item, {onRemove} = {}) {
        const card = document.createElement("article");
        card.className = "report-item";
        const title = document.createElement("strong");
        title.textContent = item.title || "Sách";
        const meta = document.createElement("span");
        meta.textContent = `${item.listing_type === "BORROW" ? "Mượn" : "Mua"} · ${global.formatPrice(Number(item.unit_price) || 0)}`;
        card.append(title, meta);
        if (item.listing_type === "BORROW") {
            const dates = document.createElement("div");
            dates.className = "borrow-date-fields";
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
                input.dataset.borrowListing = String(item.listing_id);
                input.dataset.borrowField = key;
                field.append(input);
                dates.append(field);
            }
            card.append(dates);
        }
        const remove = document.createElement("button");
        remove.className = "button button-outline";
        remove.type = "button";
        remove.textContent = "Xóa";
        remove.addEventListener("click", onRemove || (() => {}));
        card.append(remove);
        return card;
    }

    function orderCard(order, {onDetails} = {}) {
        const card = document.createElement("article");
        card.className = "report-item";
        const title = document.createElement("strong");
        title.textContent = `${order.order_code} · ${order.order_type}`;
        const status = document.createElement("span");
        status.textContent = `${order.status} · ${global.formatPrice(Number(order.total_amount) || 0)}`;
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
