document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-requests-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const form = page.querySelector("[data-request-form]");
    const list = page.querySelector("[data-request-list]");
    const pagination = page.querySelector("[data-request-pagination]");
    const error = page.querySelector("[data-request-error]");
    let currentPage = 1;
    let editingRequestId = null;

    const requestCard = (request) => {
        const card = document.createElement("article");
        card.className = "report-item";
        const title = document.createElement("strong");
        title.textContent = `${request.request_type} · ${request.title_keyword || `Đầu sách #${request.book_work_id || request.category_id}`}`;
        const summary = document.createElement("p");
        summary.textContent = `${request.description || ""} · ${request.status}`;
        card.append(title, summary);
        const owns = Number(request.user_id) === Number(PassbookAuth.getCurrentUser()?.id);
        const action = (label, callback) => {
            const button = document.createElement("button");
            button.className = "button button-outline";
            button.type = "button";
            button.textContent = label;
            button.addEventListener("click", callback);
            card.append(button);
        };
        if (owns) {
            action("Sửa", () => {
                editingRequestId = request.id;
                form.elements.request_type.value = request.request_type;
                form.elements.title_keyword.value = request.title_keyword || "";
                form.elements.description.value = request.description || "";
                form.elements.price.value = request.request_type === "SELL_INTENT"
                    ? request.asking_price || ""
                    : request.budget_max || "";
                form.querySelector("button[type=submit]").textContent = "Lưu thay đổi";
                page.querySelector("[data-request-edit-cancel]").hidden = false;
                form.scrollIntoView({behavior: "smooth", block: "start"});
            });
            action("Xem kết quả phù hợp", async (event) => {
                const button = event.currentTarget;
                button.disabled = true;
                try {
                    const matches = await BooksAPI.requestMatches(request.id);
                    const rows = Array.isArray(matches) ? matches : matches.results || [];
                    const resultText = rows.map((match) =>
                        `${match.title} · ${match.price} · ${match.match_type}`,
                    ).join("\n") || "Chưa tìm thấy kết quả phù hợp.";
                    window.alert(resultText);
                } catch (requestError) {
                    error.textContent = requestError.message;
                } finally {
                    button.disabled = false;
                }
            });
            action("Hủy yêu cầu", async (event) => {
                if (!window.confirm("Hủy yêu cầu này?")) return;
                const button = event.currentTarget;
                button.disabled = true;
                try {
                    await BooksAPI.deleteRequest(request.id);
                    await load();
                } catch (requestError) {
                    error.textContent = requestError.message;
                } finally {
                    button.disabled = false;
                }
            });
        } else {
            let interested = false;
            action("Tôi quan tâm", async (event) => {
                const button = event.currentTarget;
                button.disabled = true;
                try {
                    if (interested) {
                        await BooksAPI.removeRequestInterest(request.id);
                        interested = false;
                        button.textContent = "Tôi quan tâm";
                    } else {
                        await BooksAPI.requestInterests(request.id, {});
                        interested = true;
                        button.textContent = "Rút quan tâm";
                    }
                } catch (requestError) {
                    error.textContent = requestError.message;
                    button.disabled = false;
                }
            });
        }
        return card;
    };

    const load = async () => {
        list.replaceChildren(PassbookCommonComponents.loadingState());
        pagination.replaceChildren();
        try {
            const data = await BooksAPI.requests({page: currentPage, page_size: 10});
            const rows = data.results || [];
            list.replaceChildren(...(rows.length
                ? rows.map(requestCard)
                : [PassbookCommonComponents.emptyState("Chưa có yêu cầu đang mở.")]));
            pagination.replaceChildren(PassbookCommonComponents.pagination({
                previous: data.previous,
                next: data.next,
                onPrevious: () => { currentPage = Math.max(1, currentPage - 1); void load(); },
                onNext: () => { currentPage += 1; void load(); },
            }));
        } catch (requestError) {
            list.replaceChildren(PassbookCommonComponents.emptyState("Không thể tải yêu cầu."));
            error.textContent = requestError.message;
        }
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const data = new FormData(form);
        const type = data.get("request_type").toString();
        const amount = data.get("price").toString().trim();
        const payload = {
            request_type: type,
            title_keyword: data.get("title_keyword").toString().trim(),
            description: data.get("description").toString().trim(),
        };
        if (amount) payload[type === "SELL_INTENT" ? "asking_price" : "budget_max"] = amount;
        const submit = form.querySelector("button[type=submit]");
        submit.disabled = true;
        error.textContent = "";
        try {
            if (editingRequestId) await BooksAPI.updateRequest(editingRequestId, payload);
            else await BooksAPI.createRequest(payload);
            form.reset();
            editingRequestId = null;
            submit.textContent = "Đăng yêu cầu";
            page.querySelector("[data-request-edit-cancel]").hidden = true;
            currentPage = 1;
            await load();
        } catch (requestError) {
            error.textContent = requestError.message;
        } finally {
            submit.disabled = false;
        }
    });
    page.querySelector("[data-request-edit-cancel]").addEventListener("click", () => {
        editingRequestId = null;
        form.reset();
        form.querySelector("button[type=submit]").textContent = "Đăng yêu cầu";
        page.querySelector("[data-request-edit-cancel]").hidden = true;
        error.textContent = "";
    });
    page.querySelector("[data-request-refresh]").addEventListener("click", load);
    void load();
});
