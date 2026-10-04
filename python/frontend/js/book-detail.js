document.addEventListener("DOMContentLoaded", async () => {
    const container = document.querySelector("[data-book-detail]");
    if (!container) return;
    const params = new URLSearchParams(location.search);
    const id = params.get("id");
    const listingType = params.get("listing_type");
    const listingId = params.get("listing_id");
    const toLocalDateTime = (date) =>
        new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
    if (!id) {
        container.innerHTML = '<div class="empty-state"><strong>Không tìm thấy mã giáo trình.</strong><a class="button button-primary" href="books.html">Về danh sách</a></div>';
        return;
    }
    try {
        let book;
        if (listingType === "borrow") {
            if (!listingId) throw new Error("Không tìm thấy tin cho mượn.");
            const listing = await BooksAPI.lendListing(listingId);
            book = {
                ...listing.book,
                id: listing.book_id,
                title: listing.title,
                description: listing.description,
                price: listing.rental_fee,
                status: "available",
                seller: listing.seller,
                listing_type: "BORROW",
                listing_id: listing.id,
            };
        } else {
            book = await BooksAPI.get(id);
        }
        if (isLoggedIn()) {
            try {
                await loadFavoriteBookIds();
            } catch (error) {
                showToast(error.message);
            }
        }
        const images = book.images || [];
        const mainImage = container.querySelector("[data-detail-main-image]");
        mainImage.src = safeImageUrl((images.find((item) => item.is_primary) || images[0])?.image_url);
        mainImage.alt = `Ảnh ${book.title}`;
        mainImage.addEventListener("error", () => {
            mainImage.src = `https://placehold.co/640x860/f0e5d7/263b4a?text=${encodeURIComponent(book.subject?.name || "PASSBOOK")}`;
        }, {once: true});
        const thumbs = container.querySelector("[data-detail-thumbs]");
        thumbs.replaceChildren();
        images.forEach((image, index) => {
            const source = safeImageUrl(image.image_url);
            const thumb = document.createElement("button");
            thumb.className = `gallery-thumb ${index === 0 ? "is-active" : ""}`;
            thumb.type = "button";
            const thumbnailImage = document.createElement("img");
            thumbnailImage.src = source;
            thumbnailImage.alt = `Ảnh ${index + 1}`;
            thumb.append(thumbnailImage);
            thumb.addEventListener("click", () => {
                mainImage.src = source;
                thumbs.querySelector(".is-active")?.classList.remove("is-active");
                thumb.classList.add("is-active");
            });
            thumbs.append(thumb);
        });
        const status = container.querySelector("[data-detail-status]");
        status.className = "badge badge-success";
        const availabilityLabels = {
            available: "Đang bán",
            reserved: "Đang được giữ",
            sold: "Đã bán",
            hidden: "Đã ẩn",
        };
        if (book.listing_type === "BORROW") availabilityLabels.available = "Đang cho mượn";
        const conditionLabel = {
            new: "Mới",
            like_new: "Như mới",
            good: "Tốt",
            used: "Đã sử dụng",
        }[book.condition_status] || book.condition_label || "Tình trạng chưa rõ";
        status.textContent = `${availabilityLabels[book.status] || "Trạng thái chưa rõ"} · ${conditionLabel}`;
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
        container.querySelector("[data-detail-price]").textContent = book.listing_type === "BORROW"
            ? `Phí mượn · ${formatPrice(Number(book.price))}`
            : formatPrice(Number(book.price));
        const detailFields = [
            ["Tác giả", book.author],
            ["Môn học", book.subject?.name],
            ["Mã môn", book.subject?.code],
            ["Danh mục", book.category?.name],
            ["Phiên bản", book.edition_number || book.edition],
            ["ISBN", book.isbn],
            ["Nhà xuất bản", book.publisher],
            ["Năm xuất bản", book.publication_year],
            ["Ngôn ngữ", book.language?.name],
            ["Tình trạng sách", book.condition_description],
        ];
        container.querySelector("[data-detail-meta]").innerHTML = detailFields
            .map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "—")}</dd></div>`)
            .join("");
        container.querySelector("[data-detail-description]").textContent = book.description || "Chưa có mô tả.";
        const intentPanel = container.querySelector("[data-detail-intents]");
        const renderIntentPanel = (summary) => {
            intentPanel.replaceChildren();
            const counts = document.createElement("p");
            counts.className = "detail-intents__counts";
            counts.textContent = `👥 ${summary.buying_count || 0} người dự định mua · 🏷️ ${summary.selling_count || 0} người dự định bán`;
            intentPanel.append(counts);
            for (const [type, idKey, activeLabel, inactiveLabel] of [
                ["BUY", "my_buy_request_id", "✓ Bạn đang dự định mua", "Tôi dự định mua"],
                ["SELL_INTENT", "my_sell_intent_request_id", "✓ Bạn đang dự định bán", "Tôi dự định bán"],
            ]) {
                const button = document.createElement("button");
                button.className = "button button-outline";
                button.type = "button";
                button.textContent = summary[idKey] ? activeLabel : inactiveLabel;
                button.setAttribute("aria-pressed", String(Boolean(summary[idKey])));
                button.addEventListener("click", async () => {
                    if (!PassbookGuards.requireAuth()) return;
                    button.disabled = true;
                    try {
                        summary = summary[idKey]
                            ? await BooksAPI.cancelIntent(book.id, type)
                            : await BooksAPI.setIntent(book.id, type);
                        renderIntentPanel(summary);
                        showToast(summary[idKey] ? "Đã lưu dự định." : "Đã hủy dự định.");
                    } catch (error) {
                        showToast(error.message);
                        button.disabled = false;
                    }
                });
                intentPanel.append(button);
            }
        };
        try {
            renderIntentPanel(await BooksAPI.intentSummary(book.id));
        } catch (intentError) {
            intentPanel.replaceChildren(PassbookCommonComponents.emptyState(
                "Không thể tải số người dự định mua/bán.",
                intentError.message,
            ));
        }
        const sellerName = book.seller?.name || "Người bán";
        container.querySelector("[data-detail-seller]").innerHTML = `<div class="seller-line"><span class="avatar">${escapeHtml(sellerName.slice(0, 2).toUpperCase())}</span><strong>${escapeHtml(sellerName)}</strong></div><p class="caption">${escapeHtml(book.seller?.university?.name || "Trường chưa khai báo")}</p>`;
        const actions = container.querySelector("[data-detail-actions]");
        actions.innerHTML = "";
        if (book.status === "available" && Number(book.seller?.id) !== Number(PassbookAuth.getCurrentUser()?.id)) {
            const cartButton = document.createElement("button");
            cartButton.className = "button button-primary";
            cartButton.type = "button";
            cartButton.textContent = book.listing_type === "BORROW"
                ? "Thêm vào giỏ mượn"
                : "Thêm vào giỏ";
            cartButton.addEventListener("click", async () => {
                if (!PassbookGuards.requireAuth()) return;
                cartButton.disabled = true;
                try {
                    if (book.listing_type === "BORROW") {
                        await OrdersAPI.addCartItem({
                            listing_type: "BORROW",
                            listing_id: book.listing_id,
                        });
                    } else {
                        let pageNumber = 1;
                        let listing = null;
                        let hasNext = true;
                        while (hasNext && !listing) {
                            const data = await BooksAPI.listings({
                                search: book.title,
                                page: pageNumber,
                                page_size: 50,
                            });
                            listing = (data.results || []).find(
                                (item) => Number(item.book_id) === Number(book.id),
                            ) || null;
                            hasNext = Boolean(data.next);
                            pageNumber += 1;
                        }
                        if (!listing) {
                            throw new PassbookErrors.ApiError(
                                "Tin đăng không còn khả dụng để thêm vào giỏ.",
                                {status: 409, code: "listing_unavailable"},
                            );
                        }
                        await OrdersAPI.addCartItem({
                            listing_type: "SALE",
                            listing_id: listing.id,
                        });
                    }
                    window.location.assign("workspace.html#cart-title");
                } catch (error) {
                    showToast(error.message);
                } finally {
                    cartButton.disabled = false;
                }
            });
            actions.appendChild(cartButton);

            if (book.listing_type !== "BORROW") {
                const reserveButton = document.createElement("button");
                reserveButton.className = "button button-outline";
                reserveButton.type = "button";
                reserveButton.textContent = "Đặt giữ";
                reserveButton.addEventListener("click", () => {
                if (!PassbookGuards.requireAuth()) return;
                const defaultExpiry = toLocalDateTime(new Date(Date.now() + 24 * 60 * 60 * 1000));
                const minimumExpiry = toLocalDateTime(new Date());
                showModal(`<form data-reservation-form><button class="modal-close" type="button" data-modal-close>Đóng</button><h2>Đặt giữ giáo trình</h2><label class="form-label" for="reservation-expiry">Giữ đến</label><input class="form-control" id="reservation-expiry" name="expires_at" type="datetime-local" min="${minimumExpiry}" value="${defaultExpiry}" required><p class="form-error" data-reservation-error></p><div class="modal-actions"><button class="button button-primary" type="submit">Gửi yêu cầu</button></div></form>`);
                const form = document.querySelector("[data-reservation-form]");
                form.addEventListener("submit", async (event) => {
                    event.preventDefault();
                    if (!form.reportValidity()) return;
                    const submit = form.querySelector("button[type='submit']");
                    const error = form.querySelector("[data-reservation-error]");
                    submit.disabled = true;
                    error.textContent = "";
                    try {
                        const expiresAt = new Date(new FormData(form).get("expires_at").toString());
                        await ReservationsAPI.create(book.id, {expires_at: expiresAt.toISOString()});
                        closeModal();
                        showToast("Đã gửi yêu cầu đặt giữ.");
                    } catch (requestError) {
                        error.textContent = requestError.message;
                    } finally {
                        submit.disabled = false;
                    }
                });
                });
                actions.appendChild(reserveButton);
            }

            const messageButton = document.createElement("button");
            messageButton.className = "button button-primary";
            messageButton.type = "button";
            messageButton.textContent = "Nhắn tin người bán";
            messageButton.addEventListener("click", async () => {
                if (!isLoggedIn()) {
                    PassbookRouter.navigate(PassbookRouter.loginUrl());
                    return;
                }
                try {
                    const conversation = await MessagingAPI.createForBook(book.id);
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
                PassbookRouter.navigate(PassbookRouter.loginUrl());
                return;
            }
            showModal(`<form data-report-form><button class="modal-close" type="button" data-modal-close>Đóng</button><h2>Báo cáo giáo trình</h2><label class="form-label" for="report-reason">Lý do</label><input id="report-reason" required maxlength="255"><label class="form-label" for="report-description">Mô tả</label><textarea id="report-description" required maxlength="5000"></textarea><div class="modal-actions"><button class="button button-primary" type="submit">Gửi báo cáo</button></div></form>`);
            document.querySelector("[data-report-form]").addEventListener("submit", async (event) => {
                event.preventDefault();
                const reason = document.querySelector("#report-reason").value.trim();
                const description = document.querySelector("#report-description").value.trim();
                if (!reason || !description) return;
                try {
                    await ReportsAPI.create({book_id: book.id, reason, description});
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
        container.innerHTML = `<div class="empty-state"><strong>${escapeHtml(error.message)}</strong><a class="button button-primary" href="books.html">Về danh sách</a></div>`;
    }
});
