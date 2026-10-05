const catalogFilters = [
    ["#catalog-query", "search", "q"],
    ["#filter-school", "university"],
    ["#filter-faculty", "faculty"],
    ["#filter-major", "major"],
    ["#filter-subject", "subject"],
    ["#filter-author", "author"],
    ["#filter-isbn", "isbn"],
    ["#filter-edition", "edition"],
    ["#filter-year", "publication_year"],
    ["#filter-language", "language_id"],
    ["#filter-category", "category_id"],
    ["#filter-min-price", "min_price"],
    ["#filter-max-price", "max_price"],
    ["#sort-books", "sort"],
];
let catalogRequestId = 0;
let borrowCatalog = false;
const catalogPage = () => borrowCatalog ? "borrow.html" : "books.html";

function renderApiBookCard(book) {
    return renderBookCard(book);
}

function bindBorrowButtons(root) {
    root.querySelectorAll("[data-borrow-request]").forEach((button) => {
        button.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (!PassbookGuards.requireAuth()) return;
            openBorrowReservationDialog({
                bookId: button.dataset.bookId,
                listingId: button.dataset.borrowRequest,
                title: button.dataset.title,
            });
        });
    });
}

function currentCatalogParams(page) {
    const params = {page, page_size: 10};
    for (const [selector, key] of catalogFilters) {
        const value = document.querySelector(selector)?.value.trim();
        if (value) params[key] = key === "sort" ? value.replace("-", "_") : value;
    }
    const condition = document.querySelector("input[name='condition']:checked")?.value;
    if (condition) params.condition_status = condition;
    return params;
}

function syncCatalogUrl(page) {
    const params = new URLSearchParams();
    for (const [selector, key, urlKey = key] of catalogFilters) {
        const value = document.querySelector(selector)?.value.trim();
        if (value) params.set(urlKey, value);
    }
    const condition = document.querySelector("input[name='condition']:checked")?.value;
    if (condition) params.set("condition_status", condition);
    if (page > 1) params.set("page", String(page));
    const query = params.toString();
    history.replaceState(null, "", `${catalogPage()}${query ? `?${query}` : ""}`);
}

function populateOptions(select, rows, label) {
    select.replaceChildren(new Option(label, ""));
    for (const option of rows || []) {
        select.add(new Option(option.name, String(option.id)));
    }
}

async function loadCatalogOptions() {
    const options = await BooksAPI.options();
    populateOptions(document.querySelector("#filter-category"), options.categories, "Tất cả danh mục");
    populateOptions(document.querySelector("#filter-language"), options.languages, "Tất cả ngôn ngữ");
    const urlParams = new URLSearchParams(location.search);
    const categorySlug = urlParams.get("category_slug");
    if (categorySlug) {
        const category = (options.categories || []).find((item) => item.slug === categorySlug);
        if (category) document.querySelector("#filter-category").value = String(category.id);
    }
    for (const [selector, key, urlKey = key] of catalogFilters) {
        const field = document.querySelector(selector);
        const value = urlParams.get(urlKey);
        if (field && value) field.value = key === "sort" ? value.replace("_", "-") : value;
    }
}

async function loadBooks(page = 1) {
    const requestId = ++catalogRequestId;
    const grid = document.querySelector("[data-catalog-grid]");
    const empty = document.querySelector("[data-catalog-empty]");
    const error = document.querySelector("[data-filter-error]");
    const params = currentCatalogParams(page);
    const minPrice = Number(params.min_price);
    const maxPrice = Number(params.max_price);
    if (params.min_price && params.max_price && minPrice > maxPrice) {
        error.textContent = "Giá tối thiểu không được lớn hơn giá tối đa.";
        return;
    }
    error.textContent = "";
    syncCatalogUrl(page);
    grid.innerHTML = '<div class="loading-state" role="status">Đang tải sách...</div>';
    try {
        const data = borrowCatalog
            ? await BooksAPI.lendListings(params)
            : await BooksAPI.list(params);
        if (requestId !== catalogRequestId) return;
        if (isLoggedIn()) {
            try {
                await loadFavoriteBookIds();
            } catch (favoriteError) {
                showToast(favoriteError.message);
            }
        }
        if (requestId !== catalogRequestId) return;
        const books = (data.results || []).map((listing) => borrowCatalog ? {
            ...listing.book,
            id: listing.book_id,
            title: listing.title,
            description: listing.description,
            price: listing.rental_fee,
            condition_status: listing.condition_status,
            primary_image: listing.primary_image
                ? {image_url: listing.primary_image}
                : null,
            seller: listing.seller,
            listing_type: "BORROW",
            listing_id: listing.id,
            borrow_terms: listing.borrow_terms,
            deposit_amount: listing.deposit_amount,
        } : listing);
        grid.innerHTML = books.map(renderApiBookCard).join("");
        bindFavoriteButtons(grid);
        if (borrowCatalog) bindBorrowButtons(grid);
        attachImageFallbacks(grid);
        grid.hidden = !books.length;
        empty.hidden = Boolean(books.length);
        document.querySelector("[data-result-count]").textContent = `${data.count} sách`;
        const pagination = document.querySelector("[data-pagination]");
        pagination.replaceChildren();
        if (data.previous) {
            const previous = document.createElement("button");
            previous.className = "button button-outline";
            previous.type = "button";
            previous.textContent = "Trước";
            previous.addEventListener("click", () => loadBooks(Math.max(1, page - 1)));
            pagination.append(previous);
        }
        if (data.next) {
            const next = document.createElement("button");
            next.className = "button button-outline";
            next.type = "button";
            next.textContent = "Sau";
            next.addEventListener("click", () => loadBooks(page + 1));
            pagination.append(next);
        }
    } catch (requestError) {
        if (requestId !== catalogRequestId) return;
        grid.replaceChildren(PassbookCommonComponents.emptyState("Không thể tải sách.", requestError.message));
        empty.hidden = true;
        const retry = document.createElement("button");
        retry.className = "button button-outline";
        retry.type = "button";
        retry.textContent = "Thử lại";
        retry.addEventListener("click", () => loadBooks(page));
        grid.append(retry);
    }
}

