(function (global) {
    "use strict";

    class ApiError extends Error {
        constructor(message, {status = 0, payload = null, code = "api_error"} = {}) {
            super(message);
            this.name = "ApiError";
            this.status = status;
            this.payload = payload;
            this.code = code;
        }
    }

    function messageFor(error) {
        const status = Number(error?.status || 0);
        const payload = error?.payload;
        if (status === 0) {
            return error?.code === "timeout"
                ? "Yêu cầu mất quá nhiều thời gian. Vui lòng thử lại."
                : "Không thể kết nối máy chủ. Kiểm tra kết nối mạng và thử lại.";
        }
        if (status === 401) return "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.";
        if (status === 403) return "Bạn không có quyền thực hiện thao tác này.";
        if (status === 404) return "Không tìm thấy dữ liệu yêu cầu.";
        if (status === 409) return "Dữ liệu vừa thay đổi. Tải lại và thử lại.";
        if (status === 422) return "Một số thông tin chưa hợp lệ.";
        if (status === 429) return "Bạn thao tác quá nhanh. Vui lòng đợi rồi thử lại.";
        if (status >= 500) return "Máy chủ đang gặp sự cố. Vui lòng thử lại sau.";

        if (payload && typeof payload === "object") {
            const detail = payload.detail || payload.message;
            if (typeof detail === "string") return detail;
            const firstField = Object.values(payload).find((value) =>
                typeof value === "string" || Array.isArray(value)
            );
            if (Array.isArray(firstField) && typeof firstField[0] === "string") {
                return firstField[0];
            }
            if (typeof firstField === "string") return firstField;
        }
        return error?.message || "Đã xảy ra lỗi. Vui lòng thử lại.";
    }

    function fieldErrors(error) {
        const payload = error?.payload;
        if (!payload || typeof payload !== "object") return {};
        return Object.fromEntries(
            Object.entries(payload).map(([field, value]) => [
                field,
                Array.isArray(value) ? value.map(String).join(" ") : String(value),
            ]),
        );
    }

    global.PassbookErrors = Object.freeze({ApiError, messageFor, fieldErrors});
})(window);
