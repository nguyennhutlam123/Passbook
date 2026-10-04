document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-favorites-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const list = page.querySelector("[data-favorites-list]");
    const pagination = page.querySelector("[data-favorites-pagination]");
    const error = page.querySelector("[data-favorites-error]");
    let pageNumber = Math.max(1, Number(new URLSearchParams(location.search).get("page")) || 1);

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
        error.textContent = "";
        list.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải sách yêu thích..."));
        pagination.replaceChildren();
        try {
            const data = await FavoritesAPI.list({page: pageNumber, page_size: 20});
            const favorites = data.results || [];
            list.replaceChildren(...(favorites.length
                ? favorites.map(renderBook)
                : [PassbookCommonComponents.emptyStateElement(
                    "Bạn chưa lưu sách yêu thích nào.",
                    "Nhấn biểu tượng trái tim trên sách để lưu vào danh sách này.",
                )]));
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
            list.replaceChildren(PassbookCommonComponents.emptyStateElement(
                "Không thể tải sách yêu thích.",
                requestError.message,
            ));
        }
    };
    void load();
});
