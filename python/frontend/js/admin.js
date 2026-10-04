document.addEventListener("DOMContentLoaded", () => {
    const dashboard = document.querySelector("[data-admin-dashboard]");
    if (!dashboard || !PassbookGuards.requireRole("ADMIN")) return;

    const metrics = dashboard.querySelector("[data-admin-metrics]");
    const reports = dashboard.querySelector("[data-admin-reports]");
    const filter = dashboard.querySelector("[data-report-filter]");
    const errorElement = dashboard.querySelector("[data-admin-error]");
    let reportPage = 1;

    const metric = (label, value, detail = "") => {
        const card = document.createElement("article");
        card.className = "report-item admin-metric";
        const title = document.createElement("span");
        title.textContent = label;
        const count = document.createElement("strong");
        count.textContent = typeof value === "number"
            ? value.toLocaleString("vi-VN")
            : String(value || 0);
        card.append(title, count);
        if (detail) {
            const caption = document.createElement("small");
            caption.textContent = detail;
            card.append(caption);
        }
        return card;
    };

    const loadDashboard = async () => {
        if (metrics.hidden) return;
        metrics.replaceChildren();
        const loading = document.createElement("p");
        loading.className = "loading-state";
        loading.textContent = "Đang tải thống kê...";
        metrics.append(loading);
        try {
            const data = await AdminAPI.dashboard();
            const cards = [
                metric("Người dùng", data.users?.total, `${data.users?.active || 0} hoạt động · ${data.users?.locked || 0} khóa`),
                metric("Tin đăng", data.listings?.total, `${data.listings?.active || 0} đang bán · ${data.listings?.sold || 0} đã bán · ${data.listings?.pending || 0} chờ · ${data.listings?.rejected || 0} từ chối`),
                metric("Tin cho mượn", data.lend_listings?.total, `${data.lend_listings?.active || 0} đang hoạt động · ${data.lend_listings?.on_loan || 0} đang cho mượn`),
                metric("Đặt giữ", data.reservations?.total, `${data.reservations?.pending || 0} chờ · ${data.reservations?.confirmed || 0} xác nhận`),
                metric("Giỏ hàng", data.carts?.total, `${data.carts?.active || 0} đang hoạt động`),
                metric("Đơn hàng", data.orders?.total, `${data.orders?.pending || 0} chờ thanh toán · ${data.orders?.completed || 0} hoàn tất`),
                metric("Thanh toán", data.payments?.total, `${data.payments?.paid || 0} thành công · ${data.payments?.failed || 0} thất bại`),
                metric("Trả hàng / hoàn tiền", `${data.returns?.total || 0} / ${data.refunds?.total || 0}`, `${data.returns?.requested || 0} yêu cầu trả · ${data.refunds?.requested || 0} yêu cầu hoàn`),
                metric("Vận chuyển", data.shipments?.total, `${data.shipments?.shipped || 0} đã gửi · ${data.shipments?.delivered || 0} đã giao`),
                metric("Báo cáo", data.reports?.total, `${data.reports?.open || 0} đang mở · ${data.reports?.in_review || 0} đang xem xét`),
                metric("Hội thoại / tin nhắn", `${data.conversations || 0} / ${data.messages || 0}`),
                metric("Lượt yêu thích", data.favorites),
            ];
            metrics.replaceChildren(...cards);
            errorElement.textContent = "";
        } catch (error) {
            metrics.replaceChildren();
            errorElement.textContent = error.message;
        }
    };

    const makeSelect = (value) => {
        const select = document.createElement("select");
        select.className = "form-control";
        select.setAttribute("aria-label", "Trạng thái báo cáo");
        [
            ["OPEN", "Mới"],
            ["IN_REVIEW", "Đang xem xét"],
            ["RESOLVED", "Đã xử lý"],
            ["REJECTED", "Từ chối"],
        ].forEach(([optionValue, label]) => {
            const option = document.createElement("option");
            option.value = optionValue;
            option.textContent = label;
            option.selected = value === optionValue;
            select.append(option);
        });
        return select;
    };

    const renderReport = (report) => {
        const card = document.createElement("article");
        card.className = "report-item";
        const title = document.createElement("strong");
        title.textContent = report.reason || "Báo cáo";
        const metadata = document.createElement("span");
        metadata.textContent = `#${report.id} · Sách #${report.book_id || "—"} · ${report.status}`;
        const description = document.createElement("p");
        description.textContent = report.description || "Không có mô tả.";
        const note = document.createElement("textarea");
        note.className = "form-control";
        note.maxLength = 5000;
        note.value = report.resolution_note || "";
        note.placeholder = "Ghi chú xử lý";
        note.setAttribute("aria-label", "Ghi chú xử lý");
        const status = makeSelect(report.status);
        const save = document.createElement("button");
        save.className = "button button-primary";
        save.type = "button";
        save.textContent = "Lưu xử lý";
        save.addEventListener("click", async () => {
            save.disabled = true;
            try {
                await AdminAPI.updateReport(report.id, {
                    status: status.value,
                    resolution_note: note.value,
                });
                await Promise.all([loadReports(), loadDashboard()]);
            } catch (error) {
                showToast(error.message);
            } finally {
                save.disabled = false;
            }
        });
        card.append(title, metadata, description, status, note, save);
        return card;
    };

    const loadReports = async () => {
        reports.replaceChildren();
        const loading = document.createElement("p");
        loading.className = "loading-state";
        loading.textContent = "Đang tải báo cáo...";
        reports.append(loading);
        try {
            const data = await AdminAPI.reports({
                page: reportPage,
                page_size: 50,
                status: filter.value,
            });
            const nodes = (data.results || []).map(renderReport);
            if (!nodes.length) {
                const empty = document.createElement("p");
                empty.className = "caption";
                empty.textContent = "Không có báo cáo.";
                nodes.push(empty);
            }
            if (data.previous || data.next) {
                const pagination = document.createElement("div");
                pagination.className = "modal-actions";
                if (data.previous) {
                    const previous = document.createElement("button");
                    previous.className = "button button-outline";
                    previous.type = "button";
                    previous.textContent = "Trước";
                    previous.addEventListener("click", () => {
                        reportPage = Math.max(1, reportPage - 1);
                        loadReports();
                    });
                    pagination.append(previous);
                }
                if (data.next) {
                    const next = document.createElement("button");
                    next.className = "button button-outline";
                    next.type = "button";
                    next.textContent = "Sau";
                    next.addEventListener("click", () => {
                        reportPage += 1;
                        loadReports();
                    });
                    pagination.append(next);
                }
                nodes.push(pagination);
            }
            reports.replaceChildren(...nodes);
        } catch (error) {
            reports.replaceChildren();
            const message = document.createElement("p");
            message.className = "form-error";
            message.textContent = error.message;
            reports.append(message);
        }
    };

    filter.addEventListener("change", () => {
        reportPage = 1;
        loadReports();
    });
    void loadDashboard();
    void loadReports();
});