document.addEventListener("DOMContentLoaded", async () => {
    if (!document.querySelector("[data-catalog-grid]")) return;
    borrowCatalog = Boolean(document.querySelector("[data-borrow-catalog]"));
    const params = new URLSearchParams(location.search);
    for (const [selector, key, urlKey = key] of catalogFilters) {
        const field = document.querySelector(selector);
        const value = params.get(urlKey) || (urlKey === "q" ? params.get("search") : "");
        if (field) field.value = value || "";
    }
    const savedCondition = params.get("condition_status");
    if (savedCondition) {
        const condition = document.querySelector(`input[name='condition'][value="${CSS.escape(savedCondition)}"]`);
        if (condition) condition.checked = true;
    }
    const page = Math.max(1, Number(params.get("page")) || 1);
    const search = document.querySelector("#catalog-query");
    document.querySelectorAll("input[name='condition']").forEach((field) =>
        field.addEventListener("change", () => void loadBooks(1)),
    );
    for (const selector of [
        "#filter-category", "#filter-language",
        "#filter-year", "#sort-books", "#filter-min-price", "#filter-max-price",
    ]) {
        document.querySelector(selector)?.addEventListener("change", () => void loadBooks(1));
    }
    let debounce;
    for (const selector of [
        "#catalog-query", "#filter-school", "#filter-faculty", "#filter-major", "#filter-subject",
        "#filter-author", "#filter-isbn", "#filter-edition",
    ]) {
        document.querySelector(selector)?.addEventListener("input", () => {
            window.clearTimeout(debounce);
            debounce = window.setTimeout(() => void loadBooks(1), 300);
        });
    }
    const filterPanel = document.querySelector(".filter-panel");
    const filterToggle = document.querySelector("[data-filter-open]");
    const setFiltersOpen = (open) => {
        filterPanel?.classList.toggle("is-open", open);
        filterToggle?.setAttribute("aria-expanded", String(open));
        const indicator = filterToggle?.querySelector("span");
        if (indicator) indicator.textContent = open ? "⌃" : "⌄";
    };
    const closeFilters = (restoreFocus = false) => {
        if (!filterPanel?.classList.contains("is-open")) return;
        setFiltersOpen(false);
        if (restoreFocus) filterToggle?.focus();
    };
    const filterClose = document.querySelector("[data-filter-close]");

    document.querySelector("[data-apply-filters]")?.addEventListener("click", () => {
        window.clearTimeout(debounce);
        void loadBooks(1);
        closeFilters(true);
    });
    document.querySelector("[data-search-submit]")?.addEventListener("click", () => {
        window.clearTimeout(debounce);
        void loadBooks(1);
    });
    search?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            window.clearTimeout(debounce);
            void loadBooks(1);
        }
    });
    document.querySelector("[data-reset-filters]")?.addEventListener("click", () => {
        window.location.assign(catalogPage());
    });
    document.querySelector("[data-reset-empty]")?.addEventListener("click", () => {
        window.location.assign(catalogPage());
    });
    filterToggle?.addEventListener("click", () =>
        setFiltersOpen(!filterPanel?.classList.contains("is-open")),
    );
    filterClose?.addEventListener("click", () => closeFilters(true));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeFilters(true);
    });
    document.addEventListener("click", (event) => {
        if (
            filterPanel?.classList.contains("is-open")
            && !filterPanel.contains(event.target)
            && !filterToggle?.contains(event.target)
        ) {
            closeFilters();
        }
    });
    const catalogOptionsTask = loadCatalogOptions().catch((error) => {
        document.querySelector("[data-filter-error]").textContent =
            `Không thể tải bộ lọc. ${error.message}`;
    });
    const needsCatalogOptions = [
        "category_slug",
        "category_id",
        "language_id",
    ].some((key) => params.has(key));
    try {
        if (needsCatalogOptions) {
            await catalogOptionsTask;
            await loadBooks(page);
        } else {
            await Promise.all([catalogOptionsTask, loadBooks(page)]);
        }
    } catch (error) {
        document.querySelector("[data-filter-error]").textContent =
            `Không thể tải sách. ${error.message}`;
    }
});
