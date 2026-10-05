document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.querySelector("[data-login-form]");
    const registerForm = document.querySelector("[data-register-form]");
    const registerOtpForm = document.querySelector("[data-register-otp-form]");
    const forgotPasswordForm = document.querySelector("[data-forgot-password-form]");
    const forgotOtpForm = document.querySelector("[data-forgot-otp-form]");
    const resetPasswordForm = document.querySelector("[data-reset-password-form]");
    const registerSuccess = document.querySelector("[data-register-success]");
    let pendingRegistrationEmail = "";
    let pendingResetTarget = "";
    const otpTimers = new WeakMap();
    const formatRemaining = (seconds) => {
        const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
        const remainder = (seconds % 60).toString().padStart(2, "0");
        return `${minutes}:${remainder}`;
    };
    const stopOtpTimer = (form) => {
        const timer = otpTimers.get(form);
        if (timer) window.clearInterval(timer);
        otpTimers.delete(form);
    };
    const startOtpTimer = (form, response = {}) => {
        stopOtpTimer(form);
        const now = Date.now();
        const expiresAt = now + (Number(response.otp_expires_in_seconds) || 300) * 1000;
        const resendAt = now + (Number(response.otp_resend_after_seconds) || 60) * 1000;
        const timerLabel = form.querySelector("[data-otp-expiry]");
        const resendButton = form.querySelector("button[data-register-resend], button[data-forgot-resend]");
        const update = () => {
            const currentTime = Date.now();
            const expiresIn = Math.max(0, Math.ceil((expiresAt - currentTime) / 1000));
            const resendIn = Math.max(0, Math.ceil((resendAt - currentTime) / 1000));
            if (timerLabel) {
                timerLabel.textContent = expiresIn > 0
                    ? `Mã hết hạn sau ${formatRemaining(expiresIn)}${resendIn > 0 ? ` · gửi lại sau ${formatRemaining(resendIn)}` : ""}.`
                    : "Mã đã hết hạn. Hãy gửi lại mã để tiếp tục.";
            }
            if (resendButton) resendButton.disabled = resendIn > 0;
        };
        update();
        otpTimers.set(form, window.setInterval(update, 1000));
    };
    const beginSubmit = (form) => {
        if (form.dataset.pending === "true") return null;
        const button = form.querySelector("button[type='submit']");
        if (!button) return null;
        form.dataset.pending = "true";
        const label = button.textContent;
        button.disabled = true;
        button.textContent = "Đang xử lý...";
        return () => {
            form.dataset.pending = "false";
            button.disabled = false;
            button.textContent = label;
        };
    };
    const setErrors = (form, errors) => {
        form.querySelectorAll("[data-error-for]").forEach((element) => { element.textContent = ""; });
        Object.entries(errors).forEach(([field, message]) => {
            const target = form.querySelector(`[data-error-for="${field}"]`);
            if (target) target.textContent = Array.isArray(message) ? message.join(" ") : String(message);
        });
    };
    loginForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(loginForm);
        const identifier = data.get("email")?.toString().trim() || "";
        const errors = {};
        if (!identifier.includes("@") && !/^\+?[0-9 ()-]{7,30}$/.test(identifier)) errors.email = "Nhập email hoặc số điện thoại hợp lệ.";
        if (identifier.includes("@") && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(identifier)) errors.email = "Email không hợp lệ.";
        if (!data.get("password")) errors.password = "Vui lòng nhập mật khẩu.";
        setErrors(loginForm, errors);
        if (Object.keys(errors).length) return;
        const finish = beginSubmit(loginForm);
        if (!finish) return;
        try {
            const credentials = identifier.includes("@")
                ? {email: identifier.toLowerCase(), password: data.get("password")}
                : {phone: identifier, password: data.get("password")};
            await AuthAPI.login(credentials);
            PassbookRouter.redirectAfterLogin("index.html");
        } catch (error) {
            setErrors(loginForm, PassbookErrors.fieldErrors(error));
            showToast(error.payload?.detail || error.message);
        } finally {
            finish();
        }
    });

    registerForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(registerForm);
        const errors = {};
        if (!data.get("name")?.toString().trim()) errors.name = "Họ tên không được để trống.";
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.get("email"))) errors.email = "Email không hợp lệ.";
        if (data.get("password")?.toString().length < 8) errors.password = "Mật khẩu cần ít nhất 8 ký tự.";
        if (data.get("password") !== data.get("confirmPassword")) errors.confirmPassword = "Mật khẩu xác nhận không khớp.";
        setErrors(registerForm, errors);
        if (Object.keys(errors).length) return;
        const finish = beginSubmit(registerForm);
        if (!finish) return;
        try {
            const result = await AuthAPI.register({
                name: data.get("name"),
                email: data.get("email"),
                phone: data.get("phone")?.toString().trim() || "",
                password: data.get("password"),
            });
            pendingRegistrationEmail = data.get("email").toString().trim().toLowerCase();
            registerForm.hidden = true;
            registerOtpForm.hidden = false;
            registerOtpForm.querySelector("[data-register-otp-target]").textContent = pendingRegistrationEmail;
            startOtpTimer(registerOtpForm, result);
        } catch (error) {
            setErrors(registerForm, error.payload || {form: error.message});
            if (error.payload?.detail) showToast(error.payload.detail);
        } finally {
            finish();
        }
    });

    registerOtpForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(registerOtpForm);
        const otp = data.get("otp")?.toString().trim() || "";
        setErrors(registerOtpForm, {});
        if (!/^\d{6}$/.test(otp)) {
            setErrors(registerOtpForm, {otp: "Nhập mã gồm 6 chữ số."});
            return;
        }
        const finish = beginSubmit(registerOtpForm);
        if (!finish) return;
        try {
            await AuthAPI.verifyOtp({
                target: pendingRegistrationEmail,
                purpose: "REGISTER",
                otp,
            });
            stopOtpTimer(registerOtpForm);
            registerOtpForm.hidden = true;
            registerSuccess.hidden = false;
            document.querySelector(".auth-switch")?.setAttribute("hidden", "");
        } catch (error) {
            setErrors(registerOtpForm, error.payload || {otp: error.message});
            showToast(error.message);
        } finally {
            finish();
        }
    });

    registerOtpForm?.querySelector("[data-register-resend]")?.addEventListener("click", async () => {
        const button = registerOtpForm.querySelector("[data-register-resend]");
        if (button.disabled) return;
        button.disabled = true;
        try {
            const result = await AuthAPI.resendOtp({
                target: pendingRegistrationEmail,
                purpose: "REGISTER",
            });
            startOtpTimer(registerOtpForm, result);
            showToast("Nếu tài khoản cần xác minh, mã mới sẽ được gửi.");
        } catch (error) {
            button.disabled = false;
            showToast(error.message);
        }
    });

    document.querySelector("[data-forgot-toggle]")?.addEventListener("click", (event) => {
        event.preventDefault();
        loginForm.hidden = true;
        forgotPasswordForm.hidden = false;
    });

    forgotPasswordForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const target = new FormData(forgotPasswordForm).get("target")?.toString().trim() || "";
        setErrors(forgotPasswordForm, {});
        if (!target) {
            setErrors(forgotPasswordForm, {target: "Nhập email hoặc số điện thoại."});
            return;
        }
        const finish = beginSubmit(forgotPasswordForm);
        if (!finish) return;
        try {
            const result = await AuthAPI.forgotPassword({target});
            pendingResetTarget = target;
            forgotPasswordForm.hidden = true;
            forgotOtpForm.hidden = false;
            startOtpTimer(forgotOtpForm, result);
            showToast("Nếu tài khoản tồn tại, mã xác minh sẽ được gửi.");
        } catch (error) {
            setErrors(forgotPasswordForm, error.payload || {target: error.message});
        } finally {
            finish();
        }
    });

    forgotOtpForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const otp = new FormData(forgotOtpForm).get("otp")?.toString().trim() || "";
        if (!/^\d{6}$/.test(otp)) {
            setErrors(forgotOtpForm, {otp: "Nhập mã gồm 6 chữ số."});
            return;
        }
        const finish = beginSubmit(forgotOtpForm);
        if (!finish) return;
        try {
            const result = await AuthAPI.verifyOtp({
                target: pendingResetTarget,
                purpose: "FORGOT_PASSWORD",
                otp,
            });
            resetPasswordForm.elements.reset_token.value = result.reset_token;
            forgotOtpForm.hidden = true;
            resetPasswordForm.hidden = false;
        } catch (error) {
            setErrors(forgotOtpForm, error.payload || {otp: error.message});
            showToast(error.message);
        } finally {
            finish();
        }
    });

    forgotOtpForm?.querySelector("[data-forgot-resend]")?.addEventListener("click", async () => {
        const button = forgotOtpForm.querySelector("[data-forgot-resend]");
        if (button.disabled) return;
        button.disabled = true;
        try {
            const result = await AuthAPI.resendOtp({
                target: pendingResetTarget,
                purpose: "FORGOT_PASSWORD",
            });
            startOtpTimer(forgotOtpForm, result);
            showToast("Nếu tài khoản tồn tại, mã mới sẽ được gửi.");
        } catch (error) {
            button.disabled = false;
            showToast(error.message);
        }
    });

    resetPasswordForm?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(resetPasswordForm);
        const password = data.get("new_password")?.toString() || "";
        if (password.length < 8 || password !== data.get("confirm_password")) {
            setErrors(resetPasswordForm, {
                new_password: password.length < 8
                    ? "Mật khẩu cần ít nhất 8 ký tự."
                    : "Mật khẩu xác nhận không khớp.",
            });
            return;
        }
        const finish = beginSubmit(resetPasswordForm);
        if (!finish) return;
        try {
            await AuthAPI.resetPassword({
                reset_token: data.get("reset_token"),
                new_password: password,
            });
            window.location.href = "login.html";
        } catch (error) {
            setErrors(resetPasswordForm, error.payload || {new_password: error.message});
            showToast(error.message);
        } finally {
            finish();
        }
    });
});
