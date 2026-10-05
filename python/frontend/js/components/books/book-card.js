(function (global) {
    "use strict";

    function fallbackImage(book) {
        const subject = book.subject?.name || book.subject || "PASSBOOK";
        return `https://placehold.co/640x860/f0e5d7/263b4a?text=${encodeURIComponent(subject.slice(0, 24))}`;
    }

    function bookCard(book, {favorite = false} = {}) {
        const escape = global.PassbookCommonComponents.escapeHtml;
        const image = book.primary_image || (Array.isArray(book.images)
            ? (book.images.find((entry) => entry.is_primary) || book.images[0])
            : null);
        const title = escape(book.title || "Giáo trình");
        const subject = escape(book.subject?.name || book.subject || "Giáo trình");
        const code = escape(book.subject?.code || book.subjectCode || "");
        const seller = escape(book.seller?.name || "Người bán");
        const category = book.category?.name || book.category_name || "";
        const sellerLocation = book.seller?.university?.name
            || book.university?.name
            || (typeof book.location === "string" ? book.location : "")
            || (typeof book.city === "string" ? book.city : "");
        const conditionValue = book.condition_status || book.condition || "";
        const condition = escape({
            new: "Mới",
            like_new: "Như mới",
            good: "Tốt",
            used: "Đã sử dụng",
        }[conditionValue] || book.condition_label || conditionValue || "Đang cập nhật");
        const statusLabels = {
            sold: "Đã bán",
            reserved: "Có yêu cầu đang xử lý",
            on_loan: "Đang cho mượn",
            hidden: "Đã ẩn",
            deleted: "Đã xóa",
        };
        const badge = statusLabels[book.status]
            ? global.PassbookCommonComponents.statusBadge(book.status, statusLabels[book.status])
            : global.PassbookCommonComponents.statusBadge("condition", condition);
        const listingBadge = book.listing_type === "BORROW"
            ? global.PassbookCommonComponents.statusBadge("borrow", "Cho mượn")
            : "";
        const rawImageUrl = image?.image_url || "";
        const imageUrl = global.safeImageUrl(rawImageUrl || fallbackImage(book));
        const id = encodeURIComponent(String(book.id));
        const detailUrl = book.listing_type === "BORROW"
            ? `book-detail.html?id=${id}&listing_type=borrow&listing_id=${encodeURIComponent(book.listing_id)}`
            : `book-detail.html?id=${id}`;
        const pressed = String(Boolean(favorite));
        const favoriteAction = book.listing_type === "BORROW"
            ? ""
            : `<button class="favorite-button ${favorite ? "is-favorite" : ""}" type="button" data-favorite="${id}" aria-label="${favorite ? "Bỏ lưu" : "Lưu"} ${title}" aria-pressed="${pressed}">${favorite ? "♥" : "♡"}</button>`;
        const isOwnBorrowListing = book.listing_type === "BORROW"
            && Number(book.seller?.id) === Number(global.PassbookAuth?.getCurrentUser()?.id);
        const borrowAction = book.listing_type === "BORROW"
            ? isOwnBorrowListing
                ? '<span class="caption">Tin đăng của bạn · không thể tự mượn</span>'
                : `<button class="button button-primary" type="button" data-borrow-request="${escape(book.listing_id)}">Thêm phiếu mượn vào giỏ</button>`
            : "";
        const isOwnSaleListing = book.listing_type !== "BORROW"
            && Number(book.seller?.id) === Number(global.PassbookAuth?.getCurrentUser()?.id);
        const saleAction = book.listing_type !== "BORROW" && book.listing_id
            ? isOwnSaleListing
                ? '<span class="caption">Tin đăng của bạn · không thể tự mua</span>'
                : `<button class="button button-primary" type="button" data-sale-add-to-cart="${escape(book.listing_id)}">Thêm vào giỏ</button>`
            : "";
        const borrowTerms = book.listing_type === "BORROW"
            ? `<p class="book-card__subject">${book.borrow_terms?.max_days ? `Tối đa ${escape(book.borrow_terms.max_days)} ngày` : "Thời hạn theo thỏa thuận"}${Number(book.deposit_amount) > 0 ? ` · Cọc ${global.formatPrice(Number(book.deposit_amount))}` : ""}</p>`
            : "";
        const reviewCount = Number(book.review_count) || 0;
        const averageRating = Number(book.average_rating);
        const ratingSummary = reviewCount && Number.isFinite(averageRating)
            ? `<p class="book-card__rating" aria-label="Đánh giá ${averageRating.toFixed(1)} trên 5 sao, ${reviewCount} lượt">${"★"} ${averageRating.toFixed(1)} <span>(${reviewCount})</span></p>`
            : "";
        return `<article class="book-card">
            <a class="book-card__cover-link" href="${detailUrl}" aria-label="Xem ${title}">
                <div class="book-card__cover">
                    <img class="book-card__image" src="${imageUrl}" data-fallback="${fallbackImage(book)}" alt="Ảnh bìa ${title}" loading="lazy">
                    ${favoriteAction}
                </div>
            </a>
            <div class="book-card__body">
                ${listingBadge}
                <h3 class="book-card__title"><a href="${detailUrl}">${title}</a></h3>
                ${category ? `<p class="book-card__category">${escape(category)}</p>` : ""}
                <p class="book-card__subject">${subject}${code ? ` · ${code}` : ""}</p>
                ${badge}
                ${ratingSummary}
                <strong class="price">${book.listing_type === "BORROW" ? "Phí mượn · " : ""}${global.formatPrice(Number(book.price) || 0)}</strong>
                ${borrowTerms}
                <div class="seller-line"><span>${seller}</span></div>
                ${sellerLocation ? `<p class="book-card__location">${escape(sellerLocation)}</p>` : ""}
                ${saleAction}
                ${borrowAction}
            </div>
        </article>`;
    }

    global.PassbookBookComponents = Object.freeze({bookCard});
})(window);
