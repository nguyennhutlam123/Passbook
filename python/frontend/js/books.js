const conditionLabels = {new: "Mới", like_new: "Như mới", good: "Tốt", used: "Đã sử dụng"};
const placeholderBookImage = "https://placehold.co/640x480/e2e8f0/475569?text=PASSBOOK";

function renderApiBookCard(book) {
    return renderBookCard(book);
}

function queryBooks(page = 1) {
    const params = new URLSearchParams({page, page_size: 10});
    const search = document.querySelector("#catalog-query")?.value.trim();
    const subject = document.querySelector("#filter-subject")?.value;
    const category = document.querySelector("#filter-category")?.value;
    const location = document.querySelector("#filter-location")?.value;
    const university = document.querySelector("#filter-school")?.value;
    const condition = document.querySelector("input[name='condition']:checked")?.value;
    const maxPrice = document.querySelector("#filter-price")?.value;
    const minPrice = document.querySelector("#filter-min-price")?.value;
    const sort = document.querySelector("#sort-books")?.value;
    if (search) params.set("search", search);
    if (subject) params.set("subject_id", subject);
    if (category) params.set("category_id", category);
    if (location) params.set("pickup_location_id", location);
    if (university) params.set("university_id", university);
    if (condition) params.set("condition_status", condition);
    if (maxPrice) params.set("max_price", maxPrice);
    if (minPrice) params.set("min_price", minPrice);
    if (sort) params.set("sort", sort);
    return api.get(`/books/?${params}`);
}

async function loadBooks(page = 1) {
    const grid = document.querySelector("[data-catalog-grid]");
    const empty = document.querySelector("[data-catalog-empty]");
    grid.innerHTML = '<div class="loading-state">Đang tải giáo trình...</div>';
    try {
        const [data] = await Promise.all([queryBooks(page), loadFavoriteBookIds()]);
        grid.innerHTML = data.results.map(renderApiBookCard).join("");
        bindFavoriteButtons(grid);
        attachImageFallbacks(grid);
        grid.hidden = !data.results.length;
        empty.hidden = data.results.length > 0;
        document.querySelector("[data-result-count]").textContent = `${data.count} giáo trình`;
        document.querySelector("[data-pagination]").innerHTML = [data.previous ? `<button class="button button-outline" data-page="${page - 1}">Trước</button>` : "", data.next ? `<button class="button button-outline" data-page="${page + 1}">Sau</button>` : ""].join("");
        document.querySelectorAll("[data-page]").forEach((button) => button.addEventListener("click", () => loadBooks(Number(button.dataset.page))));
    } catch (error) {
        grid.innerHTML = `<div class="empty-state"><strong>${error.message}</strong></div>`;
        empty.hidden = true;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (!document.querySelector("[data-catalog-grid]")) return;
    const params = new URLSearchParams(location.search);
    document.querySelector("#catalog-query").value = params.get("q") || "";
    const reload = () => loadBooks(1);
    document.querySelectorAll("#filter-school, #filter-subject, #filter-category, #filter-location, #sort-books, input[name='condition']").forEach((el) => el.addEventListener("change", reload));
    document.querySelector("[data-search-submit]")?.addEventListener("click", reload);
    document.querySelector("#catalog-query")?.addEventListener("keydown", (event) => { if (event.key === "Enter") reload(); });
    document.querySelector("#filter-price")?.addEventListener("input", (event) => {
        document.querySelector("#price-output").textContent = formatPrice(Number(event.target.value));
        reload();
    });
    document.querySelector("#filter-min-price")?.addEventListener("change", reload);
    document.querySelector("[data-reset-filters]")?.addEventListener("click", () => { location.href = "books.html"; });
    document.querySelector("[data-reset-empty]")?.addEventListener("click", () => { location.href = "books.html"; });
    document.querySelector("[data-filter-open]")?.addEventListener("click", () => document.querySelector(".filter-panel")?.classList.add("is-open"));
    document.querySelector("[data-filter-close]")?.addEventListener("click", () => document.querySelector(".filter-panel")?.classList.remove("is-open"));
    loadBooks(1);
});
