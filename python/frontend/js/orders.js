document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-orders-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const list = page.querySelector("[data-orders-list]");
    const error = page.querySelector("[data-orders-error]");
    const refreshButton = page.querySelector("[data-orders-refresh]");
    let loading = false;
    let renderedOrdersSignature = null;

    const statusLabel = (status) => ({
        PENDING_PAYMENT: "Chờ thanh toán",
        CONFIRMED: "Đã xác nhận",
        PROCESSING: "Đang xử lý",
        COMPLETED: "Hoàn tất",
        CANCELLED: "Đã hủy",
        REJECTED: "Từ chối",
    })[status] || status || "—";

    const shippingLabel = (status) => ({
        PENDING: "Chờ xử lý vận chuyển",
        SHIPPED: "Đã gửi",
        PICKED_UP: "Đã lấy hàng",
        IN_TRANSIT: "Đang vận chuyển",
        OUT_FOR_DELIVERY: "Đang giao",
        DELIVERED: "Đã giao thành công",
        EXCEPTION: "Có sự cố",
        RETURNED: "Đã hoàn hàng",
    })[status] || status || "—";

    const makeProgress = (order) => {
        const shipment = order.shipment_status;
        const borrowStatus = order.borrow_status;
        const cancelled = ["CANCELLED", "REJECTED"].includes(order.status)
            || ["CANCELLED", "REJECTED"].includes(borrowStatus);
        const isBorrow = order.order_type === "BORROW";
        const isDelivered = isBorrow
            ? ["RETURNED", "COMPLETED"].includes(borrowStatus)
            : shipment === "DELIVERED";
        const isShipping = isBorrow
            ? ["ACTIVE", "OVERDUE", "RETURN_REQUESTED"].includes(borrowStatus)
            : ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY"].includes(shipment);
        const isConfirmed = isBorrow
            ? ["CONFIRMED", "READY_FOR_PICKUP", "ACTIVE", "OVERDUE", "RETURN_REQUESTED", "RETURNED", "COMPLETED"].includes(borrowStatus)
            : ["CONFIRMED", "COMPLETED"].includes(order.status) || Boolean(shipment);
        const steps = isBorrow
            ? ["Yêu cầu mượn", "Đã xác nhận", "Đang mượn", "Đã trả"]
            : ["Đặt hàng", "Đã xác nhận", "Đã lấy hàng", "Đang vận chuyển", "Đang giao", "Đã giao"];
        const currentStep = isBorrow
            ? (isDelivered ? 3 : isShipping ? 2 : isConfirmed ? 1 : 0)
            : shipment === "DELIVERED" ? 5
                : shipment === "OUT_FOR_DELIVERY" ? 4
                    : shipment === "IN_TRANSIT" ? 3
                        : shipment === "PICKED_UP" ? 2
                            : isConfirmed ? 1 : 0;
        const tracker = document.createElement("ol");
        tracker.className = "order-progress";
        tracker.setAttribute("aria-label", "Tiến trình đơn hàng");
        if (cancelled) {
            const state = document.createElement("li");
            state.className = "order-progress__cancelled";
            state.textContent = `Đơn hàng ${statusLabel(order.status).toLowerCase()}`;
            tracker.append(state);
            return tracker;
        }
        steps.forEach((step, index) => {
            const item = document.createElement("li");
            item.className = index < currentStep
                ? "is-complete"
                : index === currentStep ? "is-current" : "";
            if (index === currentStep) item.setAttribute("aria-current", "step");
            item.textContent = step;
            tracker.append(item);
        });
        return tracker;
    };

    const imageNode = (item) => {
        const image = document.createElement("img");
        image.className = "order-item__image";
        image.src = item.image_url || "https://placehold.co/96x120/e2e8f0/475569?text=PASSBOOK";
        image.alt = `Ảnh ${item.title || "sách"}`;
        image.loading = "lazy";
        image.addEventListener("error", () => {
            image.src = "https://placehold.co/96x120/e2e8f0/475569?text=PASSBOOK";
        }, {once: true});
        return image;
    };

    const detailPanel = async (card, summary) => {
        const data = await OrdersAPI.get(summary.id);
        const panel = document.createElement("section");
        panel.className = "order-detail-panel";
        const items = document.createElement("div");
        items.className = "order-items";
        (data.items || []).forEach((item) => {
            const row = document.createElement("article");
            row.className = "order-item";
            const text = document.createElement("div");
            const title = document.createElement("strong");
            title.textContent = item.title;
            const price = document.createElement("span");
            price.textContent = `${formatPrice(Number(item.unit_price) || 0)}${item.condition ? ` · ${item.condition}` : ""}`;
            text.append(title, price);
            row.append(imageNode(item), text);
            items.append(row);
        });
        panel.append(items);
        const summaryLine = document.createElement("p");
        summaryLine.className = "order-detail__summary";
        summaryLine.textContent = [
            `Trạng thái: ${statusLabel(data.status)}`,
            `Tạm tính: ${formatPrice(Number(data.subtotal) || 0)}`,
            `Phí vận chuyển: ${formatPrice(Number(data.shipping_fee) || 0)}`,
            `Tổng tiền: ${formatPrice(Number(data.total_amount) || 0)}`,
        ].filter(Boolean).join(" · ");
        panel.append(summaryLine);

        const payments = document.createElement("section");
        payments.className = "shipment-summary";
        const paymentHeading = document.createElement("strong");
        paymentHeading.textContent = "Thanh toán";
        payments.append(paymentHeading);
        (data.payments || []).forEach((payment) => {
            const paymentLine = document.createElement("p");
            paymentLine.textContent = [
                `Payment #${payment.id}`,
                payment.payment_method || "",
                payment.status,
                formatPrice(Number(payment.amount) || 0),
                payment.reference ? `Ref ${payment.reference}` : "",
            ].filter(Boolean).join(" · ");
            payments.append(paymentLine);
        });
        if (!data.payments?.length) {
            const empty = document.createElement("p");
            empty.textContent = "Chưa có giao dịch thanh toán.";
            payments.append(empty);
        }
        panel.append(payments);

        if (data.borrow) {
            const borrow = data.borrow;
            const terms = borrow.borrow_terms || {};
            const borrowInfo = document.createElement("div");
            borrowInfo.className = "borrow-ticket";
            borrowInfo.textContent = [
                `Phiếu mượn #${borrow.id} · ${borrow.status}`,
                `Người cho mượn: ${borrow.lender?.name || "—"}`,
                `Người mượn: ${borrow.borrower?.name || "—"}`,
                `Thời hạn tối đa: ${terms.max_days ? `${terms.max_days} ngày` : "—"}`,
                `Thời gian yêu cầu: ${data.created_at ? new Date(data.created_at).toLocaleString("vi-VN") : "—"}`,
                `Bắt đầu: ${borrow.actual_start_at ? new Date(borrow.actual_start_at).toLocaleString("vi-VN") : borrow.expected_start_at ? new Date(borrow.expected_start_at).toLocaleString("vi-VN") : "—"}`,
                `Dự kiến trả: ${borrow.expected_return_at ? new Date(borrow.expected_return_at).toLocaleString("vi-VN") : "—"}`,
                `Đã trả: ${borrow.actual_return_at ? new Date(borrow.actual_return_at).toLocaleString("vi-VN") : "Chưa trả"}`,
                `Trạng thái trả: ${borrow.return_status || "Chưa yêu cầu trả"}`,
                `Cách trả: ${borrow.return_method || terms.return_method || "—"}`,
                `Mã vận đơn trả: ${borrow.return_tracking_code || "—"}`,
                borrow.return_notes ? `Ghi chú trả: ${borrow.return_notes}` : "",
            ].filter(Boolean).join("\n");
            panel.append(borrowInfo);
        } else if (data.shipping_address) {
            const address = document.createElement("p");
            address.textContent = [
                data.shipping_address.recipient_name,
                data.shipping_address.phone,
                data.shipping_address.address_line,
                data.shipping_address.city,
            ].filter(Boolean).join(" · ");
            panel.append(address);
        }

        (data.shipments || []).forEach((shipment) => {
            const section = document.createElement("section");
            section.className = "shipment-summary";
            const heading = document.createElement("strong");
            heading.textContent = `Vận chuyển: ${shippingLabel(shipment.status)}`;
            const carrier = document.createElement("p");
            carrier.textContent = [shipment.carrier, shipment.tracking_code ? `Mã vận đơn ${shipment.tracking_code}` : ""]
                .filter(Boolean).join(" · ");
            section.append(heading, carrier);
            (shipment.tracking || []).forEach((entry) => {
                const event = document.createElement("p");
                event.textContent = `${shippingLabel(entry.status)} · ${entry.location || ""} ${entry.description || ""} · ${new Date(entry.occurred_at).toLocaleString("vi-VN")}`;
                section.append(event);
            });
            panel.append(section);
        });

        if (data.can_review) {
            const review = document.createElement("a");
            review.className = "button button-primary";
            review.href = `review.html?order_id=${encodeURIComponent(data.id)}`;
            review.textContent = "Đánh giá sách";
            panel.append(review);
        }
        card.append(panel);
    };

    const renderCard = (order) => {
        const card = document.createElement("article");
        card.className = "order-card";
        card.dataset.orderId = String(order.id);
        const heading = document.createElement("div");
        heading.className = "order-card__heading";
        const code = document.createElement("strong");
        code.textContent = `Mã đơn ${order.order_code}`;
        const status = document.createElement("span");
        status.className = "badge badge-status";
        status.textContent = statusLabel(order.status);
        heading.append(code, status);
        card.append(heading, makeProgress(order));

        const rows = document.createElement("div");
        rows.className = "order-items";
        (order.items || []).forEach((item) => {
            const row = document.createElement("article");
            row.className = "order-item";
            const title = document.createElement("strong");
            title.textContent = item.title;
            const price = document.createElement("span");
            price.textContent = formatPrice(Number(item.unit_price) || 0);
            const label = document.createElement("div");
            label.append(title, price);
            row.append(imageNode(item), label);
            rows.append(row);
        });
        card.append(rows);
        const meta = document.createElement("p");
        meta.className = "order-card__meta";
        meta.textContent = [
            `Ngày đặt: ${new Date(order.created_at).toLocaleString("vi-VN")}`,
            `Tổng tiền: ${formatPrice(Number(order.total_amount) || 0)}`,
            order.payment_status ? `Thanh toán: ${order.payment_status}` : "",
            order.shipment_status ? `Vận chuyển: ${shippingLabel(order.shipment_status)}` : "",
            order.shipment_tracking_code ? `Mã vận đơn: ${order.shipment_tracking_code}` : "",
        ].filter(Boolean).join(" · ");
        card.append(meta);
        const actions = document.createElement("div");
        actions.className = "order-card__actions";
        const detailButton = document.createElement("button");
        detailButton.className = "button button-outline";
        detailButton.type = "button";
        detailButton.textContent = "Chi tiết đơn hàng";
        detailButton.addEventListener("click", async () => {
            detailButton.disabled = true;
            try {
                const existing = card.querySelector(".order-detail-panel");
                if (existing) {
                    existing.remove();
                    detailButton.textContent = "Chi tiết đơn hàng";
                } else {
                    detailButton.textContent = "Đang tải...";
                    await detailPanel(card, order);
                    detailButton.textContent = "Ẩn chi tiết";
                }
            } catch (requestError) {
                error.textContent = requestError.message;
                detailButton.textContent = "Chi tiết đơn hàng";
            } finally {
                detailButton.disabled = false;
            }
        });
        actions.append(detailButton);
        if (order.status === "COMPLETED") {
            const review = document.createElement("a");
            review.className = "button button-primary";
            review.href = `review.html?order_id=${encodeURIComponent(order.id)}`;
            review.textContent = "Đánh giá sách";
            actions.append(review);
        }
        card.append(actions);
        return card;
    };

    const load = async ({quiet = false} = {}) => {
        if (loading) return;
        loading = true;
        error.textContent = "";
        if (!quiet) {
            list.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải đơn hàng..."));
        }
        if (refreshButton) refreshButton.disabled = true;
        try {
            const data = await OrdersAPI.list({page_size: 50});
            const signature = JSON.stringify(data);
            if (signature !== renderedOrdersSignature) {
                const orders = data.results || [];
                if (orders.length) {
                    list.replaceChildren(...orders.map(renderCard));
                } else {
                    const empty = PassbookCommonComponents.emptyStateElement(
                        "Chưa có đơn hàng.",
                        "Các đơn mua và mượn sách sẽ xuất hiện tại đây.",
                    );
                    const browse = document.createElement("a");
                    browse.className = "button button-primary";
                    browse.href = "books.html";
                    browse.textContent = "Khám phá sách";
                    empty.append(browse);
                    list.replaceChildren(empty);
                }
                renderedOrdersSignature = signature;
                const requestedOrderId = new URLSearchParams(location.search).get("order_id");
                if (requestedOrderId) {
                    const orderCard = [...list.querySelectorAll("[data-order-id]")]
                        .find((item) => item.dataset.orderId === requestedOrderId);
                    if (orderCard) {
                        orderCard.classList.add("is-highlighted");
                        orderCard.scrollIntoView({behavior: "smooth", block: "center"});
                    }
                }
            }
        } catch (requestError) {
            if (!quiet) {
                list.replaceChildren(PassbookCommonComponents.emptyStateElement(
                    "Không thể tải đơn hàng.",
                    requestError.message,
                ));
            }
            error.textContent = requestError.message || "Không thể cập nhật trạng thái đơn hàng.";
        } finally {
            loading = false;
            if (refreshButton) refreshButton.disabled = false;
        }
    };
    let resumeRefreshAt = 0;
    const refreshOnResume = () => {
        const now = Date.now();
        if (document.visibilityState !== "visible" || now - resumeRefreshAt < 1000) return;
        resumeRefreshAt = now;
        void load({quiet: true});
    };
    const onVisibilityChange = () => {
        if (document.visibilityState === "visible") refreshOnResume();
    };
    let pollingTimer = null;
    const startPolling = () => {
        if (pollingTimer !== null) return;
        pollingTimer = window.setInterval(() => {
            if (document.visibilityState === "visible") void load({quiet: true});
        }, 15000);
    };
    const stopPolling = () => {
        if (pollingTimer === null) return;
        window.clearInterval(pollingTimer);
        pollingTimer = null;
    };
    const onPageHide = (event) => {
        stopPolling();
        if (!event.persisted) {
            window.removeEventListener("focus", refreshOnResume);
            document.removeEventListener("visibilitychange", onVisibilityChange);
        }
    };
    const onPageShow = (event) => {
        if (!event.persisted) return;
        window.addEventListener("focus", refreshOnResume);
        document.addEventListener("visibilitychange", onVisibilityChange);
        startPolling();
    };
    startPolling();
    refreshButton?.addEventListener("click", () => void load());
    window.addEventListener("focus", refreshOnResume);
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("pagehide", onPageHide);
    window.addEventListener("pageshow", onPageShow);
    void load();
});
