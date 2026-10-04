document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-workspace-page]");
    if (!page || !PassbookGuards.requireAuth()) return;

    const cartItems = page.querySelector("[data-cart-items]");
    const cartTotal = page.querySelector("[data-cart-total]");
    const checkoutForm = page.querySelector("[data-checkout-form]");
    const cartError = page.querySelector("[data-cart-error]");
    const ordersList = page.querySelector("[data-orders-list]");
    const reservationsList = page.querySelector("[data-reservations-list]");
    const borrowsList = page.querySelector("[data-borrows-list]");
    let currentUser = PassbookAuth.getCurrentUser() || {};
    window.addEventListener("passbook:user-updated", (event) => {
        currentUser = event.detail;
    });
    const checkoutKeyStorage = "passbook.checkout.idempotencyKey";
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
        });
    };

    const loadCart = async () => {
        try {
            const cart = await OrdersAPI.cart();
            const items = Array.isArray(cart.items) ? cart.items : [];
            if (!items.length) {
                setMessage(cartItems, "Giỏ hàng đang trống.");
                cartTotal.textContent = "";
                checkoutForm.hidden = true;
                return;
            }
            cartItems.replaceChildren(...items.map(itemCard));
            cartTotal.textContent = `Tổng cộng: ${money(items.reduce((sum, item) => sum + Number(item.unit_price), 0))}`;
            checkoutForm.hidden = false;
            cartError.textContent = "";
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

    checkoutForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!checkoutForm.reportValidity()) return;
        const data = new FormData(checkoutForm);
        const shippingSnapshot = {
            recipient_name: data.get("recipient_name").toString().trim(),
            phone: data.get("phone").toString().trim(),
            address_line: data.get("address_line").toString().trim(),
            city: data.get("city").toString().trim(),
        };
        const borrow = {};
        for (const input of page.querySelectorAll("[data-borrow-listing]")) {
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
        try {
            const result = await OrdersAPI.checkout({
                idempotency_key: checkoutKey(),
                shipping_address_snapshot: shippingSnapshot,
                borrow,
            });
            sessionStorage.removeItem(checkoutKeyStorage);
            showToast(`Đã tạo nhóm đơn ${result.checkout_code}.`);
            await Promise.all([loadCart(), loadOrders()]);
        } catch (error) {
            cartError.textContent = error.message;
        } finally {
            submit.disabled = false;
        }
    });

    const addOrderDetails = async (container, order) => {
        const detail = await OrdersAPI.get(order.id);
        const list = document.createElement("div");
        list.className = "order-detail";
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
            addAction("confirm", "Xác nhận");
            addAction("reject", "Từ chối");
        }
        if (["PENDING", "CONFIRMED"].includes(reservation.status) && isRequester) {
            addAction("cancel", "Hủy yêu cầu");
        }
        if (reservation.status === "CONFIRMED" && (isRequester || isOwner)) {
            addAction("complete", "Hoàn tất");
        }
    };

    const loadReservations = async () => {
        setMessage(reservationsList, "Đang tải yêu cầu...", "loading-state");
        try {
            const data = await ReservationsAPI.list({page: reservationPage, page_size: 50});
            const nodes = (data.results || []).map((reservation) => {
                const card = document.createElement("article");
                card.className = "report-item";
                const title = document.createElement("strong");
                title.textContent = `Đặt giữ sách #${reservation.book_id}`;
                const status = document.createElement("span");
                status.textContent = `${reservation.status} · hết hạn ${new Date(reservation.expires_at).toLocaleString("vi-VN")}`;
                card.append(title, status);
                reservationActions(reservation, card);
                return card;
            });
            if (!nodes.length) {
                nodes.push(PassbookCommonComponents.emptyState("Chưa có yêu cầu đặt giữ."));
            }
            const controls = pagination(
                data,
                reservationPage,
                (value) => { reservationPage = value; },
                loadReservations,
            );
            if (controls) nodes.push(controls);
            reservationsList.replaceChildren(...nodes);
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
        if (["ACTIVE", "OVERDUE"].includes(borrow.status)) return [["request-return", "Yêu cầu trả"]];
        if (borrow.status === "RETURN_REQUESTED") return [["return", "Đã nhận lại sách"]];
        if (borrow.status === "RETURNED") return [["complete", "Hoàn tất giao dịch"]];
        return [];
    };

    const loadBorrows = async () => {
        setMessage(borrowsList, "Đang tải giao dịch...", "loading-state");
        try {
            const data = await OrdersAPI.borrowOrders({page: borrowPage, page_size: 50});
            const nodes = (data.results || []).map((borrow) => {
                const card = document.createElement("article");
                card.className = "report-item";
                const title = document.createElement("strong");
                title.textContent = `Giao dịch mượn #${borrow.id}`;
                const status = document.createElement("span");
                status.textContent = `${borrow.status} · trả dự kiến ${new Date(borrow.expected_return_at).toLocaleString("vi-VN")}`;
                card.append(title, status);
                borrowActionOptions(borrow).forEach(([action, label]) => {
                    const button = document.createElement("button");
                    button.className = "button button-outline";
                    button.type = "button";
                    button.textContent = label;
                    button.addEventListener("click", async () => {
                        button.disabled = true;
                        try {
                            if (action === "request-return") {
                                await OrdersAPI.requestBorrowReturn(borrow.id, {});
                            } else {
                                await OrdersAPI.borrowAction(borrow.id, action);
                            }
                            await loadBorrows();
                        } catch (error) {
                            showToast(error.message);
                        } finally {
                            button.disabled = false;
                        }
                    });
                    card.append(button);
                });
                return card;
            });
            if (!nodes.length) {
                nodes.push(PassbookCommonComponents.emptyState("Chưa có giao dịch mượn."));
            }
            const controls = pagination(data, borrowPage, (value) => { borrowPage = value; }, loadBorrows);
            if (controls) nodes.push(controls);
            borrowsList.replaceChildren(...nodes);
        } catch (error) {
            setMessage(borrowsList, error.message, "form-error");
        }
    };

    page.querySelector("[data-workspace-refresh]").addEventListener("click", () => {
        void Promise.all([loadCart(), loadOrders(), loadReservations(), loadBorrows()]);
    });
    page.querySelector("[data-orders-refresh]").addEventListener("click", loadOrders);
    page.querySelector("[data-reservations-refresh]").addEventListener("click", loadReservations);
    page.querySelector("[data-borrows-refresh]").addEventListener("click", loadBorrows);
    void Promise.all([loadCart(), loadOrders(), loadReservations(), loadBorrows()]);
});
