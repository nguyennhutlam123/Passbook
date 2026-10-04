const catalogFilters = [
    ["#catalog-query", "search", "q"],
    ["#filter-listing-type", "listing_type"],
    ["#filter-school", "university_id"],
    ["#filter-faculty", "faculty_id"],
    ["#filter-major", "major_id"],
    ["#filter-subject", "subject_id"],
    ["#filter-subject-code", "subject_code"],
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

function renderApiBookCard(book) {
    return renderBookCard(book);
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
    history.replaceState(null, "", `${location.pathname}${query ? `?${query}` : ""}`);
}

function populateOptions(select, rows, label) {
    const selected = select.value;
    select.replaceChildren(new Option(label, ""));
    for (const option of rows || []) {
        select.add(new Option(option.name, String(option.id)));
    }
    if (selected && Array.from(select.options).some((option) => option.value === selected)) {
        select.value = selected;
    }
}

async function loadCatalogOptions() {
    const options = await BooksAPI.options();
    const school = document.querySelector("#filter-school");
    const faculty = document.querySelector("#filter-faculty");
    const major = document.querySelector("#filter-major");
    populateOptions(school, options.universities, "Tất cả trường");
    populateOptions(faculty, options.faculties, "Tất cả khoa");
    populateOptions(major, options.majors, "Tất cả ngành");
    populateOptions(document.querySelector("#filter-subject"), options.subjects, "Tất cả môn học");
    populateOptions(document.querySelector("#filter-category"), options.categories, "Tất cả danh mục");
    populateOptions(document.querySelector("#filter-language"), options.languages, "Tất cả ngôn ngữ");
    const urlParams = new URLSearchParams(location.search);
    for (const [selector, key, urlKey = key] of catalogFilters) {
        const field = document.querySelector(selector);
        const value = urlParams.get(urlKey);
        if (field && value) field.value = key === "sort" ? value.replace("_", "-") : value;
    }

    const applyParentFilters = () => {
        const universityId = school.value;
        const facultyId = faculty.value;
        populateOptions(
            faculty,
            options.faculties.filter((item) => !universityId || String(item.university_id) === universityId),
            "Tất cả khoa",
        );
        if (facultyId && Array.from(faculty.options).some((item) => item.value === facultyId)) {
            faculty.value = facultyId;
        }
        populateOptions(
            major,
            options.majors.filter((item) => !faculty.value || String(item.faculty_id) === faculty.value),
            "Tất cả ngành",
        );
    };
    faculty.disabled = false;
    major.disabled = false;
    school.addEventListener("change", () => {
        faculty.value = "";
        major.value = "";
        applyParentFilters();
        void loadBooks(1);
    });
    faculty.addEventListener("change", () => {
        major.value = "";
        applyParentFilters();
        void loadBooks(1);
    });
    applyParentFilters();
}

function normalizeLendListing(listing) {
    return {
        id: listing.book_id,
        listing_id: listing.id,
        listing_type: "BORROW",
        title: listing.title,
        price: listing.rental_fee,
        status: "available",
        condition_status: listing.condition_status,
        condition_label: listing.condition_label,
        edition: listing.edition,
        publication_year: listing.publication_year,
        primary_image: listing.primary_image
            ? {image_url: listing.primary_image}
            : null,
        subject: listing.subject,
        category: listing.category,
        seller: listing.seller,
        buying_intent_count: listing.buying_intent_count,
        selling_intent_count: listing.selling_intent_count,
    };
}

async function loadBooks(page = 1) {
    const requestId = ++catalogRequestId;
    const grid = document.querySelector("[data-catalog-grid]");
    const empty = document.querySelector("[data-catalog-empty]");
    const error = document.querySelector("[data-filter-error]");
    const params = currentCatalogParams(page);
    const listingType = params.listing_type || "SALE";
    delete params.listing_type;
    const minPrice = Number(params.min_price);
    const maxPrice = Number(params.max_price);
    if (params.min_price && params.max_price && minPrice > maxPrice) {
        error.textContent = "Giá tối thiểu không được lớn hơn giá tối đa.";
        return;
    }
    error.textContent = "";
    syncCatalogUrl(page);
    grid.innerHTML = '<div class="loading-state" role="status">Đang tải giáo trình...</div>';
    try {
        const data = listingType === "BORROW"
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
        const books = listingType === "BORROW"
            ? (data.results || []).map(normalizeLendListing)
            : data.results || [];
        grid.innerHTML = books.map(renderApiBookCard).join("");
        bindFavoriteButtons(grid);
        attachImageFallbacks(grid);
        grid.hidden = !books.length;
        empty.hidden = Boolean(books.length);
        document.querySelector("[data-result-count]").textContent = `${data.count} giáo trình`;
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
        grid.replaceChildren(PassbookCommonComponents.emptyState("Không thể tải giáo trình.", requestError.message));
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
        "#filter-listing-type", "#filter-subject", "#filter-major", "#filter-category", "#filter-language",
        "#filter-year", "#sort-books", "#filter-min-price", "#filter-max-price",
    ]) {
        document.querySelector(selector)?.addEventListener("change", () => void loadBooks(1));
    }
    let debounce;
    for (const selector of [
        "#catalog-query", "#filter-subject-code", "#filter-author", "#filter-isbn", "#filter-edition",
    ]) {
        document.querySelector(selector)?.addEventListener("input", () => {
            window.clearTimeout(debounce);
            debounce = window.setTimeout(() => void loadBooks(1), 300);
        });
    }
    document.querySelector("[data-search-submit]")?.addEventListener("click", () => void loadBooks(1));
    search?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            window.clearTimeout(debounce);
            void loadBooks(1);
        }
    });
    document.querySelector("[data-reset-filters]")?.addEventListener("click", () => {
        window.location.assign("books.html");
    });
    document.querySelector("[data-reset-empty]")?.addEventListener("click", () => {
        window.location.assign("books.html");
    });
    document.querySelector("[data-filter-open]")?.addEventListener("click", () =>
        document.querySelector(".filter-panel")?.classList.add("is-open"),
    );
    document.querySelector("[data-filter-close]")?.addEventListener("click", () =>
        document.querySelector(".filter-panel")?.classList.remove("is-open"),
    );
    try {
        await loadCatalogOptions();
        await loadBooks(page);
    } catch (error) {
        document.querySelector("[data-filter-error]").textContent =
            `Không thể tải bộ lọc. ${error.message}`;
        await loadBooks(page);
    }
});
