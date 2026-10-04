document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-workspace-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const workspaceView = page.dataset.workspaceView || "all";

    const cartItems = page.querySelector("[data-cart-items]");
    const cartTotal = page.querySelector("[data-cart-total]");
    const checkoutForm = page.querySelector("[data-checkout-form]");
    const checkoutSummary = page.querySelector("[data-checkout-summary]");
    const cartError = page.querySelector("[data-cart-error]");
    const checkoutSuccess = page.querySelector("[data-checkout-success]");
    const ordersList = page.querySelector("[data-orders-list]");
    const reservationsList = page.querySelector("[data-reservations-list]");
    const borrowsList = page.querySelector("[data-borrows-list]");
    let currentUser = PassbookAuth.getCurrentUser() || {};
    window.addEventListener("passbook:user-updated", (event) => {
        currentUser = event.detail;
    });
    const checkoutKeyStorage = "passbook.checkout.idempotencyKey";
    let selectedCartItemId = null;
    let buyNowProcessed = false;
    let orderPage = 1;
    let reservationPage = 1;
    let borrowPage = 1;

    const setMessage = (container, message, className = "caption") => {
        const element = document.createElement("p");
        element.className = className;
        element.textContent = message;
        container.replaceChildren(element);
    };

    const money = (value) => formatPrice(Number(value) || 0);

    const trackingLabel = (status) => ({
        PENDING: "Chờ bàn giao",
        PICKED_UP: "Đã lấy hàng",
        IN_TRANSIT: "Đang vận chuyển",
        OUT_FOR_DELIVERY: "Đang giao",
        DELIVERED: "Đã giao",
    })[status] || status || "—";

    const returnMethodLabel = (method) => ({
        DELIVERY: "Giao hàng",
    })[method] || method;

    const ticketDetails = (entries) => {
        const details = document.createElement("dl");
        details.className = "borrow-ticket__details";
        entries.filter(([, value]) => value).forEach(([label, value]) => {
            const item = document.createElement("div");
            const term = document.createElement("dt");
            term.textContent = label;
            const description = document.createElement("dd");
            description.textContent = value;
            item.append(term, description);
            details.append(item);
        });
        return details;
    };

    const pagination = (data, pageNumber, setPage, reload) => {
        if (!data.previous && !data.next) return null;
        return PassbookCommonComponents.pagination({
            previous: data.previous,
            next: data.next,
            onPrevious: () => {
                setPage(Math.max(1, pageNumber - 1));
                reload();
            },
            onNext: () => {
                setPage(pageNumber + 1);
                reload();
            },
        });
    };

    const itemCard = (item) => {
        return PassbookCommerceComponents.cartItem(item, {
            onRemove: async (event) => {
                const remove = event.currentTarget;
                remove.disabled = true;
                try {
                    await OrdersAPI.removeCartItem(item.id);
                    await loadCart();
                } catch (error) {
                    showToast(error.message);
                } finally {
                    remove.disabled = false;
                }
            },
            onBuy: async (event) => {
                const buy = event.currentTarget;
                buy.disabled = true;
                cartError.textContent = "";
                try {
                    const quote = await OrdersAPI.checkoutQuote({cart_item_id: item.id});
                    selectedCartItemId = item.id;
                    const lines = [
                        `${quote.items[0]?.title || item.title} · ${money(quote.items[0]?.subtotal || 0)}`,
                        `Tạm tính: ${money(quote.subtotal)}`,
                        `Phí nền tảng 10%: ${money(quote.platform_fee || 0)}`,
                        `Phí vận chuyển: ${money(quote.shipping_total)}`,
                        `Tổng tiền: ${money(quote.total_amount)}`,
                    ];
                    checkoutSummary.replaceChildren(...lines.map((text) => {
                        const row = document.createElement("p");
                        row.textContent = text;
                        return row;
                    }));
                    checkoutForm.hidden = false;
                    checkoutForm.scrollIntoView({behavior: "smooth", block: "center"});
                } catch (error) {
                    cartError.textContent = error.message;
                } finally {
                    buy.disabled = false;
                }
            },
        });
    };

    const loadCart = async () => {
        try {
            const cart = await OrdersAPI.cart();
            const items = Array.isArray(cart.items) ? cart.items : [];
            const buyNowListingId = new URLSearchParams(location.search).get("buy_now");
            if (!items.length) {
                setMessage(cartItems, "Giỏ hàng đang trống.");
                cartTotal.textContent = "";
                checkoutForm.hidden = true;
                selectedCartItemId = null;
                if (buyNowListingId) {
                    const query = new URLSearchParams(location.search);
                    query.delete("buy_now");
                    const suffix = query.toString();
                    history.replaceState(null, "", `${location.pathname}${suffix ? `?${suffix}` : ""}${location.hash}`);
                    cartError.textContent = "Không tìm thấy sách vừa chọn. Kiểm tra lại giỏ hàng.";
                } else {
                    cartError.textContent = "";
                }
                return;
            }
            cartItems.replaceChildren(...items.map(itemCard));
            cartTotal.textContent = `Tổng cộng: ${money(cart.total_amount)}`;
            cartError.textContent = "";
            if (buyNowListingId && !buyNowProcessed) {
                buyNowProcessed = true;
                const target = items.find((item) =>
                    String(item.listing_id) === buyNowListingId && item.listing_type !== "BORROW",
                );
                const query = new URLSearchParams(location.search);
                query.delete("buy_now");
                const suffix = query.toString();
                history.replaceState(null, "", `${location.pathname}${suffix ? `?${suffix}` : ""}${location.hash}`);
                if (target) {
                    cartItems.querySelector(`[data-cart-item="${CSS.escape(String(target.id))}"]`)
                        ?.querySelector("[data-cart-buy]")?.click();
                } else {
                    cartError.textContent = "Không tìm thấy sách vừa chọn. Kiểm tra lại giỏ hàng.";
                }
            }
            if (selectedCartItemId && !items.some((item) => item.id === selectedCartItemId)) {
                selectedCartItemId = null;
                checkoutForm.hidden = true;
            }
        } catch (error) {
            setMessage(cartItems, error.message, "form-error");
            checkoutForm.hidden = true;
        }
    };

    function checkoutKey() {
        let key = sessionStorage.getItem(checkoutKeyStorage);
        if (!key) {
            key = crypto.randomUUID();
            sessionStorage.setItem(checkoutKeyStorage, key);
        }
        return key;
    }

    page.querySelector("[data-checkout-cancel]")?.addEventListener("click", () => {
        selectedCartItemId = null;
        checkoutForm.hidden = true;
        cartError.textContent = "";
    });

    const paymentMethod = checkoutForm?.querySelector("[name='payment_method']");
    const fakeOptions = checkoutForm?.querySelector("[data-fake-payment-options]");
    const bankTransferNote = checkoutForm?.querySelector("[data-bank-transfer-note]");
    const codNote = checkoutForm?.querySelector("[data-cod-note]");
    const updatePaymentInstructions = () => {
        const method = paymentMethod?.value;
        if (fakeOptions) fakeOptions.hidden = method !== "FAKE";
        if (bankTransferNote) bankTransferNote.hidden = method !== "BANK_TRANSFER";
        if (codNote) codNote.hidden = method !== "COD";
    };
    paymentMethod?.addEventListener("change", updatePaymentInstructions);
    updatePaymentInstructions();

    checkoutForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (selectedCartItemId === null) {
            cartError.textContent = "Chọn sản phẩm cần mua trong giỏ hàng.";
            return;
        }
        if (!checkoutForm.reportValidity()) return;
        const data = new FormData(checkoutForm);
        const shippingSnapshot = {
            recipient_name: data.get("recipient_name").toString().trim(),
            phone: data.get("phone").toString().trim(),
            address_line: data.get("address_line").toString().trim(),
            city: data.get("city").toString().trim(),
        };
        const borrow = {};
        for (const input of page.querySelectorAll(
            `[data-borrow-listing][data-cart-item="${selectedCartItemId}"]`,
        )) {
            const listingId = input.dataset.borrowListing;
            borrow[listingId] ||= {};
            if (input.value) {
                borrow[listingId][input.dataset.borrowField] = new Date(input.value).toISOString();
            }
        }
        for (const [listingId, dates] of Object.entries(borrow)) {
            if (!dates.expected_start_at || !dates.expected_return_at) {
                showToast(`Chọn ngày mượn và ngày trả cho giao dịch #${listingId}.`);
                return;
            }
            if (new Date(dates.expected_return_at) <= new Date(dates.expected_start_at)) {
                showToast(`Ngày trả của giao dịch #${listingId} phải sau ngày bắt đầu.`);
                return;
            }
        }

        const submit = checkoutForm.querySelector("button[type='submit']");
        submit.disabled = true;
        cartError.textContent = "";
        const payload = {
                idempotency_key: checkoutKey(),
                cart_item_id: selectedCartItemId,
                shipping_address_snapshot: shippingSnapshot,
                payment_outcome: data.get("payment_outcome"),
                payment_method: data.get("payment_method"),
                borrow,
            };
        const completeCheckout = async () => {
            const result = await OrdersAPI.checkout(payload);
            sessionStorage.removeItem(checkoutKeyStorage);
            selectedCartItemId = null;
            checkoutForm.hidden = true;
            const firstOrder = result.orders?.[0];
            if (checkoutSuccess && firstOrder) {
                const heading = document.createElement("h2");
                heading.textContent = firstOrder.payment_status === "PROCESSING"
                    ? "Đơn hàng đang chờ xác minh chuyển khoản"
                    : firstOrder.payment_method === "COD"
                        ? "Đã tạo đơn hàng COD"
                        : "Đặt hàng thành công";
                const description = document.createElement("p");
                description.textContent = [
                    `Đơn ${firstOrder.order_code} đã được tạo.`,
                    `Order: ${firstOrder.status}`,
                    `Payment: ${firstOrder.payment_status || "—"}`,
                    firstOrder.payment_method === "COD"
                        ? "COD chưa được xác nhận đã thu tiền."
                        : "",
                ].filter(Boolean).join(" · ");
                const link = document.createElement("a");
                link.className = "button button-primary";
                link.href = `orders.html?order_id=${encodeURIComponent(firstOrder.id)}`;
                link.textContent = "Xem đơn hàng mới";
                checkoutSuccess.replaceChildren(heading, description, link);
                checkoutSuccess.hidden = false;
            } else {
                showToast(`Thanh toán thành công · đơn ${firstOrder?.order_code || result.checkout_code}.`);
            }
            await Promise.all([
                loadCart(),
                ordersList ? loadOrders() : Promise.resolve(),
            ]);
        };
        try {
            await completeCheckout();
        } catch (error) {
            cartError.textContent = (
                error.status === 409
                && error.payload?.payment_status === "CANCELLED"
                && typeof error.payload.detail === "string"
            )
                ? error.payload.detail
                : error.message;
        } finally {
            submit.disabled = false;
        }
    });

    const addOrderDetails = async (container, order) => {
        const detail = await OrdersAPI.get(order.id);
        const list = document.createElement("div");
        list.className = "order-detail";
        const summary = document.createElement("p");
        summary.textContent = [
            `Đơn: ${detail.status}`,
            `Đặt lúc: ${new Date(detail.created_at).toLocaleString("vi-VN")}`,
            detail.shipping_address?.recipient_name
                ? `Người nhận: ${detail.shipping_address.recipient_name}`
                : "",
            detail.shipping_address?.address_line
                ? `Địa chỉ: ${detail.shipping_address.address_line}, ${detail.shipping_address.city || ""}`
                : "",
        ].filter(Boolean).join(" · ");
        list.append(summary);
        (detail.items || []).forEach((item) => {
            const row = document.createElement("p");
            row.textContent = `${item.title} · ${money(item.unit_price)}`;
            list.append(row);
        });
        (detail.payments || []).forEach((payment) => {
            const paymentRow = document.createElement("div");
            paymentRow.className = "payment-row";
            const row = document.createElement("p");
            row.textContent = `Thanh toán #${payment.id}: ${payment.status} · ${money(payment.amount)}`;
            paymentRow.append(row);
            list.append(paymentRow);
        });
        (detail.shipments || []).forEach((shipment) => {
            const section = document.createElement("section");
            const title = document.createElement("strong");
            title.textContent = `Giao hàng #${shipment.id}: ${shipment.status}`;
            section.append(title);
            if (shipment.tracking_code) {
                const trackingCode = document.createElement("p");
                trackingCode.textContent = `Mã vận đơn: ${shipment.tracking_code}`;
                section.append(trackingCode);
            }
            (shipment.tracking || []).forEach((entry) => {
                const tracking = document.createElement("p");
                tracking.textContent = `${entry.status} · ${entry.location || ""} · ${entry.description || ""}`;
                section.append(tracking);
            });
            list.append(section);
            if (shipment.status !== "DELIVERED") {
                for (const status of ["IN_TRANSIT", "DELIVERED"]) {
                    const update = document.createElement("button");
                    update.className = "button button-outline";
                    update.type = "button";
                    update.textContent = `Cập nhật vận chuyển: ${status}`;
                    update.addEventListener("click", async () => {
                        update.disabled = true;
                        try {
                            await ShippingAPI.addTracking(shipment.id, {
                                status,
                                description: status === "DELIVERED"
                                    ? "Đã giao hàng."
                                    : "Đang vận chuyển.",
                            });
                            await loadOrders();
                        } catch (error) {
                            showToast(error.message);
                        } finally {
                            update.disabled = false;
                        }
                    });
                    list.append(update);
                }
            }
        });

        if (order.status === "PENDING_PAYMENT" && !(detail.payments || []).some((payment) => payment.status === "PAID")) {
            const pay = document.createElement("button");
            pay.className = "button button-primary";
            pay.type = "button";
            pay.textContent = "Tạo yêu cầu thanh toán";
            pay.addEventListener("click", async () => {
                const apiHost = new URL(API_BASE_URL).hostname;
                const provider = window.PASSBOOK_PAYMENT_PROVIDER
                    || (["localhost", "127.0.0.1"].includes(apiHost) ? "fake" : "");
                const paymentMethod = window.PASSBOOK_PAYMENT_METHOD
                    || (provider === "fake" ? "TEST" : "");
                if (!provider || !paymentMethod) {
                    showToast("Chưa cấu hình payment provider cho môi trường này.");
                    return;
                }
                pay.disabled = true;
                try {
                    const keyName = `passbook.payment.${order.id}.idempotencyKey`;
                    let key = sessionStorage.getItem(keyName);
                    if ((detail.payments || []).some((payment) => payment.status === "FAILED")) {
                        sessionStorage.removeItem(keyName);
                        key = null;
                    }
                    if (!key) {
                        key = crypto.randomUUID();
                        sessionStorage.setItem(keyName, key);
                    }
                    await PaymentsAPI.createIntent(order.id, {
                        provider,
                        payment_method: paymentMethod,
                        idempotency_key: key,
                    });
                    showToast("Đã tạo yêu cầu thanh toán.");
                    await loadOrders();
                } catch (error) {
                    showToast(error.message);
                } finally {
                    pay.disabled = false;
                }
            });
            list.append(pay);
        }
        if ((detail.payments || []).some((payment) => payment.status === "PAID")
            && !(detail.shipments || []).length) {
            const createShipment = document.createElement("button");
            createShipment.className = "button button-outline";
            createShipment.type = "button";
            createShipment.textContent = "Tạo vận đơn (người bán)";
            createShipment.addEventListener("click", async () => {
                createShipment.disabled = true;
                try {
                    const carrier = prompt("Đơn vị vận chuyển (có thể để trống):") || "";
                    const trackingCode = prompt("Mã vận đơn (có thể để trống):") || "";
                    await ShippingAPI.create(order.id, {
                        carrier: carrier.trim(),
                        tracking_code: trackingCode.trim(),
                    });
                    await loadOrders();
                } catch (error) {
                    showToast(error.message);
                } finally {
                    createShipment.disabled = false;
                }
            });
            list.append(createShipment);
        }

        if (order.status === "PENDING_PAYMENT") {
            const cancel = document.createElement("button");
            cancel.className = "button button-outline";
            cancel.type = "button";
            cancel.textContent = "Hủy đơn";
            cancel.addEventListener("click", async () => {
                if (!confirm("Bạn có chắc muốn hủy đơn hàng này?")) return;
                cancel.disabled = true;
                try {
                    await OrdersAPI.cancel(order.id);
                    await loadOrders();
                } catch (error) {
                    showToast(error.message);
                } finally {
                    cancel.disabled = false;
                }
            });
            list.append(cancel);
        }

        const returns = document.createElement("div");
        const paidPayment = (detail.payments || []).find((payment) => payment.status === "PAID");
        const canReturn = order.status === "COMPLETED"
            || (detail.shipments || []).some((shipment) => shipment.status === "DELIVERED");
        for (const item of detail.items || []) {
            const requestReturn = document.createElement("button");
            requestReturn.className = "button button-outline";
            requestReturn.type = "button";
            requestReturn.textContent = `Yêu cầu trả: ${item.title}`;
            requestReturn.addEventListener("click", async () => {
                const reason = prompt("Lý do trả hàng:");
                if (!reason?.trim()) return;
                requestReturn.disabled = true;
                try {
                    await ReturnsAPI.create(order.id, {
                        sale_order_item_id: item.id,
                        reason: reason.trim().slice(0, 100),
                    });
                    showToast("Đã gửi yêu cầu trả hàng.");
                    await loadOrders();
                } catch (error) {
                    showToast(error.message);
                } finally {
                    requestReturn.disabled = false;
                }
            });
            if (canReturn) returns.append(requestReturn);
            if (paidPayment) {
                const refundButton = document.createElement("button");
                refundButton.className = "button button-outline";
                refundButton.type = "button";
                refundButton.textContent = `Yêu cầu hoàn tiền: ${item.title}`;
                refundButton.addEventListener("click", async () => {
                    const reason = prompt("Lý do hoàn tiền:");
                    if (!reason?.trim()) return;
                    refundButton.disabled = true;
                    try {
                        const keyName = `passbook.refund.${order.id}.${item.id}.idempotencyKey`;
                        let idempotencyKey = sessionStorage.getItem(keyName);
                        if (!idempotencyKey) {
                            idempotencyKey = crypto.randomUUID();
                            sessionStorage.setItem(keyName, idempotencyKey);
                        }
                        const refund = await ReturnsAPI.refund(order.id, {
                            payment_id: paidPayment.id,
                            sale_order_item_id: item.id,
                            idempotency_key: idempotencyKey,
                            reason: reason.trim().slice(0, 100),
                            amount: item.unit_price,
                        });
                        showToast(`Đã tạo yêu cầu hoàn tiền #${refund.id}.`);
                        if (
                            currentUser.role === "ADMIN"
                            && ["localhost", "127.0.0.1"].includes(new URL(API_BASE_URL).hostname)
                        ) {
                            ["COMPLETED", "FAILED"].forEach((status) => {
                                const simulate = document.createElement("button");
                                simulate.className = "button button-outline";
                                simulate.type = "button";
                                simulate.textContent = status === "COMPLETED"
                                    ? "Mô phỏng hoàn tiền thành công"
                                    : "Mô phỏng hoàn tiền thất bại";
                                simulate.addEventListener("click", async () => {
                                    simulate.disabled = true;
                                    try {
                                        await ReturnsAPI.fakeRefundTransition(refund.id, status);
                                        showToast(`Đã mô phỏng hoàn tiền ${status}.`);
                                        await loadOrders();
                                    } catch (error) {
                                        showToast(error.message);
                                    } finally {
                                        simulate.disabled = false;
                                    }
                                });
                                returns.append(simulate);
                            });
                        }
                    } catch (error) {
                        showToast(error.message);
                    } finally {
                        refundButton.disabled = false;
                    }
                });
                returns.append(refundButton);
            }
        }
        if (detail.items?.length && canReturn && paidPayment) list.append(returns);
        if (order.status === "COMPLETED") {
            const review = document.createElement("button");
            review.className = "button button-outline";
            review.type = "button";
            review.textContent = "Đánh giá giao dịch";
            review.addEventListener("click", async () => {
                const rating = Number(prompt("Đánh giá từ 1 đến 5:"));
                if (!Number.isInteger(rating) || rating < 1 || rating > 5) return;
                try {
                    await OrdersAPI.createReview(order.id, {
                        rating,
                        comment: (prompt("Nhận xét (không bắt buộc):") || "").slice(0, 5000),
                    });
                    showToast("Đã lưu đánh giá.");
                } catch (error) {
                    showToast(error.message);
                }
            });
            list.append(review);
        }
        container.append(list);
    };

    const loadOrders = async () => {
        setMessage(ordersList, "Đang tải đơn hàng...", "loading-state");
        try {
            const data = await OrdersAPI.list({page: orderPage, page_size: 50});
            const nodes = (data.results || []).map((order) => {
                const {element: card, detailsButton: details} = PassbookCommerceComponents.orderCard(order);
                details.addEventListener("click", async () => {
                    details.disabled = true;
                    try {
                        const previous = card.querySelector(".order-detail");
                        if (previous) {
                            previous.remove();
                            details.textContent = "Chi tiết / thao tác";
                        } else {
                            details.textContent = "Đang tải...";
                            await addOrderDetails(card, order);
                            details.textContent = "Ẩn chi tiết";
                        }
                    } catch (error) {
                        showToast(error.message);
                        details.textContent = "Chi tiết / thao tác";
                    } finally {
                        details.disabled = false;
                    }
                });
                return card;
            });
            if (!nodes.length) {
                nodes.push(PassbookCommonComponents.emptyState("Chưa có đơn hàng."));
            }
            const controls = pagination(data, orderPage, (value) => { orderPage = value; }, loadOrders);
            if (controls) nodes.push(controls);
            ordersList.replaceChildren(...nodes);
        } catch (error) {
            setMessage(ordersList, error.message, "form-error");
        }
    };

    const reservationActions = (reservation, container) => {
        const isRequester = Number(reservation.requester_id) === Number(currentUser.id);
        const isOwner = Number(reservation.owner_id) === Number(currentUser.id);
        const addAction = (action, label) => {
            const button = document.createElement("button");
            button.className = "button button-outline";
            button.type = "button";
            button.textContent = label;
            button.addEventListener("click", async () => {
                button.disabled = true;
                try {
                    await ReservationsAPI.action(reservation.id, action);
                    await loadReservations();
                } catch (error) {
                    showToast(error.message);
                } finally {
                    button.disabled = false;
                }
            });
            container.append(button);
        };
        if (reservation.status === "PENDING" && isOwner) {
            addAction("confirm", reservation.listing_type === "BORROW" ? "Duyệt mượn" : "Xác nhận");
            addAction("reject", "Từ chối");
        }
        if (isRequester && (
            reservation.status === "PENDING"
            || (reservation.status === "CONFIRMED" && reservation.listing_type !== "BORROW")
        )) {
            addAction("cancel", "Hủy yêu cầu");
        }
        if (reservation.status === "CONFIRMED" && reservation.listing_type !== "BORROW"
            && (isRequester || isOwner)) {
            addAction("complete", "Hoàn tất");
        }
        if (reservation.status === "CONFIRMED" && isRequester
            && reservation.listing_type === "BORROW") {
            addAction("complete", "Tôi đã trả sách");
        }
    };

    const loadReservations = async () => {
        setMessage(reservationsList, "Đang tải yêu cầu...", "loading-state");
        try {
            const data = await ReservationsAPI.list({page: reservationPage, page_size: 50});
            const borrowReservations = (data.results || []).filter(
                (reservation) => reservation.listing_type === "BORROW",
            );
            const nodes = borrowReservations.map((reservation) => {
                const card = document.createElement("article");
                card.className = "report-item borrow-ticket-card";
                card.dataset.reservationId = String(reservation.id);
                if (reservation.book?.primary_image) {
                    const image = document.createElement("img");
                    image.className = "order-item__image";
                    image.src = reservation.book.primary_image;
                    image.alt = `Ảnh ${reservation.book.title || "sách mượn"}`;
                    image.addEventListener("error", () => image.remove(), {once: true});
                    card.append(image);
                }
                const title = document.createElement("strong");
                title.textContent = reservation.book?.title || `Yêu cầu mượn sách #${reservation.book_id}`;
                const status = document.createElement("span");
                const statusLabels = {
                    PENDING: "Chờ người cho mượn xác nhận",
                    CONFIRMED: "Đang mượn",
                    REJECTED: "Đã từ chối",
                    CANCELLED: "Đã hủy",
                    EXPIRED: "Yêu cầu đã hết hạn",
                    COMPLETED: "Đã hoàn tất trả sách",
                };
                status.className = `borrow-ticket__status borrow-ticket__status--${String(reservation.status).toLowerCase()}`;
                status.textContent = statusLabels[reservation.status] || reservation.status;
                const details = ticketDetails([
                    ["Mã phiếu", `#${reservation.id}`],
                    ["Người cho mượn", reservation.lender?.name],
                    ["Người mượn", reservation.requester?.name],
                    ["Môn học", [reservation.book?.subject?.name, reservation.book?.subject?.code]
                        .filter(Boolean).join(" · ")],
                    ["Danh mục", reservation.book?.category],
                    ["Ấn bản", [reservation.book?.edition, reservation.book?.publication_year]
                        .filter(Boolean).join(" · ")],
                    ["Tình trạng", reservation.book?.condition_status],
                    ["Trường", reservation.lender?.university],
                    ["Khoa / ngành", [reservation.lender?.faculty, reservation.lender?.major]
                        .filter(Boolean).join(" · ")],
                    ["Tạo lúc", reservation.created_at
                        ? new Date(reservation.created_at).toLocaleString("vi-VN")
                        : ""],
                    ["Hạn phản hồi", reservation.status === "PENDING" && reservation.expires_at
                        ? new Date(reservation.expires_at).toLocaleString("vi-VN")
                        : ""],
                    ["Phí mượn", reservation.listing?.rental_fee !== undefined
                        ? money(reservation.listing.rental_fee)
                        : ""],
                    ["Tiền đặt cọc", reservation.listing?.deposit_amount
                        ? money(reservation.listing.deposit_amount)
                        : ""],
                    ["Thời hạn tối đa", reservation.listing?.borrow_terms?.max_days
                        ? `${reservation.listing.borrow_terms.max_days} ngày`
                        : ""],
                    ["Cách trả", reservation.listing?.borrow_terms?.return_method],
                    ["Điều kiện", reservation.listing?.borrow_terms?.notes],
                ]);
                card.append(title, status, details);
                if (reservation.book?.description) {
                    const description = document.createElement("p");
                    description.className = "borrow-ticket__description";
                    description.textContent = reservation.book.description;
                    card.append(description);
                }
                reservationActions(reservation, card);
                return card;
            });
            const controls = borrowReservations.length
                ? pagination(
                    data,
                    reservationPage,
                    (value) => { reservationPage = value; },
                    loadReservations,
                )
                : null;
            if (controls) nodes.push(controls);
            reservationsList.classList.toggle("report-list", borrowReservations.length > 0);
            reservationsList.replaceChildren(...nodes);
            focusRequestedTicket("reservation_id", "reservationId");
        } catch (error) {
            setMessage(reservationsList, error.message, "form-error");
        }
    };

    const borrowActionOptions = (borrow) => {
        const isBorrower = Number(borrow.borrower_id) === Number(currentUser.id);
        const isLender = Number(borrow.lender_id) === Number(currentUser.id);
        if (borrow.status === "PENDING") {
            return isBorrower
                ? [["cancel", "Hủy yêu cầu"]]
                : isLender ? [["confirm", "Xác nhận"], ["reject", "Từ chối"]] : [];
        }
        if (borrow.status === "CONFIRMED" && isLender) return [["ready", "Chuẩn bị sách"]];
        if (borrow.status === "READY_FOR_PICKUP" && isBorrower) return [["start", "Đã nhận sách"]];
        if (
            ["ACTIVE", "OVERDUE"].includes(borrow.status)
            && isBorrower
        ) return [["request-return", "Trả sách"]];
        if (
            borrow.status === "RETURNED"
            && borrow.return_status === "DELIVERED"
            && isLender
        ) return [["complete", "Xác nhận đã nhận sách"]];
        return [];
    };

    const loadBorrows = async () => {
        setMessage(borrowsList, "Đang tải giao dịch...", "loading-state");
        try {
            const data = await OrdersAPI.borrowOrders({page: borrowPage, page_size: 50});
            const nodes = (data.results || []).map((borrow) => {
                const card = document.createElement("article");
                card.className = "report-item borrow-ticket-card";
                card.dataset.borrowId = String(borrow.id);
                if (borrow.image_url) {
                    const image = document.createElement("img");
                    image.className = "order-item__image";
                    image.src = borrow.image_url;
                    image.alt = `Ảnh ${borrow.title || "sách mượn"}`;
                    image.addEventListener("error", () => image.remove(), {once: true});
                    card.append(image);
                }
                const title = document.createElement("strong");
                title.textContent = `${borrow.title || "Sách mượn"} · Phiếu #${borrow.id}`;
                const status = document.createElement("span");
                const statusLabels = {
                    PENDING: "Chờ người cho mượn xác nhận",
                    CONFIRMED: "Đã xác nhận",
                    READY_FOR_PICKUP: "Sẵn sàng nhận sách",
                    ACTIVE: "Đang mượn",
                    RETURN_REQUESTED: "Đang trả sách",
                    RETURNED: "Đã giao đến người cho mượn · chờ xác nhận",
                    COMPLETED: "Đã trả sách",
                    REJECTED: "Đã từ chối",
                    CANCELLED: "Đã hủy",
                    OVERDUE: "Quá hạn",
                    DISPUTED: "Đang xử lý tranh chấp",
                };
                status.className = `borrow-ticket__status borrow-ticket__status--${String(borrow.status).toLowerCase()}`;
                status.textContent = statusLabels[borrow.status] || borrow.status;
                const details = ticketDetails([
                    ["Mã giao dịch", borrow.order_code || String(borrow.order_id || "")],
                    ["Người cho mượn", borrow.lender_name],
                    ["Người mượn", borrow.borrower_name],
                    ["Ngày tạo", borrow.created_at
                        ? new Date(borrow.created_at).toLocaleString("vi-VN")
                        : ""],
                    ["Phí mượn", money(borrow.rental_fee)],
                    ["Tiền đặt cọc", money(borrow.deposit_amount)],
                    ["Thời hạn tối đa", borrow.borrow_terms?.max_days
                        ? `${borrow.borrow_terms.max_days} ngày`
                        : ""],
                    ["Bắt đầu", borrow.actual_start_at
                        ? new Date(borrow.actual_start_at).toLocaleString("vi-VN")
                        : borrow.expected_start_at
                            ? new Date(borrow.expected_start_at).toLocaleString("vi-VN")
                            : "Chưa bắt đầu"],
                    ["Dự kiến trả", borrow.expected_return_at
                        ? new Date(borrow.expected_return_at).toLocaleString("vi-VN")
                        : ""],
                    ["Đã trả", borrow.actual_return_at
                        ? new Date(borrow.actual_return_at).toLocaleString("vi-VN")
                        : "Chưa trả"],
                    ["Trạng thái trả", borrow.return_status || "Chưa yêu cầu trả"],
                    ["Cách trả", returnMethodLabel(
                        borrow.return_method || borrow.borrow_terms?.return_method,
                    )],
                    ["Mã vận đơn trả", borrow.return_tracking_code],
                    ["Ghi chú", borrow.return_notes],
                ]);
                card.append(title, status, details);
                const actionGroup = document.createElement("div");
                actionGroup.className = "borrow-ticket-card__actions";
                let returnRequestForm = null;
                borrowActionOptions(borrow).forEach(([action, label]) => {
                    const button = document.createElement("button");
                    button.className = action === "return" || action === "complete"
                        ? "button button-primary"
                        : "button button-outline";
                    button.type = "button";
                    button.textContent = label;
                    button.addEventListener("click", async () => {
                        if (action === "request-return") {
                            returnRequestForm.hidden = !returnRequestForm.hidden;
                            return;
                        }
                        button.disabled = true;
                        try {
                            await OrdersAPI.borrowAction(borrow.id, action);
                            await loadBorrows();
                        } catch (error) {
                            showToast(error.message);
                        } finally {
                            button.disabled = false;
                        }
                    });
                    actionGroup.append(button);
                });
                if (actionGroup.childElementCount) card.append(actionGroup);
                if (
                    ["ACTIVE", "OVERDUE"].includes(borrow.status)
                    && Number(borrow.borrower_id) === Number(currentUser.id)
                ) {
                    returnRequestForm = document.createElement("form");
                    returnRequestForm.className = "borrow-return-form";
                    returnRequestForm.hidden = true;
                    const methodLabel = document.createElement("label");
                    methodLabel.textContent = "Phương thức vận chuyển";
                    const method = document.createElement("select");
                    method.required = true;
                    method.name = "return_method";
                    const delivery = document.createElement("option");
                    delivery.value = "DELIVERY";
                    delivery.textContent = "Giao hàng về cho người cho mượn";
                    method.append(delivery);
                    methodLabel.append(method);
                    const carrierLabel = document.createElement("label");
                    carrierLabel.textContent = "Đơn vị vận chuyển";
                    const carrier = document.createElement("input");
                    carrier.required = true;
                    carrier.maxLength = 100;
                    carrier.autocomplete = "organization";
                    carrier.placeholder = "Ví dụ: đơn vị giao hàng đã chọn";
                    carrierLabel.append(carrier);
                    const trackingLabel = document.createElement("label");
                    trackingLabel.textContent = "Mã vận đơn";
                    const trackingCode = document.createElement("input");
                    trackingCode.required = true;
                    trackingCode.maxLength = 100;
                    trackingCode.autocomplete = "off";
                    trackingLabel.append(trackingCode);
                    const notesLabel = document.createElement("label");
                    notesLabel.textContent = "Ghi chú (không bắt buộc)";
                    const notes = document.createElement("textarea");
                    notesLabel.append(notes);
                    const submit = document.createElement("button");
                    submit.className = "button button-primary";
                    submit.type = "submit";
                    submit.textContent = "Tạo yêu cầu trả và vận chuyển";
                    returnRequestForm.append(
                        methodLabel,
                        carrierLabel,
                        trackingLabel,
                        notesLabel,
                        submit,
                    );
                    returnRequestForm.addEventListener("submit", async (event) => {
                        event.preventDefault();
                        submit.disabled = true;
                        try {
                            await OrdersAPI.requestBorrowReturn(borrow.id, {
                                return_method: method.value,
                                carrier: carrier.value.trim(),
                                return_tracking_code: trackingCode.value.trim(),
                                return_notes: notes.value.trim(),
                            });
                            await loadBorrows();
                        } catch (error) {
                            showToast(error.message);
                        } finally {
                            submit.disabled = false;
                        }
                    });
                    card.append(returnRequestForm);
                }
                if (borrow.return_shipment) {
                    const shipment = borrow.return_shipment;
                    const trackingSection = document.createElement("section");
                    trackingSection.className = "shipment-summary";
                    const shipmentTitle = document.createElement("strong");
                    shipmentTitle.textContent = "Đơn trả sách · Người mượn → Người cho mượn";
                    const shipmentInfo = document.createElement("p");
                    shipmentInfo.textContent = [
                        `Trạng thái: ${trackingLabel(shipment.status)}`,
                        shipment.carrier,
                        shipment.tracking_code ? `Mã vận đơn: ${shipment.tracking_code}` : "",
                    ].filter(Boolean).join(" · ");
                    trackingSection.append(shipmentTitle, shipmentInfo);
                    (shipment.tracking || []).forEach((entry) => {
                        const event = document.createElement("p");
                        event.textContent = [
                            trackingLabel(entry.status),
                            entry.location,
                            entry.description,
                            entry.occurred_at
                                ? new Date(entry.occurred_at).toLocaleString("vi-VN")
                                : "",
                        ].filter(Boolean).join(" · ");
                        trackingSection.append(event);
                    });
                    if (
                        Number(borrow.borrower_id) === Number(currentUser.id)
                        && shipment.status !== "DELIVERED"
                    ) {
                        const nextTrackingStatus = {
                            PENDING: "PICKED_UP",
                            PICKED_UP: "IN_TRANSIT",
                            IN_TRANSIT: "DELIVERED",
                            OUT_FOR_DELIVERY: "DELIVERED",
                        }[shipment.status];
                        if (nextTrackingStatus) {
                            const updateTracking = document.createElement("button");
                            updateTracking.className = "button button-outline";
                            updateTracking.type = "button";
                            updateTracking.textContent = `Cập nhật vận chuyển: ${trackingLabel(nextTrackingStatus)}`;
                            updateTracking.addEventListener("click", async () => {
                                updateTracking.disabled = true;
                                try {
                                    await OrdersAPI.addShipmentTracking(shipment.id, {
                                        status: nextTrackingStatus,
                                    });
                                    await loadBorrows();
                                } catch (error) {
                                    showToast(error.message);
                                } finally {
                                    updateTracking.disabled = false;
                                }
                            });
                            trackingSection.append(updateTracking);
                        }
                    }
                    card.append(trackingSection);
                }
                return card;
            });
            const borrowResults = data.results || [];
            const controls = borrowResults.length
                ? pagination(data, borrowPage, (value) => { borrowPage = value; }, loadBorrows)
                : null;
            if (controls) nodes.push(controls);
            borrowsList.classList.toggle("report-list", borrowResults.length > 0);
            borrowsList.replaceChildren(...nodes);
            focusRequestedTicket("borrow_id", "borrowId");
        } catch (error) {
            setMessage(borrowsList, error.message, "form-error");
        }
    };

    function focusRequestedTicket(queryName, dataName) {
        const requestedId = new URLSearchParams(location.search).get(queryName);
        if (!requestedId) return;
        const attribute = dataName === "reservationId"
            ? "[data-reservation-id]"
            : "[data-borrow-id]";
        const ticket = [...page.querySelectorAll(attribute)]
            .find((item) => item.dataset[dataName] === requestedId);
        if (ticket) {
            ticket.classList.add("is-highlighted");
            ticket.scrollIntoView({behavior: "smooth", block: "center"});
        }
    }

    page.querySelector("[data-workspace-refresh]")?.addEventListener("click", () => {
        void Promise.all([loadCart(), loadOrders(), loadReservations(), loadBorrows()]);
    });
    page.querySelector("[data-orders-refresh]")?.addEventListener("click", loadOrders);
    page.querySelector("[data-reservations-refresh]")?.addEventListener("click", loadReservations);
    page.querySelector("[data-borrows-refresh]")?.addEventListener("click", loadBorrows);
    if (workspaceView === "cart") {
        void loadCart();
    } else if (workspaceView === "borrows") {
        void Promise.all([loadReservations(), loadBorrows()]);
    } else {
        void Promise.all([loadCart(), loadOrders(), loadReservations(), loadBorrows()]);
    }
});
