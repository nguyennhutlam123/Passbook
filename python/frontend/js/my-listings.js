document.addEventListener("DOMContentLoaded", async () => {
    const page = document.querySelector("[data-my-listings-page]");
    if (!page || !PassbookGuards.requireAuth()) return;

    const grid = page.querySelector("[data-my-listings-grid]");
    const empty = page.querySelector("[data-my-listings-empty]");
    const errorMessage = page.querySelector("[data-my-listings-error]");
    let activeFilter = "all";
    let books = [];

    const render = () => {
        const visible = books.filter((book) => {
            if (activeFilter === "available") return book.status === "available";
            if (activeFilter === "inactive") return book.status !== "available";
            return true;
        });
        empty.hidden = visible.length > 0;
        grid.hidden = !visible.length;
        grid.innerHTML = visible.map((book) => `<div class="my-listing">
            ${renderBookCard(book)}
            <div class="listing-actions">
                <button class="button button-outline" type="button" data-edit="${book.id}">Sửa tin</button>
                <button class="button button-outline" type="button" data-delete="${book.id}">Xóa tin</button>
                ${book.status === "available" && book.listing_type !== "BORROW" ? `<button class="button button-outline" type="button" data-sold="${book.id}">Đánh dấu đã bán</button>` : ""}
            </div>
        </div>`).join("");

        grid.querySelectorAll("[data-edit]").forEach((button) => button.addEventListener("click", () => {
            const book = books.find((item) => item.id === Number(button.dataset.edit));
            if (!book) return;
            localStorage.setItem("editingListing", JSON.stringify(book));
            window.location.assign("sell.html");
        }));
        grid.querySelectorAll("[data-delete]").forEach((button) => button.addEventListener("click", async () => {
            if (!window.confirm("Bạn có chắc muốn xóa tin đăng này?")) return;
            button.disabled = true;
            try {
                await BooksAPI.delete(button.dataset.delete);
                await loadBooks();
                showToast("Đã xóa tin đăng.");
            } catch (requestError) {
                errorMessage.textContent = requestError.message;
                button.disabled = false;
            }
        }));
        grid.querySelectorAll("[data-sold]").forEach((button) => button.addEventListener("click", async () => {
            button.disabled = true;
            try {
                await BooksAPI.markSold(button.dataset.sold);
                await loadBooks();
                showToast("Đã đánh dấu đã bán.");
            } catch (requestError) {
                errorMessage.textContent = requestError.message;
                button.disabled = false;
            }
        }));
        bindFavoriteButtons(grid);
    };

    const loadBooks = async () => {
        errorMessage.textContent = "";
        grid.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải tin đăng..."));
        try {
            const data = await BooksAPI.mine({page_size: 50});
            books = data.results || [];
            render();
        } catch (requestError) {
            books = [];
            grid.replaceChildren();
            empty.hidden = false;
            empty.querySelector("strong").textContent = "Không thể tải tin đăng";
            errorMessage.textContent = requestError.message;
        }
    };

    page.querySelectorAll("[data-listing-filter]").forEach((button) => button.addEventListener("click", () => {
        activeFilter = button.dataset.listingFilter;
        page.querySelectorAll("[data-listing-filter]").forEach((filter) => {
            const selected = filter === button;
            filter.className = `button${selected ? " is-active" : " button-outline"}`;
            filter.setAttribute("aria-pressed", String(selected));
        });
        render();
    }));

    try {
        await loadFavoriteBookIds();
    } catch (requestError) {
        showToast(requestError.message);
    }
    await loadBooks();
});
