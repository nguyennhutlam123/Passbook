document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-payment-simulator]");
    if (!page || !PassbookGuards.requireRole("ADMIN")) return;
    const apiHost = new URL(API_BASE_URL).hostname;
    const localApi = ["localhost", "127.0.0.1"].includes(apiHost);
    const error = page.querySelector("[data-fake-payment-error]");
    const forms = [
        {
            form: page.querySelector("[data-fake-payment-form]"),
            idName: "payment_id",
            request: (id, status) => PaymentsAPI.fakeTransition(id, status),
        },
        {
            form: page.querySelector("[data-fake-refund-form]"),
            idName: "refund_id",
            request: (id, status) => PaymentsAPI.fakeRefundTransition(id, status),
        },
    ];
    if (!localApi) {
        forms.forEach(({form}) => {
            form.hidden = true;
        });
        error.textContent = "Payment simulation bị khóa vì API không chạy trên localhost.";
        return;
    }
    forms.forEach(({form, idName, request}) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const id = form.elements[idName].value.trim();
            const status = form.elements.status.value;
            const submit = form.querySelector("button[type=submit]");
            submit.disabled = true;
            error.textContent = "";
            try {
                await request(id, status);
                showToast(`Đã gửi trạng thái mô phỏng ${status}.`);
            } catch (requestError) {
                error.textContent = requestError.message;
            } finally {
                submit.disabled = false;
            }
        });
    });
});
