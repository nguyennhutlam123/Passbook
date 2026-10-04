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
        const conditionValue = book.condition_status || book.condition || "";
        const condition = escape({
            new: "Mới",
            like_new: "Như mới",
            good: "Tốt",
            used: "Đã sử dụng",
        }[conditionValue] || book.condition_label || conditionValue || "Đang cập nhật");
        const editionInfo = [book.edition, book.publication_year]
            .filter(Boolean)
            .map(escape)
            .join(" · ");
        const statusLabels = {
            sold: "Đã bán",
            reserved: "Đã giữ",
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
        const borrowAction = book.listing_type === "BORROW"
            ? `<button class="button button-primary" type="button" data-borrow-request="${escape(book.listing_id)}" data-book-id="${id}" data-title="${title}">Đăng ký mượn</button>`
            : "";
        const intentCounts = book.listing_type === "BORROW"
            ? ""
            : `<p class="book-card__intent-counts"><span>👥 ${Number(book.buying_intent_count) || 0} dự định mua</span><span>🏷️ ${Number(book.selling_intent_count) || 0} dự định bán</span></p>`;
        return `<article class="book-card">
            <a class="book-card__cover-link" href="${detailUrl}" aria-label="Xem ${title}">
                <div class="book-card__cover">
                    <img class="book-card__image" src="${imageUrl}" data-fallback="${fallbackImage(book)}" alt="Ảnh bìa ${title}" loading="lazy">
                    ${favoriteAction}
                </div>
            </a>
            <div class="book-card__body">
                ${listingBadge}
                ${badge}
                <h3 class="book-card__title"><a href="${detailUrl}">${title}</a></h3>
                <p class="book-card__subject">${subject}${code ? ` · ${code}` : ""}</p>
                ${editionInfo ? `<p class="book-card__subject">${editionInfo}</p>` : ""}
                <strong class="price">${book.listing_type === "BORROW" ? "Phí mượn · " : ""}${global.formatPrice(Number(book.price) || 0)}</strong>
                ${intentCounts}
                <div class="seller-line"><span>${seller}</span></div>
                ${borrowAction}
            </div>
        </article>`;
    }

    global.PassbookBookComponents = Object.freeze({bookCard});
})(window);
