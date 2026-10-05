document.addEventListener("DOMContentLoaded", async () => {
    const container = document.querySelector("[data-book-detail]");
    if (!container) return;
    const params = new URLSearchParams(location.search);
    const id = params.get("id");
    const listingType = params.get("listing_type");
    const listingId = params.get("listing_id");
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
                status: listing.book.status,
                seller: listing.seller,
                listing_type: "BORROW",
                listing_id: listing.id,
                images: listing.images || [],
                borrow_terms: listing.borrow_terms,
                deposit_amount: listing.deposit_amount,
                reviews: listing.reviews || [],
                average_rating: listing.average_rating,
                review_count: listing.review_count,
            };
        } else {
            book = await BooksAPI.get(id);
        }
        container.querySelector("[data-detail-back]").href =
            book.listing_type === "BORROW" ? "borrow.html" : "books.html";
        if (isLoggedIn()) {
            try {
                await loadFavoriteBookIds();
            } catch (error) {
                showToast(error.message);
            }
        }
        const images = book.images || [];
        const mainImage = container.querySelector("[data-detail-main-image]");
        const fallbackImage = "https://placehold.co/640x860/f0e5d7/263b4a?text=PASSBOOK";
        const primaryImage = images.find((item) => item.is_primary) || images[0];
        mainImage.src = primaryImage?.image_url
            ? safeImageUrl(primaryImage.image_url)
            : fallbackImage;
        mainImage.alt = `Ảnh ${book.title}`;
        mainImage.addEventListener("error", () => {
            if (mainImage.src !== fallbackImage) mainImage.src = fallbackImage;
        });
        const thumbs = container.querySelector("[data-detail-thumbs]");
        thumbs.replaceChildren();
        images.forEach((image, index) => {
            const source = safeImageUrl(image.image_url);
            const thumb = document.createElement("button");
            thumb.className = `gallery-thumb ${image === primaryImage ? "is-active" : ""}`;
            thumb.type = "button";
            const thumbnailImage = document.createElement("img");
            thumbnailImage.src = source;
            thumbnailImage.alt = `Ảnh ${index + 1}`;
            thumbnailImage.addEventListener("error", () => {
                thumbnailImage.src = fallbackImage;
            }, {once: true});
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
            available: book.listing_type === "BORROW" ? "Đang cho mượn" : "Đang bán",
            reserved: "Có yêu cầu đang xử lý",
            on_loan: "Đang được mượn",
            sold: "Đã bán",
            hidden: "Đã ẩn",
        };
        const conditionLabel = {
            new: "Mới",
            like_new: "Như mới",
            good: "Tốt",
            used: "Đã sử dụng",
        }[book.condition_status] || book.condition_label || "Tình trạng chưa rõ";
        status.textContent = `${availabilityLabels[book.status] || "Trạng thái chưa rõ"} · ${conditionLabel}`;
        container.querySelector("[data-detail-title]").textContent = book.title;
        if (book.listing_type !== "BORROW") {
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
        }
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
            ...(book.listing_type === "BORROW" ? [
                ["Trường", book.seller?.university?.name],
                ["Khoa", book.seller?.faculty?.name],
                ["Ngành", book.seller?.major?.name],
                ["Người cho mượn", book.seller?.name],
                ["Thời hạn mượn tối đa", book.borrow_terms?.max_days
                    ? `${book.borrow_terms.max_days} ngày`
                    : null],
                ["Phí trễ hạn mỗi ngày", book.borrow_terms?.late_fee_per_day],
                ["Cách trả sách", {
                    IN_PERSON: "Gặp trực tiếp",
                    POSTAL: "Gửi bưu điện",
                }[book.borrow_terms?.return_method] || book.borrow_terms?.return_method],
                ["Bên chịu phí giao nhận", {
                    BORROWER: "Người mượn",
                    LENDER: "Người cho mượn",
                }[book.borrow_terms?.shipping_paid_by] || book.borrow_terms?.shipping_paid_by],
                ["Bắt buộc đặt cọc", book.borrow_terms?.deposit_required ? "Có" : "Không"],
                ["Tiền đặt cọc", book.deposit_amount],
                ["Điều kiện mượn", book.borrow_terms?.notes],
            ] : []),
        ];
        container.querySelector("[data-detail-meta]").innerHTML = detailFields
            .map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "—")}</dd></div>`)
            .join("");
        container.querySelector("[data-detail-description]").textContent = book.description || "Chưa có mô tả.";
        const reviews = book.reviews || [];
        const reviewPanel = container.querySelector("[data-detail-reviews]");
        const reviewTitle = reviewPanel.querySelector("[data-review-title]");
        const reviewCount = Number(book.review_count ?? reviews.length);
        const averageRating = Number(book.average_rating);
        reviewTitle.textContent = `Đánh giá sách (${reviewCount})`;
        reviewPanel.querySelector("[data-review-summary]").textContent = reviewCount
            ? `${Number.isFinite(averageRating) ? averageRating.toFixed(1) : "—"} / 5 sao · ${reviewCount} đánh giá`
            : "Chưa có đánh giá cho sách này.";
        const reviewList = reviewPanel.querySelector("[data-review-list]");
        reviewList.replaceChildren(...(reviews.length
            ? reviews.map((review) => {
                const card = document.createElement("article");
                card.className = "review-card";
                const heading = document.createElement("strong");
                heading.textContent = `${"★".repeat(review.rating)}${"☆".repeat(5 - review.rating)} · ${review.reviewer?.name || "Người dùng"}`;
                const time = document.createElement("time");
                time.dateTime = review.created_at;
                time.textContent = new Date(review.created_at).toLocaleDateString("vi-VN");
                const comment = document.createElement("p");
                comment.textContent = review.comment || "Không có nhận xét.";
                card.append(heading, time, comment);
                return card;
            })
            : [PassbookCommonComponents.emptyState("Hãy là người đầu tiên đánh giá sau khi hoàn tất giao dịch.")]));
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
        if (book.listing_type === "BORROW") {
            intentPanel.hidden = true;
        } else {
            try {
                renderIntentPanel(await BooksAPI.intentSummary(book.id));
            } catch (intentError) {
                intentPanel.replaceChildren(PassbookCommonComponents.emptyState(
                    "Không thể tải số người dự định mua/bán.",
                    intentError.message,
                ));
            }
        }
        const sellerName = book.seller?.name || "Người bán";
        const sellerPanel = container.querySelector("[data-detail-seller]");
        sellerPanel.replaceChildren();
        const sellerHeading = document.createElement("strong");
        sellerHeading.textContent = book.listing_type === "BORROW" ? "Người cho mượn" : "Người đăng";
        const sellerLine = document.createElement("div");
        sellerLine.className = "seller-line";
        const avatar = document.createElement("span");
        avatar.className = "avatar";
        avatar.textContent = sellerName.slice(0, 2).toUpperCase();
        const profileLink = document.createElement("a");
        profileLink.href = `public-profile.html?id=${encodeURIComponent(book.seller.id)}`;
        profileLink.textContent = sellerName;
        sellerLine.append(avatar, profileLink);
        const school = document.createElement("p");
        school.className = "caption";
        school.textContent = book.seller?.university?.name || "Trường chưa khai báo";
        const viewProfile = document.createElement("a");
        viewProfile.className = "text-link";
        viewProfile.href = profileLink.href;
        viewProfile.textContent = "Xem trang cá nhân";
        sellerPanel.append(sellerHeading, sellerLine, school, viewProfile);
        const actions = container.querySelector("[data-detail-actions]");
        actions.innerHTML = "";
        if (book.status === "available" && Number(book.seller?.id) !== Number(PassbookAuth.getCurrentUser()?.id)) {
            if (book.listing_type === "BORROW") {
                const borrowButton = document.createElement("button");
                borrowButton.className = "button button-primary";
                borrowButton.type = "button";
                borrowButton.textContent = "Tạo phiếu mượn";
                borrowButton.addEventListener("click", () =>
                    void addBorrowListingToCart(book.listing_id, borrowButton),
                );
                actions.appendChild(borrowButton);
            } else {
                const findSaleListingId = async () => {
                    if (Number.isSafeInteger(Number(book.listing_id)) && Number(book.listing_id) > 0) {
                        return Number(book.listing_id);
                    }
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
                            "Tin đăng không còn khả dụng để mua.",
                            {status: 409, code: "listing_unavailable"},
                        );
                    }
                    return listing.id;
                };
                const addToCart = async (button, buyNow) => {
                    try {
                        const listingId = await findSaleListingId();
                        await addSaleListingToCart(listingId, button, {buyNow});
                    } catch (error) {
                        showToast(error.message);
                    }
                };
                const cartButton = document.createElement("button");
                cartButton.className = "button button-outline";
                cartButton.type = "button";
                cartButton.textContent = "Thêm vào giỏ";
                cartButton.addEventListener("click", () => addToCart(cartButton, false));
                const buyNowButton = document.createElement("button");
                buyNowButton.className = "button button-primary";
                buyNowButton.type = "button";
                buyNowButton.textContent = "Mua ngay";
                buyNowButton.addEventListener("click", () => addToCart(buyNowButton, true));
                actions.append(cartButton);
                actions.append(buyNowButton);
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
            const reportListingId = book.listing_id || listingId;
            showModal(`<form data-report-form><button class="modal-close" type="button" data-modal-close>Đóng</button><h2>Báo cáo</h2><label class="form-label" for="report-target">Đối tượng</label><select class="form-control" id="report-target" name="target"><option value="book">Thông tin sách</option>${reportListingId ? '<option value="listing">Tin đăng</option>' : ""}${book.seller?.id ? '<option value="user">Người dùng</option>' : ""}</select><label class="form-label" for="report-reason">Lý do</label><select class="form-control" id="report-reason" name="reason" required><option value="INAPPROPRIATE_CONTENT">Nội dung không phù hợp</option><option value="INCORRECT_BOOK_INFO">Thông tin sách sai</option><option value="SPAM">Spam</option><option value="SCAM">Lừa đảo</option><option value="POLICY_VIOLATION">Nội dung vi phạm</option><option value="OTHER">Lý do khác</option></select><label class="form-label" for="report-description">Mô tả (không bắt buộc)</label><textarea class="form-control" id="report-description" name="description" maxlength="5000"></textarea><div class="modal-actions"><button class="button button-primary" type="submit">Gửi báo cáo</button></div></form>`);
            document.querySelector("[data-report-form]").addEventListener("submit", async (event) => {
                event.preventDefault();
                const form = event.currentTarget;
                const formData = new FormData(form);
                const target = formData.get("target");
                const report = {
                    reason: formData.get("reason"),
                    description: formData.get("description").toString().trim(),
                    ...(target === "book" ? {book_id: book.id} : {}),
                    ...(target === "listing" && book.listing_type === "BORROW"
                        ? {lend_listing_id: reportListingId}
                        : target === "listing" ? {sale_listing_id: reportListingId} : {}),
                    ...(target === "user" ? {reported_user_id: book.seller.id} : {}),
                };
                try {
                    await ReportsAPI.create(report);
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
