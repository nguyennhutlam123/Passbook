document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-favorites-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const list = page.querySelector("[data-favorites-list]");
    const pagination = page.querySelector("[data-favorites-pagination]");
    const error = page.querySelector("[data-favorites-error]");
    let pageNumber = Math.max(1, Number(new URLSearchParams(location.search).get("page")) || 1);
    let loadRequestId = 0;

    const renderBook = (favorite) => {
        const book = favorite.book;
        const wrapper = document.createElement("div");
        wrapper.innerHTML = PassbookBookComponents.bookCard(book, {favorite: true});
        const card = wrapper.firstElementChild;
        const remove = card.querySelector("[data-favorite]");
        remove?.addEventListener("click", async (event) => {
            event.preventDefault();
            event.stopPropagation();
            remove.disabled = true;
            try {
                await FavoritesAPI.remove(book.id);
                await load();
            } catch (requestError) {
                error.textContent = requestError.message;
                remove.disabled = false;
            }
        });
        return card;
    };

    const load = async () => {
        const requestId = ++loadRequestId;
        error.textContent = "";
        list.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải sách yêu thích..."));
        pagination.replaceChildren();
        try {
            const data = await FavoritesAPI.list({page: pageNumber, page_size: 20});
            if (requestId !== loadRequestId) return;
            const favorites = data.results || [];
            if (favorites.length) {
                list.replaceChildren(...favorites.map(renderBook));
            } else {
                const empty = PassbookCommonComponents.emptyStateElement(
                    "Bạn chưa lưu sách yêu thích nào.",
                    "Khám phá sách và lưu những cuốn bạn quan tâm.",
                );
                const explore = document.createElement("a");
                explore.className = "button button-primary";
                explore.href = "books.html";
                explore.textContent = "Khám phá sách";
                empty.append(explore);
                list.replaceChildren(empty);
            }
            const controls = PassbookCommonComponents.pagination({
                previous: data.previous,
                next: data.next,
                onPrevious: () => {
                    pageNumber = Math.max(1, pageNumber - 1);
                    history.replaceState(null, "", `favorites.html?page=${pageNumber}`);
                    void load();
                },
                onNext: () => {
                    pageNumber += 1;
                    history.replaceState(null, "", `favorites.html?page=${pageNumber}`);
                    void load();
                },
            });
            pagination.replaceChildren(controls);
        } catch (requestError) {
            if (requestId !== loadRequestId) return;
            const failure = PassbookCommonComponents.emptyStateElement(
                "Không thể tải sách yêu thích.",
                "Kiểm tra kết nối rồi thử lại.",
            );
            const retry = document.createElement("button");
            retry.className = "button button-outline";
            retry.type = "button";
            retry.textContent = "Thử lại";
            retry.addEventListener("click", () => void load());
            failure.append(retry);
            list.replaceChildren(failure);
        }
    };
    void load();
});
