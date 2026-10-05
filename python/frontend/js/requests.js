document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-requests-page]");
    if (!page || !PassbookGuards.requireAuth()) return;

    const form = page.querySelector("[data-request-form]");
    const ownList = page.querySelector("[data-own-request-list]");
    const communityList = page.querySelector("[data-community-request-list]");
    const pagination = page.querySelector("[data-request-pagination]");
    const ownPagination = page.querySelector("[data-own-request-pagination]");
    const error = page.querySelector("[data-request-error]");
    const requestType = form.elements.request_type;
    const price = form.elements.price;
    const condition = form.elements.condition_preference;
    const expiresAt = form.elements.expires_at;
    const plannedAt = form.elements.planned_at;
    const cancelEdit = page.querySelector("[data-request-edit-cancel]");
    const submit = form.querySelector("button[type=submit]");
    const typeLabels = {BUY: "Tìm mua", BORROW: "Tìm mượn", SELL_INTENT: "Muốn bán"};
    const statusLabels = {
        OPEN: "Đang mở",
        MATCHED: "Đã có kết quả",
        CANCELLED: "Đã hủy",
        EXPIRED: "Đã hết hạn",
        COMPLETED: "Hoàn tất",
    };
    let communityPage = 1;
    let ownPage = 1;
    let activeFilter = "all";
    let editingRequestId = null;

    const node = (tag, className, text) => {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    };

    const priceForType = () => {
        const selling = requestType.value === "SELL_INTENT";
        const borrowing = requestType.value === "BORROW";
        page.querySelector("[data-request-price-label]").textContent = selling
            ? "Giá mong muốn (VND)"
            : borrowing ? "Ngân sách thuê tối đa (VND)" : "Ngân sách tối đa (VND)";
        page.querySelector("[data-request-condition-group]").hidden = selling;
        page.querySelector("[data-request-planned-label]").textContent = selling
            ? "Ngày dự định bán (không bắt buộc)"
            : borrowing
                ? "Ngày dự định bắt đầu mượn (không bắt buộc)"
                : "Ngày dự định mua (không bắt buộc)";
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
        plannedAt.value = toLocalDateTime(request.planned_at);
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
        if (request.planned_at) {
            const action = request.request_type === "SELL_INTENT"
                ? "bán"
                : request.request_type === "BORROW" ? "mượn" : "mua";
            facts.append(node(
                "span",
                "",
                `Dự định ${action}: ${new Date(request.planned_at).toLocaleString("vi-VN")}`,
            ));
        }
        if (request.expires_at) {
            facts.append(node("span", "", `Hết hạn ${new Date(request.expires_at).toLocaleString("vi-VN")}`));
        }
        if (request.same_intent_count !== undefined) {
            const action = request.request_type === "SELL_INTENT"
                ? "bán"
                : request.request_type === "BORROW" ? "mượn" : "mua";
            facts.append(node(
                "span",
                "request-card__intent-count",
                `${Number(request.same_intent_count)} người cùng dự định ${action} sách này`,
            ));
        }
        if (request.created_at) {
            facts.append(node("span", "", new Date(request.created_at).toLocaleDateString("vi-VN")));
        }
        if (facts.childElementCount) card.append(facts);

        const actions = node("div", "request-card__actions");
        if (own) {
            if (request.status === "OPEN") {
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
                        ownPage = 1;
                        await load();
                        showToast("Đã hủy yêu cầu.");
                    } catch (requestError) {
                        error.textContent = requestError.message;
                        cancel.disabled = false;
                    }
                });
                actions.append(edit, matches, cancel);
            }
        } else {
            const interested = node(
                "button",
                "button button-primary",
                request.request_type === "BUY"
                    ? "Tôi có sách này"
                    : request.request_type === "BORROW"
                        ? "Tôi có thể cho mượn"
                        : "Tôi muốn mua sách này",
            );
            interested.type = "button";
            const replyForm = node("form", "request-response-form");
            replyForm.hidden = true;
            const noteLabel = node(
                "label",
                "form-label",
                request.request_type === "SELL_INTENT"
                    ? "Lời nhắn và đề xuất mua"
                    : "Giới thiệu sách bạn có",
            );
            const note = node("textarea", "form-control");
            note.maxLength = 1500;
            note.required = true;
            note.rows = 3;
            note.placeholder = "Nêu tình trạng, phiên bản, giá hoặc thời gian có thể giao...";
            const send = node("button", "button button-outline", "Gửi lời nhắn riêng");
            send.type = "submit";
            replyForm.append(noteLabel, note, send);
            interested.setAttribute("aria-expanded", "false");
            interested.addEventListener("click", () => {
                replyForm.hidden = !replyForm.hidden;
                interested.setAttribute("aria-expanded", String(!replyForm.hidden));
                if (!replyForm.hidden) note.focus();
            });
            replyForm.addEventListener("submit", async (event) => {
                event.preventDefault();
                if (!replyForm.reportValidity()) return;
                send.disabled = true;
                try {
                    const response = await BooksAPI.requestInterests(request.id, {
                        note: note.value.trim(),
                    });
                    interested.textContent = "Đã liên hệ riêng";
                    interested.disabled = true;
                    replyForm.hidden = true;
                    await openConversationModal(response.conversation_id);
                } catch (requestError) {
                    error.textContent = requestError.message;
                    send.disabled = false;
                }
            });
            actions.append(interested, replyForm);
        }
        card.append(actions);
        return card;
    };

    const renderOwnRequests = (mine) => {
        ownList.replaceChildren(...(mine.length
            ? mine.map((request) => buildRequestCard(request, {own: true}))
            : [PassbookCommonComponents.emptyStateElement("Bạn chưa đăng yêu cầu nào.")]));
    };

    const renderCommunityRequests = (requests) => {
        communityList.replaceChildren(...(requests.length
            ? requests.map((request) => buildRequestCard(request, {own: false}))
            : [PassbookCommonComponents.emptyStateElement(
                activeFilter === "all" ? "Chưa có yêu cầu từ cộng đồng." : "Chưa có yêu cầu thuộc loại này.",
            )]));
    };

    const load = async () => {
        error.textContent = "";
        ownList.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải yêu cầu của bạn..."));
        communityList.replaceChildren(PassbookCommonComponents.loadingStateElement("Đang tải yêu cầu cộng đồng..."));
        pagination.replaceChildren();
        ownPagination.replaceChildren();
        try {
            const [ownResponse, communityResponse] = await Promise.all([
                BooksAPI.requests({scope: "mine", page: ownPage, page_size: 10}),
                BooksAPI.requests({
                    page: communityPage,
                    page_size: 20,
                    ...(activeFilter === "all" ? {} : {request_type: activeFilter}),
                }),
            ]);
            renderOwnRequests(ownResponse.results || []);
            renderCommunityRequests(communityResponse.results || []);
            const ownControls = PassbookCommonComponents.pagination({
                previous: ownResponse.previous,
                next: ownResponse.next,
                onPrevious: () => { ownPage = Math.max(1, ownPage - 1); void load(); },
                onNext: () => { ownPage += 1; void load(); },
            });
            if (ownControls) ownPagination.append(ownControls);
            const communityControls = PassbookCommonComponents.pagination({
                previous: communityResponse.previous,
                next: communityResponse.next,
                onPrevious: () => { communityPage = Math.max(1, communityPage - 1); void load(); },
                onNext: () => { communityPage += 1; void load(); },
            });
            if (communityControls) pagination.append(communityControls);
        } catch (requestError) {
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
        communityPage = 1;
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
        const plannedDate = plannedAt.value ? new Date(plannedAt.value) : null;
        const expiryDate = expiresAt.value ? new Date(expiresAt.value) : null;
        if (plannedDate && plannedDate <= new Date()) {
            error.textContent = "Ngày dự định phải ở trong tương lai.";
            plannedAt.focus();
            return;
        }
        if (expiryDate && expiryDate <= new Date()) {
            error.textContent = "Ngày hết hạn phải ở trong tương lai.";
            expiresAt.focus();
            return;
        }
        if (plannedDate && expiryDate && expiryDate <= plannedDate) {
            error.textContent = "Ngày hết hạn cần sau ngày dự định.";
            expiresAt.focus();
            return;
        }
        payload.planned_at = plannedDate ? plannedDate.toISOString() : null;
        payload.expires_at = expiryDate ? expiryDate.toISOString() : null;
        submit.disabled = true;
        error.textContent = "";
        const updating = Boolean(editingRequestId);
        try {
            if (editingRequestId) await BooksAPI.updateRequest(editingRequestId, payload);
            else await BooksAPI.createRequest(payload);
            resetForm();
            ownPage = 1;
            communityPage = 1;
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
