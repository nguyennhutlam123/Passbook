document.addEventListener("DOMContentLoaded", async () => {
    const page = document.querySelector("[data-public-profile]");
    if (!page) return;

    const userId = new URLSearchParams(location.search).get("id");
    const grid = page.querySelector("[data-profile-books]");
    const error = page.querySelector("[data-profile-error]");
    const pagination = page.querySelector("[data-profile-pagination]");
    const tabs = [...page.querySelectorAll("[data-profile-type]")];
    let listingType = "ALL";
    let pageNumber = 1;
    let requestId = 0;

    if (!userId || !/^\d+$/.test(userId)) {
        page.querySelector("[data-public-name]").textContent = "Không tìm thấy người dùng.";
        grid.replaceChildren();
        return;
    }

    const renderPagination = (result) => {
        pagination.replaceChildren();
        const buttons = [];
        if (result.previous) {
            const previous = document.createElement("button");
            previous.className = "button button-outline";
            previous.type = "button";
            previous.textContent = "Trước";
            previous.addEventListener("click", () => {
                pageNumber -= 1;
                void loadListings();
            });
            buttons.push(previous);
        }
        if (result.next) {
            const next = document.createElement("button");
            next.className = "button button-outline";
            next.type = "button";
            next.textContent = "Tiếp";
            next.addEventListener("click", () => {
                pageNumber += 1;
                void loadListings();
            });
            buttons.push(next);
        }
        pagination.replaceChildren(...buttons);
    };

    const loadListings = async () => {
        const currentRequest = ++requestId;
        error.textContent = "";
        grid.innerHTML = '<p class="loading-state">Đang tải tin đăng...</p>';
        try {
            const result = await UsersAPI.publicListings(userId, {
                type: listingType,
                page: pageNumber,
                page_size: 12,
            });
            if (currentRequest !== requestId) return;
            const books = result.results || [];
            if (isLoggedIn()) {
                try {
                    await loadFavoriteBookIds();
                } catch (favoriteError) {
                    showToast(favoriteError.message);
                }
            }
            if (currentRequest !== requestId) return;
            grid.replaceChildren(...(
                books.length
                    ? books.map((book) => {
                        const wrapper = document.createElement("div");
                        wrapper.innerHTML = renderBookCard({
                            ...book,
                            subject: book.category || book.subject,
                        });
                        return wrapper.firstElementChild;
                    })
                    : [PassbookCommonComponents.emptyStateElement(
                        "Chưa có tin đăng công khai trong danh mục này.",
                        "Tin nháp, chờ duyệt, đã từ chối hoặc không còn khả dụng sẽ không hiển thị.",
                    )]
            ));
            bindFavoriteButtons(grid);
            bindBorrowButtons(grid);
            attachImageFallbacks(grid);
            page.querySelector("[data-public-listing-count]").textContent = String(result.count || 0);
            renderPagination(result);
        } catch (requestError) {
            if (currentRequest !== requestId) return;
            grid.replaceChildren();
            pagination.replaceChildren();
            error.textContent = requestError.message;
        }
    };

    tabs.forEach((tab) => tab.addEventListener("click", () => {
        listingType = tab.dataset.profileType;
        pageNumber = 1;
        tabs.forEach((item) => item.classList.toggle("is-active", item === tab));
        void loadListings();
    }));

    try {
        const profile = await UsersAPI.sellerProfile(userId);
        page.querySelector("[data-public-name]").textContent = profile.name || "Người dùng PassBook";
        page.querySelector("[data-public-university]").textContent =
            profile.university?.name || "Chưa cập nhật trường";
        page.querySelector("[data-public-avatar]").textContent =
            (profile.name || "PB").slice(0, 2).toUpperCase();
        const avatar = profile.avatar;
        if (avatar && /^https:\/\//i.test(avatar)) {
            page.querySelector("[data-public-avatar]").replaceChildren(
                Object.assign(document.createElement("img"), {
                    src: avatar,
                    alt: "",
                    referrerPolicy: "no-referrer",
                }),
            );
        }
        await loadListings();
    } catch (profileError) {
        page.querySelector("[data-public-name]").textContent = "Không tìm thấy người dùng.";
        page.querySelector("[data-public-university]").textContent = "";
        error.textContent = profileError.message;
        grid.replaceChildren();
    }
});
