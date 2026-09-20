document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.querySelector("[data-login-form]");
    const registerForm = document.querySelector("[data-register-form]");
    const setErrors = (form, errors) => {
        form.querySelectorAll("[data-error-for]").forEach((element) => { element.textContent = ""; });
        Object.entries(errors).forEach(([field, message]) => {
            const target = form.querySelector(`[data-error-for="${field}"]`);
            if (target) target.textContent = Array.isArray(message) ? message.join(" ") : message;
        });
    };

    loginForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(loginForm);
        const errors = {};
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.get("email"))) errors.email = "Email không hợp lệ.";
        if (!data.get("password")) errors.password = "Vui lòng nhập mật khẩu.";
        setErrors(loginForm, errors);
        if (Object.keys(errors).length) return;
        try {
            const result = await api.post("/auth/login/", {email: data.get("email"), password: data.get("password")});
            localStorage.setItem("accessToken", result.access);
            localStorage.setItem("refreshToken", result.refresh);
            localStorage.setItem("currentUser", JSON.stringify(result.user));
            localStorage.setItem("isLoggedIn", "true");
            window.location.href = "index.html";
        } catch (error) {
            setErrors(loginForm, error.payload || {form: error.message});
            if (error.payload?.detail) showToast(error.payload.detail);
        }
    });

    registerForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(registerForm);
        const errors = {};
        if (!data.get("name")?.toString().trim()) errors.name = "Họ tên không được để trống.";
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.get("email"))) errors.email = "Email không hợp lệ.";
        if (!data.get("university_id")) errors.university_id = "Vui lòng chọn trường.";
        if (data.get("password")?.toString().length < 8) errors.password = "Mật khẩu cần ít nhất 8 ký tự.";
        if (data.get("password") !== data.get("confirmPassword")) errors.confirmPassword = "Mật khẩu xác nhận không khớp.";
        setErrors(registerForm, errors);
        if (Object.keys(errors).length) return;
        try {
            await api.post("/auth/register/", {
                name: data.get("name"),
                email: data.get("email"),
                password: data.get("password"),
                university_id: Number(data.get("university_id")),
            });
            window.location.href = "login.html";
        } catch (error) {
            setErrors(registerForm, error.payload || {form: error.message});
            if (error.payload?.detail) showToast(error.payload.detail);
        }
    });
});
