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
        verified.setAttribute("aria-label", user.is_verified ? "Đã xác minh" : "Chưa xác minh");
        verified.title = user.is_verified ? "Đã xác minh" : "Chưa xác minh";
    }
    const reportList = document.querySelector("[data-report-list]");
    try {
        const reports = await ReportsAPI.mine({page_size: 50});
        reportList.innerHTML = reports.results?.length ? reports.results.map((report) => `<article class="report-item"><strong>${escapeHtml(report.reason)}</strong><span>Sách #${report.book_id || "—"} · ${escapeHtml(report.status)}</span><time>${new Date(report.created_at).toLocaleString("vi-VN")}</time></article>`).join("") : '<p class="caption">Chưa có báo cáo.</p>';
    } catch (error) {
        reportList.innerHTML = `<p class="caption">${escapeHtml(error.message)}</p>`;
    }
});
