document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-admin-users]");
    if (!page || !PassbookGuards.requireRole("ADMIN")) return;
    const lookup = page.querySelector("[data-user-lookup]");
    const userSearch = page.querySelector("[data-user-search]");
    const userResults = page.querySelector("[data-admin-user-results]");
    const statusForm = page.querySelector("[data-user-status-form]");
    const violationForm = page.querySelector("[data-violation-form]");
    const violations = page.querySelector("[data-user-violations]");
    const error = page.querySelector("[data-user-admin-error]");
    let userId = "";
    let userPage = 1;

    const loadUsers = async () => {
        error.textContent = "";
        const params = new FormData(userSearch);
        userResults.innerHTML = PassbookCommonComponents.loadingState("Đang tải tài khoản...");
        try {
            const data = await AdminAPI.users({
                search: params.get("search").toString().trim(),
                status: params.get("status").toString(),
                role: params.get("role").toString(),
                page: userPage,
                page_size: 20,
            });
            const cards = (data.results || []).map((user) => {
                const card = document.createElement("article");
                card.className = "report-item";
                const summary = document.createElement("strong");
                summary.textContent = `${user.full_name} · ${user.email}`;
                const details = document.createElement("p");
                details.textContent = [
                    user.phone || "Chưa có số điện thoại",
                    user.university_name || "Chưa khai báo trường",
                    user.role,
                    user.status,
                ].join(" · ");
                const select = document.createElement("button");
                select.className = "button button-outline";
                select.type = "button";
                select.textContent = "Quản lý tài khoản";
                select.addEventListener("click", async () => {
                    userId = String(user.id);
                    lookup.elements.user_id.value = userId;
                    statusForm.elements.status.value = user.status;
                    await loadViolations();
                    statusForm.scrollIntoView({behavior: "smooth", block: "center"});
                });
                card.append(summary, details, select);
                return card;
            });
            if (!cards.length) {
                const empty = document.createElement("div");
                empty.className = "empty-state";
                const label = document.createElement("strong");
                label.textContent = "Không tìm thấy tài khoản.";
                empty.append(label);
                cards.push(empty);
            }
            const controls = PassbookCommonComponents.pagination({
                previous: data.previous,
                next: data.next,
                onPrevious: () => {
                    userPage = Math.max(1, userPage - 1);
                    void loadUsers();
                },
                onNext: () => {
                    userPage += 1;
                    void loadUsers();
                },
            });
            userResults.replaceChildren(...cards, controls);
        } catch (requestError) {
            userResults.innerHTML = PassbookCommonComponents.emptyState(requestError.message);
        }
    };

    const render = (items) => {
        const nodes = items.map((item) => {
            const card = document.createElement("article");
            card.className = "report-item";
            const summary = document.createElement("strong");
            summary.textContent = `${item.violation_type} · ${item.reason} · ${item.severity} · ${item.status}`;
            const description = document.createElement("p");
            description.textContent = item.description || "Không có mô tả.";
            card.append(summary, description);
            if (item.status === "OPEN") {
                const resolve = document.createElement("button");
                resolve.className = "button button-outline";
                resolve.type = "button";
                resolve.textContent = "Đánh dấu đã xử lý";
                resolve.addEventListener("click", async () => {
                    resolve.disabled = true;
                    try {
                        await AdminAPI.updateViolation(item.id, {status: "RESOLVED"});
                        await loadViolations();
                    } catch (requestError) {
                        error.textContent = requestError.message;
                    } finally {
                        resolve.disabled = false;
                    }
                });
                card.append(resolve);
            }
            return card;
        });
        violations.replaceChildren(...(nodes.length
            ? nodes
            : [PassbookCommonComponents.emptyState("Tài khoản chưa có vi phạm.")]));
    };

    const loadViolations = async () => {
        if (!userId) return;
        error.textContent = "";
        try {
            const data = await AdminAPI.violations(userId, {page_size: 50});
            render(data.results || []);
        } catch (requestError) {
            error.textContent = requestError.message;
        }
    };

    lookup.addEventListener("submit", async (event) => {
        event.preventDefault();
        userId = lookup.elements.user_id.value.trim();
        await loadViolations();
    });
    userSearch.addEventListener("submit", async (event) => {
        event.preventDefault();
        userPage = 1;
        await loadUsers();
    });
    statusForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!userId) {
            error.textContent = "Trước tiên hãy nhập ID tài khoản.";
            return;
        }
        const submit = statusForm.querySelector("button[type=submit]");
        submit.disabled = true;
        try {
            const result = await AdminAPI.setUserStatus(userId, {
                status: statusForm.elements.status.value,
            });
            showToast(`Trạng thái tài khoản #${result.id}: ${result.status}.`);
            await loadUsers();
        } catch (requestError) {
            error.textContent = requestError.message;
        } finally {
            submit.disabled = false;
        }
    });
    violationForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!userId) {
            error.textContent = "Trước tiên hãy nhập ID tài khoản.";
            return;
        }
        const values = new FormData(violationForm);
        const submit = violationForm.querySelector("button[type=submit]");
        submit.disabled = true;
        try {
            await AdminAPI.addViolation(userId, {
                violation_type: values.get("violation_type").toString().trim(),
                reason: values.get("reason").toString().trim(),
                severity: values.get("severity").toString().trim(),
                description: values.get("description").toString().trim(),
            });
            violationForm.reset();
            await loadViolations();
        } catch (requestError) {
            error.textContent = requestError.message;
        } finally {
            submit.disabled = false;
        }
    });
    void loadUsers();
});
