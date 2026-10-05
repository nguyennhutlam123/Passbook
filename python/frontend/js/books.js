const catalogFilters = [
    ["#catalog-query", "search"],
    ["#filter-school", "university"],
    ["#filter-faculty", "faculty"],
    ["#filter-major", "major"],
    ["#filter-subject", "subject"],
    ["#filter-author", "author"],
    ["#filter-isbn", "isbn"],
    ["#filter-edition", "edition"],
    ["#filter-year", "publication_year"],
    ["#filter-language", "language"],
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

function currentCatalogParams(page) {
    const params = {page, page_size: 10};
    for (const [selector, key] of catalogFilters) {
        const value = document.querySelector(selector)?.value.trim();
        if (value) params[key] = key === "sort" ? value.replace("-", "_") : value;
    }
    const urlParams = new URLSearchParams(location.search);
    if (!params.category_id) {
        const categoryId = urlParams.get("category_id");
        const categorySlug = urlParams.get("category_slug");
        if (categoryId) params.category_id = categoryId;
        else if (categorySlug) params.category_slug = categorySlug;
    }
    if (!params.language && urlParams.has("language_id")) {
        params.language_id = urlParams.get("language_id");
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
    const currentUrlParams = new URLSearchParams(location.search);
    if (!params.has("category_id")) {
        const categoryId = currentUrlParams.get("category_id");
        const categorySlug = currentUrlParams.get("category_slug");
        if (categoryId) params.set("category_id", categoryId);
        else if (categorySlug) params.set("category_slug", categorySlug);
    }
    if (!params.has("language") && currentUrlParams.has("language_id")) {
        params.set("language_id", currentUrlParams.get("language_id"));
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
    const languageField = document.querySelector("#filter-language");
    const legacyLanguageId = urlParams.get("language_id");
    if (languageField && !urlParams.has("language") && legacyLanguageId) {
        const language = (options.languages || []).find(
            (option) => String(option.id) === legacyLanguageId,
        );
        if (language) languageField.value = language.name;
    }
}

async function loadBooks(page = 1) {
    const requestId = ++catalogRequestId;
    const grid = document.querySelector("[data-catalog-grid]");
    const empty = document.querySelector("[data-catalog-empty]");
    const error = document.querySelector("[data-filter-error]");
    const catalogLayout = document.querySelector(".catalog-layout");
    const params = currentCatalogParams(page);
    const minPrice = Number(params.min_price);
    const maxPrice = Number(params.max_price);
    if (params.min_price && params.max_price && minPrice > maxPrice) {
        error.textContent = "Giá tối thiểu không được lớn hơn giá tối đa.";
        return;
    }
    error.textContent = "";
    catalogLayout?.classList.remove("catalog-layout--empty");
    empty.hidden = true;
    grid.hidden = false;
    syncCatalogUrl(page);
    grid.innerHTML = '<div class="loading-state" role="status">Đang tải sách...</div>';
    const favoriteLoad = isLoggedIn() && !borrowCatalog
        ? loadFavoriteBookIds().catch((favoriteError) => {
            showToast(favoriteError.message);
        })
        : Promise.resolve();
    try {
        const data = borrowCatalog
            ? await BooksAPI.lendListings(params)
            : await BooksAPI.list(params);
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
            average_rating: listing.average_rating,
            review_count: listing.review_count,
        } : listing);
        grid.innerHTML = books.map(renderApiBookCard).join("");
        bindFavoriteButtons(grid);
        if (isLoggedIn() && !borrowCatalog) {
            const favoriteButtons = [...grid.querySelectorAll("[data-favorite]")];
            favoriteButtons.forEach((button) => {
                button.disabled = true;
            });
            void favoriteLoad.then(() => {
                if (requestId !== catalogRequestId) return;
                syncFavoriteButtons(grid);
            });
        }
        if (!borrowCatalog) bindSaleButtons(grid);
        if (borrowCatalog) bindBorrowButtons(grid);
        attachImageFallbacks(grid);
        grid.hidden = !books.length;
        empty.hidden = Boolean(books.length);
        catalogLayout?.classList.toggle(
            "catalog-layout--empty",
            borrowCatalog && books.length === 0,
        );
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
        catalogLayout?.classList.remove("catalog-layout--empty");
        grid.replaceChildren(PassbookCommonComponents.emptyStateElement(
            "Không thể tải sách.",
            requestError.message,
        ));
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
        "#filter-author", "#filter-isbn", "#filter-edition", "#filter-language",
    ]) {
        document.querySelector(selector)?.addEventListener("input", () => {
            window.clearTimeout(debounce);
            debounce = window.setTimeout(() => void loadBooks(1), 300);
        });
    }
    document.querySelector("[data-apply-filters]")?.addEventListener("click", () => {
        window.clearTimeout(debounce);
        void loadBooks(1);
    });
    document.querySelector("[data-search-submit]")?.addEventListener("click", () => void loadBooks(1));
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
    const filterPanel = document.querySelector(".filter-panel");
    const filterToggle = document.querySelector("[data-filter-open]");
    const setFiltersOpen = (open) => {
        filterPanel?.classList.toggle("is-open", open);
        filterToggle?.setAttribute("aria-expanded", String(open));
        if (filterToggle) filterToggle.querySelector("span").textContent = open ? "⌃" : "⌄";
    };
    filterToggle?.addEventListener("click", () =>
        setFiltersOpen(!filterPanel?.classList.contains("is-open")),
    );
    document.querySelector("[data-filter-close]")?.addEventListener("click", () =>
        setFiltersOpen(false),
    );
    const optionsRequest = loadCatalogOptions();
    const booksRequest = loadBooks(page);
    try {
        await Promise.all([optionsRequest, booksRequest]);
    } catch (error) {
        document.querySelector("[data-filter-error]").textContent =
            `Không thể tải bộ lọc. ${error.message}`;
    }
});
