document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-requests-page]");
    if (!page || !PassbookGuards.requireAuth()) return;

    const form = page.querySelector("[data-request-form]");
    const ownList = page.querySelector("[data-own-request-list]");
    const communityList = page.querySelector("[data-community-request-list]");
    const pagination = page.querySelector("[data-request-pagination]");
    const error = page.querySelector("[data-request-error]");
    const requestType = form.elements.request_type;
    const price = form.elements.price;
    const condition = form.elements.condition_preference;
    const expiresAt = form.elements.expires_at;
    const cancelEdit = page.querySelector("[data-request-edit-cancel]");
    const submit = form.querySelector("button[type=submit]");
    const currentUserId = Number(PassbookAuth.getCurrentUser()?.id);
    const typeLabels = {BUY: "Tìm mua", BORROW: "Tìm mượn", SELL_INTENT: "Muốn bán"};
    const statusLabels = {
        OPEN: "Đang mở",
        MATCHED: "Đã có kết quả",
        CANCELLED: "Đã hủy",
        EXPIRED: "Đã hết hạn",
        COMPLETED: "Hoàn tất",
    };
    let currentPage = 1;
    let activeFilter = "all";
    let editingRequestId = null;
    let loadRequestId = 0;

    const node = (tag, className, text) => {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    };

    const priceForType = () => {
        const selling = requestType.value === "SELL_INTENT";
        page.querySelector("[data-request-price-label]").textContent = selling
            ? "Giá mong muốn (VND)"
            : "Ngân sách tối đa (VND)";
        page.querySelector("[data-request-condition-group]").hidden = selling;
    };

    const formatAmount = (amount) => amount === null || amount === undefined
        ? ""
        : `${new Intl.NumberFormat("vi-VN").format(Number(amount))}đ`;

    const toLocalDateTime = (value) => {
        if (!value) return "";
        const date = new Date(value);
        return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
            .toISOString()
            .slice(0, 16);
    };

    const fillEditForm = (request) => {
        editingRequestId = request.id;
        requestType.value = request.request_type;
        form.elements.title_keyword.value = request.title_keyword || "";
        form.elements.description.value = request.description || "";
        price.value = request.request_type === "SELL_INTENT"
            ? request.asking_price || ""
            : request.budget_max || "";
        condition.value = request.condition_preference || "";
        expiresAt.value = toLocalDateTime(request.expires_at);
        priceForType();
        page.querySelector("[data-request-form-title]").textContent = "Chỉnh sửa yêu cầu";
        submit.textContent = "Lưu thay đổi";
        cancelEdit.hidden = false;
        form.scrollIntoView({behavior: "smooth", block: "start"});
        form.elements.title_keyword.focus({preventScroll: true});
    };

    const renderMatches = async (request, container, button) => {
        button.disabled = true;
        button.textContent = "Đang tìm...";
        try {
            const response = await BooksAPI.requestMatches(request.id);
            const matches = Array.isArray(response) ? response : response.results || [];
            const panel = node("div", "request-matches");
            panel.append(node("strong", "", "Kết quả phù hợp"));
            if (!matches.length) {
                panel.append(node("p", "caption", "Chưa tìm thấy tin đăng phù hợp."));
            } else {
                matches.forEach((match) => {
                    const row = node("article", "request-match");
                    row.append(
                        node("strong", "", match.title || "Tin đăng phù hợp"),
                        node("span", "", [
                            match.match_type || "",
                            match.price !== undefined ? formatAmount(match.price) : "",
                        ].filter(Boolean).join(" · ")),
                    );
                    panel.append(row);
                });
            }
            container.querySelector(".request-matches")?.remove();
            container.append(panel);
            button.textContent = "Cập nhật kết quả";
        } catch (requestError) {
            error.textContent = requestError.message;
            button.textContent = "Xem kết quả phù hợp";
        } finally {
            button.disabled = false;
        }
    };

    const buildRequestCard = (request, {own}) => {
        const card = node("article", "request-card");
        card.dataset.requestId = String(request.id);
        const heading = node("div", "request-card__heading");
        heading.append(
            node("span", "request-type-badge", typeLabels[request.request_type] || request.request_type),
            node("span", `request-status request-status--${String(request.status || "").toLowerCase()}`, statusLabels[request.status] || request.status),
        );
        const title = node("h3", "", request.title_keyword || `Đầu sách #${request.book_work_id || request.category_id || "—"}`);
        const description = node("p", "request-card__description", request.description || "Chưa có mô tả.");
        card.append(heading, title, description);
        const facts = node("div", "request-card__facts");
        if (request.request_type === "SELL_INTENT" && request.asking_price) {
            facts.append(node("span", "", `Giá mong muốn ${formatAmount(request.asking_price)}`));
        } else if (request.budget_max) {
            facts.append(node("span", "", `Ngân sách đến ${formatAmount(request.budget_max)}`));
        }
        if (request.condition_preference) {
            facts.append(node("span", "", `Tình trạng: ${request.condition_preference}`));
        }
        if (request.expires_at) {
            facts.append(node("span", "", `Hết hạn ${new Date(request.expires_at).toLocaleString("vi-VN")}`));
        }
        if (request.created_at) {
            facts.append(node("span", "", new Date(request.created_at).toLocaleDateString("vi-VN")));
        }
        if (facts.childElementCount) card.append(facts);

        const actions = node("div", "request-card__actions");
        if (own) {
            const edit = node("button", "button button-outline", "Sửa");
            edit.type = "button";
            edit.addEventListener("click", () => fillEditForm(request));
            const matches = node("button", "button button-outline", "Xem kết quả phù hợp");
            matches.type = "button";
            matches.addEventListener("click", () => {
                void renderMatches(request, card, matches);
            });
            const cancel = node("button", "button button-outline", "Hủy yêu cầu");
            cancel.type = "button";
            cancel.addEventListener("click", async () => {
                if (!window.confirm("Hủy yêu cầu này?")) return;
                cancel.disabled = true;
                try {
                    await BooksAPI.deleteRequest(request.id);
                    await load();
                    showToast("Đã hủy yêu cầu.");
                } catch (requestError) {
                    error.textContent = requestError.message;
                    cancel.disabled = false;
                }
            });
            actions.append(edit, matches, cancel);
        } else {
            const interested = node("button", "button button-primary", "Tôi quan tâm");
            interested.type = "button";
            interested.addEventListener("click", async () => {
                interested.disabled = true;
                try {
                    await BooksAPI.requestInterests(request.id, {});
                    interested.textContent = "Đã gửi quan tâm";
                    interested.setAttribute("aria-pressed", "true");
                    showToast("Đã gửi lời quan tâm cho người đăng.");
                } catch (requestError) {
                    error.textContent = requestError.message;
                    interested.disabled = false;
                }
            });
            actions.append(interested);
        }
        card.append(actions);
        return card;
    };

    const renderRows = (requests) => {
        const mine = requests.filter((request) => Number(request.user_id) === currentUserId);
        const community = requests.filter((request) => Number(request.user_id) !== currentUserId)
            .filter((request) => activeFilter === "all" || request.request_type === activeFilter);
        ownList.replaceChildren(...(mine.length
            ? mine.map((request) => buildRequestCard(request, {own: true}))
            : [PassbookCommonComponents.emptyStateElement("Bạn chưa đăng yêu cầu nào.")]));
        communityList.replaceChildren(...(community.length
            ? community.map((request) => buildRequestCard(request, {own: false}))
            : [PassbookCommonComponents.emptyStateElement(
                activeFilter === "all" ? "Chưa có yêu cầu từ cộng đồng." : "Chưa có yêu cầu thuộc loại này.",
            )]));
    };

    const load = async () => {
        const requestId = ++loadRequestId;
        error.textContent = "";
        ownList.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải yêu cầu của bạn..."));
        communityList.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải yêu cầu cộng đồng..."));
        pagination.replaceChildren();
        try {
            const response = await BooksAPI.requests({page: currentPage, page_size: 20});
            if (requestId !== loadRequestId) return;
            renderRows(response.results || []);
            const controls = PassbookCommonComponents.pagination({
                previous: response.previous,
                next: response.next,
                onPrevious: () => { currentPage = Math.max(1, currentPage - 1); void load(); },
                onNext: () => { currentPage += 1; void load(); },
            });
            if (controls) pagination.append(controls);
        } catch (requestError) {
            if (requestId !== loadRequestId) return;
            ownList.replaceChildren(PassbookCommonComponents.emptyStateElement("Không thể tải yêu cầu."));
            communityList.replaceChildren();
            error.textContent = requestError.message;
        }
    };

    const resetForm = () => {
        editingRequestId = null;
        form.reset();
        priceForType();
        page.querySelector("[data-request-form-title]").textContent = "Tạo yêu cầu mới";
        submit.textContent = "Đăng yêu cầu";
        cancelEdit.hidden = true;
        error.textContent = "";
    };

    requestType.addEventListener("change", priceForType);
    page.querySelectorAll("[data-request-filter]").forEach((button) => button.addEventListener("click", () => {
        activeFilter = button.dataset.requestFilter;
        page.querySelectorAll("[data-request-filter]").forEach((filter) => {
            const selected = filter === button;
            filter.className = `button${selected ? " is-active" : " button-outline"}`;
            filter.setAttribute("aria-pressed", String(selected));
        });
        void load();
    }));
    cancelEdit.addEventListener("click", resetForm);
    page.querySelector("[data-request-refresh]").addEventListener("click", load);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const type = requestType.value;
        const payload = {
            request_type: type,
            title_keyword: form.elements.title_keyword.value.trim(),
            description: form.elements.description.value.trim(),
            budget_max: null,
            asking_price: null,
            condition_preference: type === "SELL_INTENT"
                ? ""
                : condition.value,
        };
        const amount = price.value.trim();
        if (amount) payload[type === "SELL_INTENT" ? "asking_price" : "budget_max"] = amount;
        if (expiresAt.value) {
            const expiry = new Date(expiresAt.value);
            if (expiry <= new Date()) {
                error.textContent = "Ngày hết hạn phải ở trong tương lai.";
                expiresAt.focus();
                return;
            }
            payload.expires_at = expiry.toISOString();
        }
        submit.disabled = true;
        error.textContent = "";
        const updating = Boolean(editingRequestId);
        try {
            if (editingRequestId) await BooksAPI.updateRequest(editingRequestId, payload);
            else await BooksAPI.createRequest(payload);
            resetForm();
            currentPage = 1;
            await load();
            showToast(updating ? "Đã cập nhật yêu cầu." : "Đã đăng yêu cầu.");
        } catch (requestError) {
            error.textContent = requestError.message;
        } finally {
            submit.disabled = false;
        }
    });

    priceForType();
    void load();
});
