(function (global) {
    "use strict";

    const sections = {
        overview: ["Tổng quan", "overview"],
        users: ["Tài khoản", "users"],
        marketplace: ["Marketplace", "marketplace"],
        moderation: ["Kiểm duyệt tin", "moderation"],
        reservations: ["Đặt sách", "reservations"],
        borrow: ["Mượn sách", "borrow"],
        commerce: ["Đơn hàng / Commerce", "commerce"],
        payments: ["Thanh toán", "payments"],
        shipping: ["Vận chuyển", "shipping"],
        returns: ["Trả hàng / hoàn tiền", "returns"],
        reports: ["Báo cáo", "reports"],
        messaging: ["Tin nhắn", "messaging"],
        notifications: ["Thông báo", "notifications"],
        reviews: ["Đánh giá", "reviews"],
        favorites: ["Yêu thích", "favorites"],
        demand: ["Nhu cầu", "demand"],
        catalog: ["Danh mục", "catalog"],
        analytics: ["Phân tích", "analytics"],
    };

    const metricNames = {
        total: "Tổng số",
        active: "Đang hoạt động",
        locked_inactive: "Đã khóa / không hoạt động",
        pending: "Pending",
        confirmed: "Đã xác nhận",
        completed: "Hoàn tất",
        cancelled: "Đã hủy",
        rejected: "Đã từ chối",
        failed: "Thất bại",
        paid: "Đã thanh toán",
        refunded: "Đã hoàn tiền",
        return_requested: "Đang yêu cầu trả",
        overdue_borrow: "Quá hạn",
        total_orders: "Tổng đơn hàng",
        total_borrow_orders: "Tổng yêu cầu mượn",
        total_reservations: "Tổng lượt đặt",
        total_buy_requests: "Want to Buy",
        total_borrow_requests: "Want to Borrow",
        total_conversations: "Hội thoại",
        total_messages: "Tin nhắn",
        total_amount: "Tổng giá trị",
        gmv: "GMV (SALE)",
        average_order_value: "Giá trị đơn trung bình",
        average_rating: "Điểm đánh giá trung bình",
        unread: "Chưa đọc",
        today: "Hôm nay",
        this_month: "Tháng này",
        categories: "Danh mục",
        subjects: "Môn học",
        universities: "Trường",
        conversations: "Hội thoại",
        messages: "Tin nhắn",
        notifications: "Thông báo",
        favorites: "Lượt yêu thích",
        reviews: "Đánh giá",
        return_shipment: "Shipment trả sách",
        owner_confirmation_pending: "Chờ chủ sách xác nhận",
    };
    const reservationStatuses = ["PENDING", "CONFIRMED", "REJECTED", "CANCELLED", "EXPIRED", "COMPLETED"];
    const borrowStatuses = ["PENDING", "CONFIRMED", "READY_FOR_PICKUP", "ACTIVE", "RETURN_REQUESTED", "RETURNED", "COMPLETED", "REJECTED", "CANCELLED", "OVERDUE", "DISPUTED"];

    function element(tag, text, className) {
        const node = document.createElement(tag);
        if (text !== undefined && text !== null) node.textContent = String(text);
        if (className) node.className = className;
        return node;
    }

    function humanize(key) {
        return metricNames[key] || String(key).replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function formatValue(value) {
        if (value === null || value === undefined || value === "") return "—";
        if (typeof value === "number") return value.toLocaleString("vi-VN");
        if (typeof value === "boolean") return value ? "Có" : "Không";
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
    }

    function formatMoney(value) {
        const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(value ?? "0"));
        if (!match) return "—";
        const whole = BigInt(match[2]).toLocaleString("vi-VN");
        const fraction = (match[3] || "").replace(/0+$/, "");
        return `${match[1]}${whole}${fraction ? `,${fraction}` : ""} ₫`;
    }

    function addTable(parent, rows, columns) {
        if (!Array.isArray(rows) || !rows.length) {
            parent.append(element("p", "Chưa có dữ liệu.", "empty-state"));
            return;
        }
        const table = element("table", undefined, "admin-data-table");
        const head = document.createElement("thead");
        const headingRow = document.createElement("tr");
        columns.forEach(({label}) => headingRow.append(element("th", label)));
        head.append(headingRow);
        const body = document.createElement("tbody");
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            columns.forEach(({key, render}) => {
                const td = document.createElement("td");
                td.textContent = render ? render(row) : formatValue(row?.[key]);
                tr.append(td);
            });
            body.append(tr);
        });
        table.append(head, body);
        parent.append(table);
    }

    const coreAdminMetricKeys = new Set([
        "total",
        "active",
        "pending",
        "confirmed",
        "completed",
        "cancelled",
        "rejected",
        "failed",
        "paid",
        "refunded",
        "total_orders",
        "total_borrow_orders",
        "total_reservations",
        "gmv",
        "platform_revenue",
        "seller_earnings",
        "shipping",
        "delivered",
        "average_order_value",
        "return_requested",
        "overdue_borrow",
    ]);

    function addMetricCards(parent, data, hiddenKeys = []) {
        const entries = [];
        Object.entries(data || {}).forEach(([key, value]) => {
            if (hiddenKeys.includes(key)) return;
            if (typeof value === "number") {
                if (!coreAdminMetricKeys.has(key)) return;
                entries.push([key, value]);
            } else if (value && typeof value === "object" && !Array.isArray(value)) {
                Object.entries(value).forEach(([nestedKey, nestedValue]) => {
                    if (typeof nestedValue !== "number") return;
                    const metricKey = `${key}.${nestedKey}`;
                    const normalizedKey = nestedKey.toLowerCase();
                    if (!coreAdminMetricKeys.has(normalizedKey) && !coreAdminMetricKeys.has(key)) return;
                    entries.push([metricKey, nestedValue]);
                });
            }
        });
        const cards = element("div", undefined, "admin-metric-grid");
        entries.forEach(([key, value]) => {
            const card = element("article", undefined, "report-item admin-metric");
            card.append(element("span", key.includes(".")
                ? `${humanize(key.split(".")[0])} · ${humanize(key.split(".")[1])}`
                : humanize(key)), element("strong", formatValue(value)));
            cards.append(card);
        });
        if (entries.length) parent.append(cards);
    }

    function addGroups(parent, data) {
        Object.entries(data || {}).forEach(([key, value]) => {
            if (!value || typeof value !== "object" || Array.isArray(value)) return;
            const entries = Object.entries(value);
            if (!entries.length || !entries.every(([, count]) => typeof count === "number")) return;
            const section = element("section", undefined, "admin-data-group");
            section.append(element("h3", humanize(key)));
            addTable(section, entries.map(([name, count]) => ({name, count})), [
                {key: "name", label: "Trạng thái / nhóm"},
                {key: "count", label: "Số lượng"},
            ]);
            parent.append(section);
        });
    }

    function addArrays(parent, data) {
        Object.entries(data || {}).forEach(([key, value]) => {
            if (!Array.isArray(value)) return;
            const section = element("section", undefined, "admin-data-group");
            section.append(element("h3", humanize(key)));
            const first = value.find((item) => item && typeof item === "object");
            const columns = first
                ? Object.keys(first).map((field) => ({key: field, label: humanize(field)}))
                : [{key: "value", label: "Giá trị"}];
            addTable(section, value, columns);
            parent.append(section);
        });
    }

    function sectionShell(title) {
        const wrapper = document.createElement("div");
        const heading = element("div", undefined, "section-heading");
        heading.append(element("h2", title));
        const refresh = element("button", "Tải lại", "button button-outline");
        refresh.type = "button";
        heading.append(refresh);
        wrapper.append(heading);
        return {wrapper, refresh};
    }

    function keyValueTable(data) {
        const flat = [];
        Object.entries(data || {}).forEach(([key, value]) => {
            if (value && typeof value === "object" && !Array.isArray(value)) {
                Object.entries(value).forEach(([nestedKey, nestedValue]) => {
                    flat.push({label: `${humanize(key)} · ${humanize(nestedKey)}`, value: formatValue(nestedValue)});
                });
            } else {
                flat.push({label: humanize(key), value: formatValue(value)});
            }
        });
        return flat;
    }

    function detailCard(title, data) {
        const card = element("article", undefined, "admin-detail-card");
        card.append(element("h3", title));
        addTable(card, keyValueTable(data), [
            {key: "label", label: "Thông tin"},
            {key: "value", label: "Giá trị"},
        ]);
        return card;
    }

    function initialize() {
        const dashboard = document.querySelector("[data-admin-dashboard]");
        if (!dashboard || !global.PassbookGuards.requireRole("ADMIN")) return;
        const view = dashboard.querySelector("[data-admin-view]");
        const error = dashboard.querySelector("[data-admin-error]");
        const nav = dashboard.querySelector("[data-admin-navigation]");
        const simulator = dashboard.querySelector("[data-payment-simulator]");
        let activeSection = "";
        let pendingShipmentId = null;
        const pageBySection = {};
        const queryBySection = {};

        async function loadSummary(section, query = {}) {
            return global.AdminAPI.dashboardSection(section, query);
        }

        function createFilterForm(section, statusOptions, onSubmit, extraFields = []) {
            const form = element("form", undefined, "admin-filter-form");
            const statusLabel = element("label", "Trạng thái");
            const status = element("select", undefined, "form-control");
            status.setAttribute("aria-label", "Lọc theo trạng thái");
            const all = element("option", "Tất cả trạng thái");
            all.value = "";
            status.append(all);
            statusOptions.forEach((value) => {
                const option = element("option", value);
                option.value = value;
                status.append(option);
            });
            statusLabel.append(status);
            form.append(statusLabel);
            const fields = {};
            extraFields.forEach(({key, label, type = "number"}) => {
                const fieldLabel = element("label", label);
                const input = element("input", undefined, "form-control");
                input.type = type;
                input.name = key;
                input.setAttribute("aria-label", label);
                if (type === "date") input.placeholder = "YYYY-MM-DD";
                else input.min = "1";
                fields[key] = input;
                fieldLabel.append(input);
                form.append(fieldLabel);
            });
            const submit = element("button", "Lọc", "button button-primary");
            submit.type = "submit";
            form.append(submit);
            form.addEventListener("submit", (event) => {
                event.preventDefault();
                const query = {status: status.value};
                Object.entries(fields).forEach(([key, input]) => {
                    if (input.value) query[key] = input.value;
                });
                onSubmit(query);
            });
            return {form, status, fields};
        }

        function addPagination(parent, data, section, reload) {
            const controls = element("div", undefined, "component-pagination");
            const count = element("span", `${formatValue(data.count || 0)} kết quả · Trang ${pageBySection[section] || 1}`);
            controls.append(count);
            if (data.previous) {
                const previous = element("button", "Trước", "button button-outline");
                previous.type = "button";
                previous.addEventListener("click", () => {
                    pageBySection[section] = Math.max(1, (pageBySection[section] || 1) - 1);
                    reload();
                });
                controls.append(previous);
            }
            if (data.next) {
                const next = element("button", "Sau", "button button-outline");
                next.type = "button";
                next.addEventListener("click", () => {
                    pageBySection[section] = (pageBySection[section] || 1) + 1;
                    reload();
                });
                controls.append(next);
            }
            parent.append(controls);
        }

        function showError(container, requestError) {
            container.replaceChildren(element("p", requestError.message || "Không thể tải dữ liệu.", "form-error"));
        }

        async function renderRecordSection(section, config, shell, detailContainer) {
            const page = pageBySection[section] || 1;
            const query = {...(queryBySection[section] || {}), page};
            const form = createFilterForm(section, config.statuses, (filters) => {
                queryBySection[section] = filters;
                pageBySection[section] = 1;
                renderSection(section);
            }, [
                {key: "user", label: "User ID"},
                {key: "book", label: "Book ID"},
                {key: "listing", label: "Listing ID"},
                {key: "start_date", label: "Từ ngày", type: "date"},
                {key: "end_date", label: "Đến ngày", type: "date"},
            ]);
            const oldQuery = queryBySection[section] || {};
            form.status.value = oldQuery.status || "";
            Object.entries(form.fields).forEach(([key, input]) => {
                input.value = oldQuery[key] || "";
            });
            const body = element("div");
            shell.wrapper.append(form.form, body, detailContainer);
            const load = async () => {
                body.replaceChildren(element("p", "Đang tải danh sách...", "loading-state"));
                try {
                    const [response, summary] = await Promise.all([
                        config.list(query),
                        config.summary ? loadSummary(config.summary) : Promise.resolve(null),
                    ]);
                    const rows = response.results || [];
                    body.replaceChildren();
                    if (summary) addMetricCards(body, summary);
                    if (!rows.length) body.append(element("p", "Không có bản ghi phù hợp.", "empty-state"));
                    else {
                        const columns = config.columns;
                        addTable(body, rows, columns.map(({key, label, render}) => ({
                            key, label, render: render || ((record) => formatValue(record[key])),
                        })));
                        const buttons = element("div", undefined, "admin-record-links");
                        rows.forEach((record) => {
                            const open = element("button", `Chi tiết #${record.id}`, "button button-outline");
                            open.type = "button";
                            open.addEventListener("click", async () => {
                                open.disabled = true;
                                try {
                                    const detail = await config.detail(record.id);
                                    detailContainer.replaceChildren(detailCard(`${config.detailTitle} #${record.id}`, detail));
                                } catch (requestError) {
                                    detailContainer.replaceChildren(element("p", requestError.message, "form-error"));
                                } finally {
                                    open.disabled = false;
                                }
                            });
                            buttons.append(open);
                        });
                        body.append(buttons);
                    }
                    addPagination(body, response, section, load);
                } catch (requestError) {
                    showError(body, requestError);
                }
            };
            shell.refresh.addEventListener("click", load);
            await load();
        }

        async function renderUsers(shell) {
            const query = {...(queryBySection.users || {}), page: pageBySection.users || 1};
            const form = element("form", undefined, "admin-filter-form");
            const searchLabel = element("label", "Tên, email hoặc điện thoại");
            const search = element("input", undefined, "form-control");
            search.type = "search";
            search.value = (queryBySection.users || {}).search || "";
            search.placeholder = "Tìm tài khoản";
            searchLabel.append(search);
            const status = element("select", undefined, "form-control");
            status.setAttribute("aria-label", "Lọc trạng thái tài khoản");
            [["", "Tất cả trạng thái"], ["ACTIVE", "ACTIVE"], ["BLOCKED", "BLOCKED"], ["PENDING_VERIFICATION", "PENDING_VERIFICATION"]].forEach(([value, label]) => {
                const option = element("option", label);
                option.value = value;
                status.append(option);
            });
            status.value = (queryBySection.users || {}).status || "";
            const statusLabel = element("label", "Trạng thái");
            statusLabel.append(status);
            const roleLabel = element("label", "Vai trò");
            const role = element("select", undefined, "form-control");
            role.setAttribute("aria-label", "Lọc vai trò tài khoản");
            [["", "Tất cả vai trò"], ["STUDENT", "STUDENT"], ["ADMIN", "ADMIN"]].forEach(([value, label]) => {
                const option = element("option", label);
                option.value = value;
                role.append(option);
            });
            role.value = (queryBySection.users || {}).role || "";
            roleLabel.append(role);
            const submit = element("button", "Lọc", "button button-primary");
            submit.type = "submit";
            form.append(searchLabel, statusLabel, roleLabel, submit);
            form.addEventListener("submit", (event) => {
                event.preventDefault();
                queryBySection.users = {search: search.value, status: status.value, role: role.value};
                pageBySection.users = 1;
                renderSection("users");
            });
            const content = element("div");
            shell.wrapper.append(form, content);
            const load = async () => {
                content.replaceChildren(element("p", "Đang tải tài khoản...", "loading-state"));
                try {
                    const [stats, data] = await Promise.all([
                        loadSummary("users"),
                        global.AdminAPI.users(query),
                    ]);
                    content.replaceChildren();
                    addMetricCards(content, stats);
                    const rows = data.results || [];
                    addTable(content, rows, [
                        {key: "id", label: "ID"},
                        {key: "full_name", label: "Tên"},
                        {key: "email", label: "Email"},
                        {key: "role", label: "Vai trò"},
                        {key: "status", label: "Trạng thái"},
                        {key: "created_at", label: "Ngày tạo"},
                    ]);
                    addPagination(content, data, "users", load);
                    const note = element("a", "Mở công cụ quản lý tài khoản", "button button-outline");
                    note.href = "users.html";
                    content.append(note);
                } catch (requestError) {
                    showError(content, requestError);
                }
            };
            shell.refresh.addEventListener("click", load);
            await load();
        }

        function renderReportCard(report, reload) {
            const card = element("article", undefined, "report-item");
            const reasonLabels = {
                INAPPROPRIATE_CONTENT: "Nội dung không phù hợp",
                INCORRECT_BOOK_INFO: "Thông tin sách sai",
                SPAM: "Spam",
                SCAM: "Lừa đảo",
                POLICY_VIOLATION: "Vi phạm chính sách",
                OTHER: "Lý do khác",
            };
            const statusLabels = {
                OPEN: "Mới",
                IN_REVIEW: "Đang xem xét",
                RESOLVED: "Đã xử lý",
                REJECTED: "Từ chối",
            };
            card.append(element(
                "strong",
                `#${report.id} · ${reasonLabels[report.reason] || report.reason || "Báo cáo"}`,
            ));
            card.append(element("p", [
                `Người báo cáo: ${report.reporter_name || `#${report.reporter_id || "—"}`}`,
                report.reported_user_id
                    ? `Tài khoản: ${report.reported_user_name || `#${report.reported_user_id}`}`
                    : "",
                report.book_id
                    ? `Sách: ${report.book_title || `#${report.book_id}`}`
                    : "",
                report.sale_listing_id
                    ? `Tin bán: ${report.sale_listing_title || `#${report.sale_listing_id}`}`
                    : "",
                report.lend_listing_id
                    ? `Tin cho mượn: ${report.lend_listing_title || `#${report.lend_listing_id}`}`
                    : "",
                report.message_id ? `Tin nhắn #${report.message_id}` : "",
                report.message_sender_id
                    ? `Người gửi tin nhắn #${report.message_sender_id}`
                    : "",
                `Người xử lý #${report.handled_by_id || "—"}`,
                statusLabels[report.status] || report.status,
                formatValue(report.created_at),
            ].filter(Boolean).join(" · ")));
            card.append(element("p", report.description || "Không có mô tả."));
            if (report.message_content) {
                const message = element("blockquote", report.message_content, "caption");
                card.append(message);
            }
            const select = element("select", undefined, "form-control");
            ["OPEN", "IN_REVIEW", "RESOLVED", "REJECTED"].forEach((value) => {
                const option = element("option", statusLabels[value]);
                option.value = value;
                option.selected = report.status === value;
                select.append(option);
            });
            const note = element("textarea", undefined, "form-control");
            note.value = report.resolution_note || "";
            note.placeholder = "Ghi chú nội bộ; bắt buộc khi đóng báo cáo";
            const save = element("button", "Lưu xử lý", "button button-primary");
            save.type = "button";
            save.addEventListener("click", async () => {
                save.disabled = true;
                try {
                    await global.AdminAPI.updateReport(report.id, {
                        status: select.value,
                        resolution_note: note.value,
                    });
                    await reload();
                } catch (requestError) {
                    global.showToast(requestError.message);
                } finally {
                    save.disabled = false;
                }
            });
            card.append(select, note, save);
            return card;
        }

        async function renderReports(shell) {
            const selectedStatus = (queryBySection.reports || {}).status || "";
            const filter = createFilterForm("reports", ["OPEN", "IN_REVIEW", "RESOLVED", "REJECTED"], (values) => {
                queryBySection.reports = values;
                pageBySection.reports = 1;
                renderSection("reports");
            });
            const reportStatusLabels = {
                OPEN: "Mới",
                IN_REVIEW: "Đang xem xét",
                RESOLVED: "Đã xử lý",
                REJECTED: "Từ chối",
            };
            [...filter.status.options].forEach((option) => {
                if (reportStatusLabels[option.value]) {
                    option.textContent = reportStatusLabels[option.value];
                }
            });
            filter.status.value = selectedStatus;
            const content = element("div");
            shell.wrapper.append(filter.form, content);
            const load = async () => {
                content.replaceChildren(element("p", "Đang tải báo cáo...", "loading-state"));
                try {
                    const [stats, data] = await Promise.all([
                        loadSummary("reports"),
                        global.AdminAPI.reports({
                            ...(queryBySection.reports || {}),
                            page: pageBySection.reports || 1,
                        }),
                    ]);
                    content.replaceChildren();
                    addMetricCards(content, stats);
                    const list = element("div", undefined, "report-list");
                    (data.results || []).forEach((report) => list.append(renderReportCard(report, load)));
                    if (!data.results?.length) list.append(element("p", "Không có báo cáo phù hợp.", "empty-state"));
                    content.append(list);
                    addPagination(content, data, "reports", load);
                } catch (requestError) {
                    showError(content, requestError);
                }
            };
            shell.refresh.addEventListener("click", load);
            await load();
        }

        async function renderAnalytics(shell) {
            const form = element("form", undefined, "admin-filter-form");
            const periodLabel = element("label", "Khoảng thời gian");
            const period = element("select", undefined, "form-control");
            [["day", "Ngày"], ["week", "Tuần"], ["month", "Tháng"], ["year", "Năm"]].forEach(([value, label]) => {
                const option = element("option", label);
                option.value = value;
                period.append(option);
            });
            period.value = (queryBySection.analytics || {}).period || "day";
            periodLabel.append(period);
            form.append(periodLabel);
            const dateInputs = {};
            ["start_date", "end_date"].forEach((key) => {
                const label = element("label", key === "start_date" ? "Từ ngày" : "Đến ngày");
                const input = element("input", undefined, "form-control");
                input.type = "date";
                input.value = (queryBySection.analytics || {})[key] || "";
                label.append(input);
                form.append(label);
                dateInputs[key] = input;
            });
            const submit = element("button", "Áp dụng", "button button-primary");
            submit.type = "submit";
            form.append(submit);
            const content = element("div");
            shell.wrapper.append(form, content);
            const load = async () => {
                content.replaceChildren(element("p", "Đang tải phân tích...", "loading-state"));
                try {
                    const data = await loadSummary("analytics", queryBySection.analytics || {period: "day"});
                    content.replaceChildren();
                    content.append(element("p", `Khoảng: ${data.period} · ${data.start_date || "—"} – ${data.end_date || "—"}`, "caption"));
                    addArrays(content, data);
                } catch (requestError) {
                    showError(content, requestError);
                }
            };
            form.addEventListener("submit", (event) => {
                event.preventDefault();
                queryBySection.analytics = {
                    period: period.value,
                    start_date: dateInputs.start_date.value,
                    end_date: dateInputs.end_date.value,
                };
                load();
            });
            shell.refresh.addEventListener("click", load);
            await load();
        }

        async function renderShipping(shell) {
            const filters = element("form", undefined, "admin-filter-form");
            const statusLabel = element("label", "Trạng thái");
            const status = element("select", undefined, "form-control");
            status.setAttribute("aria-label", "Lọc trạng thái Shipment");
            [["", "Tất cả"], ["PENDING", "Pending"], ["SHIPPED", "Shipped"], ["PICKED_UP", "Picked Up"], ["IN_TRANSIT", "In Transit"], ["OUT_FOR_DELIVERY", "Out for Delivery"], ["DELIVERED", "Delivered"], ["EXCEPTION", "Exception"], ["RETURNED", "Returned"]].forEach(([value, label]) => {
                const option = element("option", label);
                option.value = value;
                status.append(option);
            });
            status.value = (queryBySection.shipping || {}).status || "";
            statusLabel.append(status);
            const typeLabel = element("label", "Loại giao dịch");
            const type = element("select", undefined, "form-control");
            type.setAttribute("aria-label", "Lọc loại Shipment");
            [["", "Tất cả loại"], ["SALE", "SALE Shipment"], ["BORROW", "BORROW Shipment"], ["BORROW_RETURN", "BORROW RETURN Shipment"]].forEach(([value, label]) => {
                const option = element("option", label);
                option.value = value;
                type.append(option);
            });
            type.value = (queryBySection.shipping || {}).type || "";
            typeLabel.append(type);
            const searchLabel = element("label", "Tracking number");
            const search = element("input", undefined, "form-control");
            search.type = "search";
            search.maxLength = 150;
            search.value = (queryBySection.shipping || {}).search || "";
            searchLabel.append(search);
            const submit = element("button", "Lọc", "button button-primary");
            submit.type = "submit";
            filters.append(statusLabel, typeLabel, searchLabel, submit);

            const summary = element("div");
            const results = element("div");
            const detail = element("div", undefined, "admin-detail-container");
            shell.wrapper.append(
                element("p", "PassBook hiện là đơn vị vận hành vận chuyển. Status updates đi qua state machine dùng chung, có nguồn ADMIN; sau này Carrier API/Webhook có thể dùng cùng domain service.", "caption"),
                filters,
                summary,
                results,
                detail,
            );
            const query = () => ({
                ...(queryBySection.shipping || {}),
                page: pageBySection.shipping || 1,
            });
            let selectedShipmentId = pendingShipmentId;
            pendingShipmentId = null;

            const renderShipmentDetail = async (shipmentId) => {
                selectedShipmentId = shipmentId;
                detail.replaceChildren(element("p", "Đang tải chi tiết Shipment...", "loading-state"));
                try {
                    const shipment = await global.AdminAPI.shipment(shipmentId);
                    detail.replaceChildren();
                    const fields = {
                        tracking_number: shipment.tracking_number,
                        carrier: shipment.carrier,
                        type: shipment.type,
                        direction: shipment.direction,
                        sender: shipment.sender ? `${shipment.sender.name} (${shipment.sender.email})` : "—",
                        receiver: shipment.receiver ? `${shipment.receiver.name} (${shipment.receiver.email})` : "—",
                        order: shipment.order ? `#${shipment.order.id} · ${shipment.order.code} · ${shipment.order.type} · ${shipment.order.status}` : "—",
                        borrow: shipment.borrow ? `#${shipment.borrow.id} · ${shipment.borrow.status}` : "—",
                        late_days: shipment.type === "BORROW_RETURN"
                            ? shipment.borrow?.late_days ?? 0
                            : undefined,
                        late_fee_per_day: shipment.type === "BORROW_RETURN"
                            ? formatMoney(shipment.borrow?.late_fee_per_day)
                            : undefined,
                        late_fee_estimate: shipment.type === "BORROW_RETURN"
                            ? formatMoney(shipment.borrow?.late_fee_estimate)
                            : undefined,
                        late_fee_confirmed: shipment.type === "BORROW_RETURN"
                            ? formatMoney(shipment.borrow?.late_fee_amount)
                            : undefined,
                        status: shipment.status,
                        created_at: shipment.created_at,
                        updated_at: shipment.updated_at,
                    };
                    detail.append(detailCard(`Shipment #${shipment.id}`, fields));
                    const actions = element("section", undefined, "admin-data-group");
                    actions.append(element("h3", "Cập nhật trạng thái"));
                    if (shipment.allowed_next_statuses?.length) {
                        const form = element("form", undefined, "admin-filter-form");
                        const label = element("label", "Trạng thái tiếp theo hợp lệ");
                        const nextStatus = element("select", undefined, "form-control");
                        shipment.allowed_next_statuses.forEach((next) => {
                            const option = element("option", next);
                            option.value = next;
                            nextStatus.append(option);
                        });
                        label.append(nextStatus);
                        const noteLabel = element("label", "Ghi chú");
                        const note = element("input", undefined, "form-control");
                        note.type = "text";
                        note.maxLength = 5000;
                        noteLabel.append(note);
                        const locationLabel = element("label", "Vị trí (nếu có)");
                        const location = element("input", undefined, "form-control");
                        location.type = "text";
                        location.maxLength = 255;
                        locationLabel.append(location);
                        const update = element("button", "Cập nhật shipment", "button button-primary");
                        update.type = "submit";
                        form.append(label, noteLabel, locationLabel, update);
                        form.addEventListener("submit", async (event) => {
                            event.preventDefault();
                            const isBorrowDelivery = shipment.type === "BORROW"
                                && nextStatus.value === "DELIVERED";
                            const isBorrowReturn = shipment.type === "BORROW_RETURN"
                                && nextStatus.value === "DELIVERED";
                            const message = isBorrowDelivery
                                ? `Xác nhận đã giao sách và thu COD cho phiếu mượn #${shipment.borrow?.id}? Chỉ sau xác nhận này, phiếu mới chuyển sang đang mượn.`
                                : isBorrowReturn
                                    ? `Xác nhận đã nhận lại sách của phiếu #${shipment.borrow?.id}? Hệ thống sẽ chốt phí trễ ${formatMoney(shipment.borrow?.late_fee_estimate)}, hoàn tất phiếu và mở lại sách.`
                                    : `Xác nhận chuyển Shipment #${shipment.id} từ ${shipment.status} sang ${nextStatus.value}?`;
                            if (!global.confirm(message)) return;
                            update.disabled = true;
                            try {
                                const result = await global.AdminAPI.updateShipmentStatus(
                                    shipment.id,
                                    {
                                        status: nextStatus.value,
                                        note: note.value,
                                        location: location.value,
                                    },
                                );
                                global.showToast(`Shipment #${result.id}: ${result.old_status} → ${result.status}.`);
                                await load();
                                await renderShipmentDetail(shipment.id);
                            } catch (requestError) {
                                actions.append(element("p", requestError.message, "form-error"));
                            } finally {
                                update.disabled = false;
                            }
                        });
                        actions.append(form);
                    } else {
                        actions.append(element("p", "Không còn trạng thái tiếp theo hợp lệ.", "caption"));
                    }
                    detail.append(actions);

                    const historySection = element("section", undefined, "admin-data-group");
                    historySection.append(element("h3", "Lịch sử trạng thái"));
                    if (shipment.status_history?.length) {
                        const history = shipment.status_history.map((entry) => ({
                            event: `#${entry.id} · ${entry.status}`,
                            source: entry.source,
                            changed_by: entry.changed_by_id ? `#${entry.changed_by_id}` : "—",
                            location: entry.location,
                            note: entry.note,
                            time: entry.occurred_at,
                        }));
                        addTable(historySection, history, [
                            {key: "event", label: "Trạng thái"},
                            {key: "source", label: "Nguồn"},
                            {key: "changed_by", label: "Người cập nhật"},
                            {key: "location", label: "Vị trí"},
                            {key: "note", label: "Ghi chú"},
                            {key: "time", label: "Thời gian"},
                        ]);
                    } else {
                        historySection.append(element("p", "Chưa có sự kiện tracking.", "empty-state"));
                    }
                    detail.append(historySection);
                } catch (requestError) {
                    showError(detail, requestError);
                }
            };

            const load = async () => {
                results.replaceChildren(element("p", "Đang tải shipments...", "loading-state"));
                try {
                    const [stats, data] = await Promise.all([
                        loadSummary("shipping"),
                        global.AdminAPI.shipments(query()),
                    ]);
                    summary.replaceChildren();
                    addMetricCards(summary, stats);
                    results.replaceChildren();
                    const rows = data.results || [];
                    if (!rows.length) results.append(element("p", "Không có Shipment phù hợp.", "empty-state"));
                    else {
                        addTable(results, rows, [
                            {key: "tracking_number", label: "Tracking number"},
                            {key: "type", label: "Loại"},
                            {key: "direction", label: "Hướng"},
                            {key: "sender", label: "Người gửi", render: (row) => row.sender?.name || "—"},
                            {key: "receiver", label: "Người nhận", render: (row) => row.receiver?.name || "—"},
                            {key: "order", label: "Đơn hàng", render: (row) => `#${row.order?.id || "—"} · ${row.order?.status || "—"}`},
                            {key: "status", label: "Trạng thái"},
                            {key: "created_at", label: "Ngày tạo"},
                            {key: "updated_at", label: "Cập nhật"},
                        ]);
                        const recordButtons = element("div", undefined, "admin-record-links");
                        rows.forEach((row) => {
                            const button = element("button", `Chi tiết Shipment #${row.id}`, "button button-outline");
                            button.type = "button";
                            button.addEventListener("click", () => renderShipmentDetail(row.id));
                            recordButtons.append(button);
                        });
                        results.append(recordButtons);
                    }
                    addPagination(results, data, "shipping", load);
                    if (selectedShipmentId && !detail.firstChild) {
                        await renderShipmentDetail(selectedShipmentId);
                    }
                } catch (requestError) {
                    summary.replaceChildren();
                    showError(results, requestError);
                }
            };

            filters.addEventListener("submit", (event) => {
                event.preventDefault();
                queryBySection.shipping = {
                    status: status.value,
                    type: type.value,
                    search: search.value.trim(),
                };
                pageBySection.shipping = 1;
                load();
            });
            shell.refresh.addEventListener("click", async () => {
                await load();
                if (selectedShipmentId) await renderShipmentDetail(selectedShipmentId);
            });
            await load();
        }

        async function renderCommerce(shell) {
            const summary = element("div");
            const filters = element("form", undefined, "admin-filter-form");
            const statusLabel = element("label", "Order status");
            const status = element("select", undefined, "form-control");
            status.setAttribute("aria-label", "Lọc Order status");
            [["", "Tất cả trạng thái"], ["PENDING_PAYMENT", "PENDING_PAYMENT"], ["CONFIRMED", "CONFIRMED"], ["PROCESSING", "PROCESSING"], ["COMPLETED", "COMPLETED"], ["CANCELLED", "CANCELLED"], ["DISPUTED", "DISPUTED"]].forEach(([value, label]) => {
                const option = element("option", label);
                option.value = value;
                status.append(option);
            });
            status.value = (queryBySection.commerce || {}).status || "";
            statusLabel.append(status);
            const typeLabel = element("label", "Order type");
            const type = element("select", undefined, "form-control");
            type.setAttribute("aria-label", "Lọc Order type");
            [["", "Tất cả"], ["SALE", "SALE"], ["BORROW", "BORROW"]].forEach(([value, label]) => {
                const option = element("option", label);
                option.value = value;
                type.append(option);
            });
            type.value = (queryBySection.commerce || {}).type || "";
            typeLabel.append(type);
            const searchLabel = element("label", "Tìm Order / người mua / người bán");
            const search = element("input", undefined, "form-control");
            search.type = "search";
            search.value = (queryBySection.commerce || {}).search || "";
            searchLabel.append(search);
            const submit = element("button", "Lọc", "button button-primary");
            submit.type = "submit";
            filters.append(statusLabel, typeLabel, searchLabel, submit);
            const results = element("div");
            const detail = element("div", undefined, "admin-detail-container");
            shell.wrapper.append(summary, filters, results, detail);

            const load = async () => {
                const query = {
                    ...(queryBySection.commerce || {}),
                    page: pageBySection.commerce || 1,
                };
                results.replaceChildren(element("p", "Đang tải danh sách Order...", "loading-state"));
                try {
                    const [metrics, response] = await Promise.all([
                        loadSummary("commerce"),
                        global.AdminAPI.orders(query),
                    ]);
                    summary.replaceChildren();
                    addMetricCards(summary, metrics);
                    addGroups(summary, metrics);
                    summary.append(element(
                        "p",
                        "GMV chỉ tính SALE; Borrow được thống kê riêng. Shipment DELIVERED hoàn tất SALE Order tự động.",
                        "caption",
                    ));
                    results.replaceChildren();
                    const rows = response.results || [];
                    if (!rows.length) {
                        results.append(element("p", "Không có Order phù hợp.", "empty-state"));
                    } else {
                        addTable(results, rows, [
                            {key: "id", label: "ID"},
                            {key: "order_code", label: "Mã đơn"},
                            {key: "order_type", label: "Loại"},
                            {key: "buyer", label: "Buyer", render: (row) => row.buyer?.name || "—"},
                            {key: "seller", label: "Seller", render: (row) => row.seller?.name || "—"},
                            {key: "amount", label: "Customer Total", render: (row) => formatMoney(row.amount)},
                            {key: "status", label: "Order status"},
                            {key: "payment_status", label: "Payment status"},
                            {key: "shipments", label: "Shipment status", render: (row) => (row.shipments || []).map((shipment) => shipment.status).join(", ") || "—"},
                        ]);
                        const buttons = element("div", undefined, "admin-record-links");
                        rows.forEach((row) => {
                            const open = element("button", `Chi tiết Order #${row.id}`, "button button-outline");
                            open.type = "button";
                            open.addEventListener("click", async () => {
                                open.disabled = true;
                                detail.replaceChildren(element("p", "Đang tải chi tiết Order...", "loading-state"));
                                try {
                                    const order = await global.AdminAPI.order(row.id);
                                    detail.replaceChildren(detailCard(`Order #${order.id}`, {
                                        order_code: order.order_code,
                                        order_type: order.order_type,
                                        order_status: order.status,
                                        buyer: order.buyer ? `${order.buyer.name} (${order.buyer.email})` : "—",
                                        seller: order.seller ? `${order.seller.name} (${order.seller.email})` : "—",
                                        amount: `${order.amount} ${order.currency || ""}`,
                                        payment_status: order.payment_status,
                                        created_at: order.created_at,
                                        completed_at: order.completed_at,
                                    }));
                                    const payments = element("section", undefined, "admin-data-group");
                                    payments.append(element("h3", "Payments"));
                                    addTable(payments, order.payments || [], [
                                        {key: "id", label: "ID"},
                                        {key: "payment_method", label: "Method"},
                                        {key: "status", label: "Status"},
                                        {key: "amount", label: "Customer Total", render: (payment) => formatMoney(payment.amount)},
                                        {key: "platform_fee", label: "Platform Fee", render: (payment) => formatMoney(payment.platform_fee)},
                                        {key: "seller_amount", label: "Seller Earnings", render: (payment) => formatMoney(payment.seller_amount)},
                                        {key: "reference", label: "Reference"},
                                        {key: "provider", label: "Provider"},
                                        {key: "paid_at", label: "Paid at"},
                                    ]);
                                    detail.append(payments);
                                    const items = element("section", undefined, "admin-data-group");
                                    items.append(element("h3", "Books"));
                                    addTable(items, order.items || [], [
                                        {key: "title", label: "Book"},
                                        {key: "book_id", label: "Book ID"},
                                        {key: "listing_id", label: "Listing ID"},
                                        {key: "seller", label: "Seller"},
                                        {key: "amount", label: "Amount"},
                                    ]);
                                    detail.append(items);
                                    const shipments = element("section", undefined, "admin-data-group");
                                    shipments.append(element("h3", "Shipments & tracking"));
                                    if (!order.shipments?.length) {
                                        shipments.append(element("p", "Chưa có Shipment.", "empty-state"));
                                    } else {
                                        order.shipments.forEach((shipment) => {
                                            const card = element("article", undefined, "admin-detail-card");
                                            card.append(element("h4", `Shipment #${shipment.id} · ${shipment.status}`));
                                            card.append(element("p", `Tracking: ${shipment.tracking_number || "—"} · Carrier: ${shipment.carrier || "PassBook"}`));
                                            addTable(card, shipment.history || [], [
                                                {key: "status", label: "Status"},
                                                {key: "source", label: "Source"},
                                                {key: "changed_by_id", label: "Changed by"},
                                                {key: "location", label: "Location"},
                                                {key: "note", label: "Note"},
                                                {key: "occurred_at", label: "Time"},
                                            ]);
                                            const openShipment = element("button", `Mở Shipment #${shipment.id} trong Shipping`, "button button-outline");
                                            openShipment.type = "button";
                                            openShipment.addEventListener("click", () => {
                                                pendingShipmentId = shipment.id;
                                                history.pushState(null, "", "#shipping");
                                                renderSection("shipping");
                                            });
                                            card.append(openShipment);
                                            shipments.append(card);
                                        });
                                    }
                                    detail.append(shipments);
                                } catch (requestError) {
                                    showError(detail, requestError);
                                } finally {
                                    open.disabled = false;
                                }
                            });
                            buttons.append(open);
                        });
                        results.append(buttons);
                    }
                    addPagination(results, response, "commerce", load);
                } catch (requestError) {
                    summary.replaceChildren();
                    showError(results, requestError);
                }
            };
            filters.addEventListener("submit", (event) => {
                event.preventDefault();
                queryBySection.commerce = {
                    status: status.value,
                    type: type.value,
                    search: search.value.trim(),
                };
                pageBySection.commerce = 1;
                load();
            });
            shell.refresh.addEventListener("click", load);
            await load();
        }

        async function renderSummary(section, shell) {
            const content = element("div");
            shell.wrapper.append(content);
            const renderOverview = (data) => {
                const makeMetric = (label, value, detail, money = false) => {
                    const card = element("article", undefined, "report-item admin-metric");
                    card.append(
                        element("span", label),
                        element("strong", money ? formatMoney(value) : formatValue(value)),
                    );
                    if (detail) card.append(element("small", detail));
                    return card;
                };
                const kpis = element("div", undefined, "admin-metric-grid");
                kpis.append(
                    makeMetric(
                        "Người dùng",
                        data.users?.total,
                        `${formatValue(data.users?.active || 0)} hoạt động`,
                    ),
                    makeMetric(
                        "Tin đăng",
                        data.listings?.total,
                        `${formatValue(data.listings?.active || 0)} active · ${formatValue(data.listings?.pending || 0)} chờ · ${formatValue(data.listings?.sold || 0)} đã bán`,
                    ),
                    makeMetric(
                        "Đơn hàng",
                        data.orders?.total,
                        `${formatValue(data.orders?.pending || 0)} chờ · ${formatValue(data.orders?.completed || 0)} hoàn tất`,
                    ),
                    makeMetric("Platform Revenue", data.finance?.platform_revenue, "Doanh thu phí ròng sau refund", true),
                    makeMetric("Seller Earnings", data.finance?.seller_earnings, "Thu nhập ròng được phân bổ", true),
                );
                content.append(kpis);

                const paymentSection = element("section", undefined, "admin-data-group");
                paymentSection.append(element("h3", "Thanh toán"));
                addTable(paymentSection, [
                    {label: "Paid Orders", value: formatValue(data.payments?.paid_orders || 0)},
                    {label: "Pending Payments", value: formatValue(data.payments?.pending_payments || 0)},
                ], [
                    {key: "label", label: "Chỉ số"},
                    {key: "value", label: "Số lượng"},
                ]);
                content.append(paymentSection);

                const operations = element("section", undefined, "admin-data-group");
                operations.append(element("h3", "Vận hành"));
                const operationsGrid = element("div", undefined, "admin-metric-grid");
                [
                    ["Pending Orders", data.orders?.pending],
                    ["Pending Reservations", data.reservations?.pending],
                    ["Pending Borrow", data.borrow?.pending],
                    ["Active Shipments", data.shipments?.active],
                    ["Pending Returns", data.returns?.pending],
                    ["Pending Refunds", data.refunds?.pending],
                ].forEach(([label, value]) => {
                    operationsGrid.append(makeMetric(label, value));
                });
                operations.append(operationsGrid);
                content.append(operations);

                const moderation = element("section", undefined, "admin-data-group");
                moderation.append(element("h3", "Kiểm duyệt"));
                moderation.append(makeMetric(
                    "Open Reports",
                    data.reports?.open ?? data.reports?.pending,
                ));
                content.append(moderation);
            };

            const renderPayments = async (data) => {
                const finance = data;
                const metrics = element("div", undefined, "admin-metric-grid");
                [
                    ["GMV", finance.gmv],
                    ["Platform Revenue", finance.platform_revenue],
                    ["Seller Earnings", finance.seller_earnings],
                    ["Net Customer Payments", finance.customer_total],
                ].forEach(([label, value]) => {
                    const card = element("article", undefined, "report-item admin-metric");
                    card.append(element("span", label), element("strong", formatMoney(value)));
                    metrics.append(card);
                });
                content.append(metrics);
                content.append(element(
                    "p",
                    "Chỉ tính SALE Payment thành công, trừ phần refund đã hoàn tất. Borrow không được tính vào doanh thu bán hàng.",
                    "caption",
                ));

                const filters = element("form", undefined, "admin-filter-form");
                const status = element("select", undefined, "form-control");
                status.setAttribute("aria-label", "Lọc Payment theo trạng thái");
                [["", "Mọi trạng thái"], ["PENDING", "PENDING"], ["PROCESSING", "Chờ xác minh"], ["PAID", "PAID"], ["FAILED", "FAILED"], ["REFUNDED", "REFUNDED"], ["CANCELLED", "CANCELLED"]]
                    .forEach(([value, label]) => {
                        const option = element("option", label);
                        option.value = value;
                        status.append(option);
                    });
                const method = element("select", undefined, "form-control");
                method.setAttribute("aria-label", "Lọc Payment theo phương thức");
                [["", "Mọi phương thức"], ["FAKE", "Fake / Online"], ["COD", "COD"], ["BANK_TRANSFER", "Bank Transfer"]]
                    .forEach(([value, label]) => {
                        const option = element("option", label);
                        option.value = value;
                        method.append(option);
                    });
                const type = element("select", undefined, "form-control");
                type.setAttribute("aria-label", "Lọc Payment theo loại Order");
                [["", "SALE + BORROW"], ["SALE", "SALE"], ["BORROW", "BORROW"]]
                    .forEach(([value, label]) => {
                        const option = element("option", label);
                        option.value = value;
                        type.append(option);
                    });
                const search = element("input", undefined, "form-control");
                search.type = "search";
                search.placeholder = "Order / payment reference / người dùng";
                const submit = element("button", "Lọc", "button button-primary");
                submit.type = "submit";
                filters.append(status, method, type, search, submit);
                const results = element("div");
                const detail = element("div", undefined, "admin-detail-container");
                content.append(filters, results, detail);

                const loadPayments = async () => {
                    const query = {
                        ...(queryBySection.payments || {}),
                        page: pageBySection.payments || 1,
                    };
                    results.replaceChildren(element("p", "Đang tải Payments...", "loading-state"));
                    try {
                        const response = await global.AdminAPI.payments(query);
                        results.replaceChildren();
                        const rows = response.results || [];
                        addTable(results, rows, [
                            {key: "id", label: "Payment ID"},
                            {key: "order_code", label: "Order"},
                            {key: "order_type", label: "Loại"},
                            {key: "customer", label: "Customer", render: (row) => row.customer?.name || "—"},
                            {key: "seller", label: "Seller", render: (row) => row.seller?.name || "—"},
                            {key: "payment_method", label: "Method"},
                            {key: "status", label: "Status", render: (row) => row.status === "PROCESSING" && row.payment_method === "BANK_TRANSFER" ? "PENDING_VERIFICATION" : row.status},
                            {key: "amount", label: "Customer Total", render: (row) => formatMoney(row.amount)},
                            {key: "platform_fee", label: "Platform Fee", render: (row) => formatMoney(row.platform_fee)},
                            {key: "seller_earnings", label: "Seller Earnings", render: (row) => formatMoney(row.seller_earnings)},
                            {key: "reference", label: "Reference"},
                        ]);
                        const actions = element("div", undefined, "admin-record-links");
                        rows.forEach((row) => {
                            const open = element("button", `Chi tiết Payment #${row.id}`, "button button-outline");
                            open.type = "button";
                            open.addEventListener("click", async () => {
                                open.disabled = true;
                                try {
                                    const payment = await global.AdminAPI.payment(row.id);
                                    detail.replaceChildren(detailCard(`Payment #${payment.id}`, {
                                        order: `${payment.order_code} (${payment.order_type})`,
                                        order_status: payment.order_status,
                                        customer: `${payment.customer?.name || "—"} · ${payment.customer?.email || ""}`,
                                        seller: `${payment.seller?.name || "—"} · ${payment.seller?.email || ""}`,
                                        method: payment.payment_method,
                                        status: payment.status === "PROCESSING" && payment.payment_method === "BANK_TRANSFER" ? "PENDING_VERIFICATION" : payment.status,
                                        subtotal: formatMoney(payment.subtotal),
                                        platform_fee: formatMoney(payment.platform_fee),
                                        customer_total: formatMoney(payment.customer_total),
                                        seller_earnings: formatMoney(payment.seller_earnings),
                                        reference: payment.reference,
                                        created_at: payment.created_at,
                                        updated_at: payment.updated_at,
                                        paid_at: payment.paid_at,
                                    }));
                                    const refunds = element("section", undefined, "admin-data-group");
                                    refunds.append(element("h3", "Refunds"));
                                    addTable(refunds, payment.refunds || [], [
                                        {key: "id", label: "Refund ID"},
                                        {key: "amount", label: "Amount", render: (refund) => formatMoney(refund.amount)},
                                        {key: "status", label: "Status"},
                                        {key: "reference", label: "Reference"},
                                        {key: "completed_at", label: "Completed At"},
                                    ]);
                                    detail.append(refunds);
                                    if (payment.payment_method === "BANK_TRANSFER" && payment.status === "PROCESSING") {
                                        const bankActions = element("div", undefined, "admin-record-links");
                                        [["PAID", "Xác minh đã nhận tiền"], ["FAILED", "Từ chối xác minh"]]
                                            .forEach(([target, label]) => {
                                                const action = element("button", label, "button button-outline");
                                                action.type = "button";
                                                action.addEventListener("click", async () => {
                                                    action.disabled = true;
                                                    try {
                                                        await global.AdminAPI.reviewBankTransfer(payment.id, {status: target});
                                                        pageBySection.payments = 1;
                                                        await load();
                                                    } catch (requestError) {
                                                        showError(detail, requestError);
                                                    } finally {
                                                        action.disabled = false;
                                                    }
                                                });
                                                bankActions.append(action);
                                            });
                                        detail.append(bankActions);
                                    }
                                } catch (requestError) {
                                    showError(detail, requestError);
                                } finally {
                                    open.disabled = false;
                                }
                            });
                            actions.append(open);
                        });
                        results.append(actions);
                        addPagination(results, response, "payments", loadPayments);
                    } catch (requestError) {
                        showError(results, requestError);
                    }
                };
                status.value = queryBySection.payments?.status || "";
                method.value = queryBySection.payments?.method || "";
                type.value = queryBySection.payments?.type || "";
                search.value = queryBySection.payments?.search || "";
                filters.addEventListener("submit", (event) => {
                    event.preventDefault();
                    queryBySection.payments = {
                        status: status.value,
                        method: method.value,
                        type: type.value,
                        search: search.value.trim(),
                    };
                    pageBySection.payments = 1;
                    loadPayments();
                });
                await loadPayments();
            };

            const load = async () => {
                content.replaceChildren(element("p", "Đang tải dữ liệu...", "loading-state"));
                try {
                    const data = await loadSummary(section);
                    content.replaceChildren();
                    if (section === "overview") {
                        renderOverview(data);
                        return;
                    }
                    if (section === "payments") {
                        await renderPayments(data);
                        return;
                    }
                    addMetricCards(content, data);
                    addGroups(content, data);
                    addArrays(content, data);
                    if (section === "marketplace") {
                        content.append(element("p", "Tổng quan số lượng và trạng thái tin đăng trong chợ sách.", "caption"));
                    } else if (section === "commerce") {
                        content.append(element("p", "GMV chỉ tính đơn mua bán; giao dịch mượn được thống kê riêng.", "caption"));
                    } else if (section === "shipping") {
                        content.append(element("p", "Theo dõi và cập nhật vận chuyển giao sách, nhận lại sách mượn và đơn mua bán.", "caption"));
                    } else if (section === "returns") {
                        content.append(element("h3", "Borrow Return · BORROWER → OWNER"));
                        content.append(element("p", "Trả sách mượn được xử lý qua vận chuyển và xác nhận đã nhận lại sách.", "caption"));
                        content.append(element("h3", "Sale Return / Refund"));
                        content.append(element("p", "Đơn hoàn hàng và hoàn tiền mua bán được theo dõi riêng với trả sách mượn.", "caption"));
                    } else if (section === "demand") {
                        content.append(element("p", "Thống kê các yêu cầu mua và mượn sách do cộng đồng đăng.", "caption"));
                    } else if (section === "borrow") {
                        content.append(element("p", "Admin theo dõi phiếu mượn và vận chuyển; người mượn hoặc chủ sách xử lý các quyết định của giao dịch.", "caption"));
                    }
                } catch (requestError) {
                    showError(content, requestError);
                }
            };
            shell.refresh.addEventListener("click", load);
            await load();
        }

        async function renderModeration(shell) {
            let listingType = "sale";
            const filters = element("form", undefined, "admin-filter-form");
            const typeTabs = element("div", undefined, "admin-dashboard-nav");
            const results = element("div");
            const statusLabel = element("label", "Trạng thái");
            const status = element("select", undefined, "form-control");
            status.setAttribute("aria-label", "Lọc tin theo trạng thái");
            [
                ["PENDING", "Chờ duyệt"],
                ["ACTIVE", "Đã duyệt"],
                ["REJECTED", "Đã từ chối"],
                ["CLOSED", "Đã xóa"],
                ["", "Tất cả"],
            ].forEach(([value, label]) => {
                const option = element("option", label);
                option.value = value;
                status.append(option);
            });
            statusLabel.append(status);
            const searchLabel = element("label", "Tìm tin / người đăng");
            const search = element("input", undefined, "form-control");
            search.type = "search";
            search.setAttribute("aria-label", "Tìm theo tên sách hoặc người đăng");
            searchLabel.append(search);
            const submit = element("button", "Lọc", "button button-primary");
            submit.type = "submit";
            filters.append(statusLabel, searchLabel, submit);

            const message = element("p", undefined, "caption");
            const updateTabs = () => {
                typeTabs.replaceChildren();
                [
                    ["sale", "Tin bán"],
                    ["borrow", "Tin cho mượn"],
                ].forEach(([value, label]) => {
                    const tab = element(
                        "button",
                        label,
                        listingType === value
                            ? "button button-primary"
                            : "button button-outline",
                    );
                    tab.type = "button";
                    if (listingType === value) tab.setAttribute("aria-current", "page");
                    tab.addEventListener("click", () => {
                        listingType = value;
                        pageBySection[`moderation-${listingType}`] = 1;
                        updateTabs();
                        load();
                    });
                    typeTabs.append(tab);
                });
            };

            const load = async () => {
                const sectionKey = `moderation-${listingType}`;
                const page = pageBySection[sectionKey] || 1;
                results.replaceChildren(element("p", "Đang tải tin đăng...", "loading-state"));
                message.textContent = "";
                try {
                    const data = await global.AdminAPI.listingsForModeration(
                        listingType,
                        {
                            status: status.value || undefined,
                            search: search.value.trim() || undefined,
                            page,
                        },
                    );
                    results.replaceChildren();
                    if (!data.results?.length) {
                        results.append(element("p", "Không có tin đăng phù hợp.", "empty-state"));
                    }
                    data.results?.forEach((listing) => {
                        const card = element("article", undefined, "admin-detail-card");
                        const heading = element("div", undefined, "section-heading");
                        heading.append(
                            element("h3", listing.title),
                            element("span", listing.status),
                        );
                        card.append(heading);
                        if (listing.book?.images?.[0]) {
                            const image = element("img");
                            image.src = listing.book.images[0];
                            image.alt = `Ảnh bìa: ${listing.title}`;
                            image.loading = "lazy";
                            image.width = 120;
                            card.append(image);
                        }
                        card.append(element(
                            "p",
                            `Người đăng: ${listing.owner?.name || "—"} (${listing.owner?.email || "—"})`,
                        ));
                        card.append(element(
                            "p",
                            `${listingType === "sale" ? "Giá bán" : "Phí mượn"}: ${formatMoney(listing.price)}`,
                        ));
                        card.append(element(
                            "p",
                            `Sách: ${listing.book?.title || "—"} · Tác giả: ${listing.book?.author || "—"} · Tình trạng: ${listing.book?.condition_status || "—"}`,
                        ));
                        if (listing.book?.category || listing.book?.edition || listing.book?.publication_year) {
                            card.append(element(
                                "p",
                                `Danh mục: ${listing.book.category || "—"} · Ấn bản: ${listing.book.edition || "—"} · Năm: ${listing.book.publication_year || "—"}`,
                            ));
                        }
                        if (listing.description) {
                            card.append(element("p", listing.description));
                        }
                        card.append(element(
                            "small",
                            `Đăng lúc: ${new Date(listing.created_at).toLocaleString("vi-VN")}`,
                        ));
                        if (listing.status === "PENDING") {
                            const actions = element("div", undefined, "section-heading");
                            const approve = element("button", "Duyệt tin", "button button-primary");
                            approve.type = "button";
                            approve.addEventListener("click", async () => {
                                approve.disabled = true;
                                try {
                                    await global.AdminAPI.moderateListing(
                                        listingType,
                                        listing.id,
                                        {action: "APPROVE"},
                                    );
                                    message.textContent = `Đã duyệt tin “${listing.title}”.`;
                                    await load();
                                } catch (requestError) {
                                    approve.disabled = false;
                                    message.textContent = requestError.message || "Không thể duyệt tin.";
                                }
                            });
                            const reject = element("button", "Từ chối", "button button-outline");
                            reject.type = "button";
                            reject.addEventListener("click", async () => {
                                if (!global.confirm(`Từ chối tin “${listing.title}”?`)) return;
                                reject.disabled = true;
                                try {
                                    await global.AdminAPI.moderateListing(
                                        listingType,
                                        listing.id,
                                        {action: "REJECT"},
                                    );
                                    message.textContent = `Đã từ chối tin “${listing.title}”.`;
                                    await load();
                                } catch (requestError) {
                                    reject.disabled = false;
                                    message.textContent = requestError.message || "Không thể từ chối tin.";
                                }
                            });
                            actions.append(approve, reject);
                            card.append(actions);
                        }
                        if (!["CLOSED", "RESERVED", "SOLD", "ON_LOAN"].includes(listing.status)) {
                            const remove = element("button", "Xóa bài đăng", "button button-outline");
                            remove.type = "button";
                            remove.addEventListener("click", async () => {
                                if (!global.confirm(
                                    `Xóa bài đăng “${listing.title}” khỏi Marketplace? Lịch sử sách và giao dịch sẽ được giữ lại.`,
                                )) return;
                                remove.disabled = true;
                                try {
                                    await global.AdminAPI.deleteListing(
                                        listingType,
                                        listing.id,
                                    );
                                    message.textContent = `Đã xóa bài đăng “${listing.title}”.`;
                                    await load();
                                } catch (requestError) {
                                    remove.disabled = false;
                                    message.textContent = requestError.message || "Không thể xóa bài đăng.";
                                }
                            });
                            card.append(remove);
                        } else if (["RESERVED", "SOLD", "ON_LOAN"].includes(listing.status)) {
                            card.append(element(
                                "p",
                                "Không thể xóa tin đang có giao dịch hoặc đang được giữ chỗ.",
                                "caption",
                            ));
                        }
                        results.append(card);
                    });
                    addPagination(results, data, sectionKey, load);
                } catch (requestError) {
                    showError(results, requestError);
                }
            };

            shell.wrapper.append(typeTabs, filters, message, results);
            updateTabs();
            filters.addEventListener("submit", (event) => {
                event.preventDefault();
                pageBySection[`moderation-${listingType}`] = 1;
                load();
            });
            shell.refresh.addEventListener("click", load);
            await load();
        }

        async function renderSection(section) {
            if (!sections[section]) section = "overview";
            activeSection = section;
            if (simulator) simulator.hidden = section !== "payments";
            const activeLink = [...nav.querySelectorAll("[data-section]")]
                .find((link) => link.dataset.section === section);
            nav.querySelectorAll("[data-section]").forEach((link) => {
                if (link === activeLink) link.setAttribute("aria-current", "page");
                else link.removeAttribute("aria-current");
            });
            nav.querySelectorAll(".admin-nav-group").forEach((group) => {
                group.open = Boolean(activeLink && group.contains(activeLink));
            });
            error.textContent = "";
            view.replaceChildren();
            const [title] = sections[section];
            const shell = sectionShell(title);
            view.append(shell.wrapper);
            if (section === "reservations" || section === "borrow") {
                const detail = element("div", undefined, "admin-detail-container");
                detail.append(element("p", section === "reservations"
                    ? "Admin theo dõi trạng thái; người đặt và chủ sách xử lý yêu cầu."
                    : "Admin theo dõi phiếu mượn; giao nhận và trả sách được quản lý trong mục Vận chuyển.", "caption"));
                const config = section === "reservations" ? {
                    statuses: reservationStatuses,
                    list: (query) => global.AdminAPI.reservations(query),
                    detail: (id) => global.AdminAPI.reservation(id),
                    detailTitle: "Reservation",
                    columns: [
                        {key: "id", label: "ID"},
                        {key: "requester", label: "Người đặt", render: (row) => `${row.requester?.name || "—"} (#${row.requester?.id || "—"})`},
                        {key: "owner", label: "Owner", render: (row) => `${row.owner?.name || "—"} (#${row.owner?.id || "—"})`},
                        {key: "book", label: "Sách", render: (row) => `${row.book?.title || "—"} (#${row.book?.id || "—"})`},
                        {key: "listing", label: "Listing", render: (row) => row.listing ? `${row.listing.type} #${row.listing.id} · ${row.listing.status}` : "—"},
                        {key: "status", label: "Trạng thái"},
                        {key: "created_at", label: "Ngày tạo"},
                    ],
                } : {
                    statuses: borrowStatuses,
                    summary: "borrow",
                    list: (query) => global.AdminAPI.borrowOrders(query),
                    detail: (id) => global.AdminAPI.borrowOrder(id),
                    detailTitle: "Borrow",
                    columns: [
                        {key: "id", label: "ID"},
                        {key: "borrower", label: "Người mượn", render: (row) => `${row.borrower?.name || "—"} (#${row.borrower?.id || "—"})`},
                        {key: "owner", label: "Owner", render: (row) => `${row.owner?.name || "—"} (#${row.owner?.id || "—"})`},
                        {key: "listing", label: "Sách / listing", render: (row) => `${row.listing?.title || row.title || "—"} (#${row.listing?.id || "—"})`},
                        {key: "status", label: "Trạng thái"},
                        {key: "created_at", label: "Ngày tạo"},
                        {key: "shipment", label: "Shipment", render: (row) => formatValue(row.shipment || row.shipments)},
                        {key: "return_status", label: "Trả sách", render: (row) => formatValue(row.return_status || row.return_info)},
                    ],
                };
                await renderRecordSection(section, config, shell, detail);
            } else if (section === "moderation") {
                await renderModeration(shell);
            } else if (section === "users") {
                await renderUsers(shell);
            } else if (section === "reports") {
                await renderReports(shell);
            } else if (section === "analytics") {
                await renderAnalytics(shell);
            } else if (section === "shipping") {
                await renderShipping(shell);
            } else if (section === "commerce") {
                await renderCommerce(shell);
            } else {
                await renderSummary(section, shell);
            }
        }

        nav.addEventListener("click", (event) => {
            const link = event.target.closest("[data-section]");
            if (!link) return;
            event.preventDefault();
            const section = link.dataset.section;
            if (location.hash !== `#${section}`) history.pushState(null, "", `#${section}`);
            renderSection(section);
        });
        global.addEventListener("hashchange", () => renderSection(location.hash.slice(1)));
        const initialSection = location.hash.slice(1) || "overview";
        renderSection(initialSection);
    }

    document.addEventListener("DOMContentLoaded", initialize);
})(window);
