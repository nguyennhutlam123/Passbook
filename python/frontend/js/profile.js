document.addEventListener("DOMContentLoaded", async () => {
    if (!document.querySelector("[data-profile-page]")) return;
    if (!PassbookGuards.requireAuth()) return;
    const user = PassbookAuth.getCurrentUser() || {
        name: "Nguyễn Lâm",
        email: "lam.passbook@gmail.com",
        university: {name: "HCMUE"},
        is_verified: true,
    };
    document.querySelector("[data-profile-name]").textContent = user.name || "Người dùng";
    document.querySelector("[data-profile-school]").textContent = user.university?.name || user.email || "";
    const verified = document.querySelector(".verified");
    if (verified) {
        verified.hidden = !user.is_verified;
        verified.setAttribute("aria-label", "Tài khoản xác thực");
        verified.removeAttribute("title");
    }
    const reportList = document.querySelector("[data-report-list]");
    try {
        const reports = await ReportsAPI.mine({page_size: 50});
        const reasonLabels = {
            INAPPROPRIATE_CONTENT: "Nội dung không phù hợp",
            INCORRECT_BOOK_INFO: "Thông tin sách sai",
            SPAM: "Spam",
            SCAM: "Lừa đảo",
            POLICY_VIOLATION: "Vi phạm chính sách",
            OTHER: "Lý do khác",
        };
        const statusLabels = {
            pending: "Đang chờ xử lý",
            reviewing: "Đang xem xét",
            resolved: "Đã xử lý",
            rejected: "Đã từ chối",
        };
        const targets = (report) => [
            report.book_id && `Sách #${report.book_id}`,
            report.sale_listing_id && `Tin bán #${report.sale_listing_id}`,
            report.lend_listing_id && `Tin cho mượn #${report.lend_listing_id}`,
            report.reported_user_id && `Tài khoản #${report.reported_user_id}`,
            report.message_id && `Tin nhắn #${report.message_id}`,
        ].filter(Boolean).join(" · ") || "Đối tượng không còn khả dụng";
        const nodes = (reports.results || []).map((report) => {
            const item = document.createElement("article");
            item.className = "report-item";
            const title = document.createElement("strong");
            title.textContent = reasonLabels[report.reason] || report.reason;
            const target = document.createElement("span");
            target.textContent = targets(report);
            const status = document.createElement("span");
            status.textContent = statusLabels[report.status] || report.status;
            const created = document.createElement("time");
            created.dateTime = report.created_at || "";
            created.textContent = report.created_at
                ? new Date(report.created_at).toLocaleString("vi-VN")
                : "";
            item.append(title, target, status, created);
            return item;
        });
        reportList.replaceChildren(...(nodes.length
            ? nodes
            : [Object.assign(document.createElement("p"), {
                className: "caption",
                textContent: "Chưa có báo cáo.",
            })]));
    } catch (error) {
        reportList.innerHTML = `<p class="caption">${escapeHtml(error.message)}</p>`;
    }
});
