document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-profile-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const profileForm = page.querySelector("[data-profile-form]");
    const passwordForm = page.querySelector("[data-password-form]");
    const addressForm = page.querySelector("[data-address-form]");
    const addressList = page.querySelector("[data-address-list]");
    const avatarInput = profileForm.elements.avatar_file;
    const avatarMessage = page.querySelector("[data-avatar-message]");
    let selectedAvatarFile = null;
    let selectedAvatarPreviewUrl = null;
    let savedAvatarUrl = null;
    let addressPage = 1;

    const applyProfile = (profile) => {
        const profileName = profile.name || "Người dùng mới";
        profileForm.elements.name.value = profile.name || "";
        savedAvatarUrl = profile.avatar || null;
        page.querySelector("[data-profile-name]").textContent = profileName;
        const accountRole = page.querySelector("[data-profile-role]");
        if (accountRole) {
            accountRole.textContent = String(profile.role || "student").toLowerCase() === "admin"
                ? "Quản trị viên"
                : "Tài khoản cá nhân";
        }
        page.querySelector("[data-profile-school]").textContent = profile.university?.name || "Chưa cập nhật trường học";
        page.querySelector("[data-profile-email]").textContent = profile.email || "Chưa cập nhật email";
        page.querySelector("[data-profile-phone]").textContent = profile.phone || "Chưa cập nhật số điện thoại";
        const accountStatus = page.querySelector("[data-profile-status]");
        const statusLabels = {
            active: "Đang hoạt động",
            pending_verification: "Chờ xác thực",
            blocked: "Đã khóa",
        };
        if (accountStatus) {
            const status = String(profile.status || "active").toLowerCase();
            accountStatus.textContent = statusLabels[status] || status;
            accountStatus.classList.toggle("profile-badge--active", status === "active");
        }
        if (!selectedAvatarFile) setAvatarPreview(savedAvatarUrl, profileName);
        PassbookAuth.updateUser({...PassbookAuth.getCurrentUser(), ...profile});
    };

    const renderAvatar = (container, name, imageUrl) => {
        container.replaceChildren();
        if (imageUrl) {
            const image = document.createElement("img");
            image.src = imageUrl;
            image.alt = "";
            image.addEventListener("error", () => {
                container.textContent = (name || "NG").slice(0, 2).toUpperCase();
            }, {once: true});
            container.append(image);
        } else {
            container.textContent = (name || "NG").slice(0, 2).toUpperCase();
        }
    };

    const setAvatarPreview = (imageUrl, name) => {
        renderAvatar(page.querySelector("[data-profile-avatar]"), name, imageUrl);
        renderAvatar(page.querySelector("[data-avatar-picker-preview]"), name, imageUrl);
    };

    const loadProfile = async () => {
        try {
            let profile = {};
            const demoMode = new URL(window.location.href).searchParams.get("demo") === "1";
            if (demoMode || globalThis.localStorage.getItem("demoProfile") === "true") {
                profile = {
                    id: "demo-profile",
                    name: "Nguyễn Lâm",
                    email: "lam.passbook@gmail.com",
                    university: {name: "HCMUE"},
                    avatar: "",
                    bio: "Khám phá sách hay, kết nối cộng đồng và quản lý tài khoản một cách tiện lợi.",
                    is_verified: true,
                };
                globalThis.localStorage.setItem("demoProfile", "true");
            } else {
                profile = await AuthAPI.profile();
            }
            applyProfile(profile);
        } catch (error) {
            showToast(error.message);
        }
    };

    avatarInput.addEventListener("change", () => {
        const file = avatarInput.files?.[0] || null;
        avatarMessage.textContent = "";
        avatarMessage.classList.remove("is-error");
        if (selectedAvatarPreviewUrl) {
            URL.revokeObjectURL(selectedAvatarPreviewUrl);
            selectedAvatarPreviewUrl = null;
        }
        if (!file) {
            selectedAvatarFile = null;
            setAvatarPreview(savedAvatarUrl, profileForm.elements.name.value);
            return;
        }
        const allowedTypes = ["image/jpeg", "image/png", "image/webp", "image/gif"];
        if (!allowedTypes.includes(file.type)) {
            avatarInput.value = "";
            selectedAvatarFile = null;
            setAvatarPreview(savedAvatarUrl, profileForm.elements.name.value);
            avatarMessage.textContent = "Vui lòng chọn ảnh JPG, PNG, WebP hoặc GIF.";
            avatarMessage.classList.add("is-error");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            avatarInput.value = "";
            selectedAvatarFile = null;
            setAvatarPreview(savedAvatarUrl, profileForm.elements.name.value);
            avatarMessage.textContent = "Ảnh đại diện phải có dung lượng tối đa 10 MB.";
            avatarMessage.classList.add("is-error");
            return;
        }
        selectedAvatarFile = file;
        selectedAvatarPreviewUrl = URL.createObjectURL(file);
        setAvatarPreview(selectedAvatarPreviewUrl, profileForm.elements.name.value);
        avatarMessage.textContent = file.name;
    });

    const loadAddresses = async () => {
        try {
            const data = await UsersAPI.addresses({page: addressPage, page_size: 10});
            const addresses = Array.isArray(data) ? data : data.results || [];
            const nodes = addresses.map((address) => {
                const card = document.createElement("article");
                card.className = "report-item";
                const details = document.createElement("span");
                details.textContent = `${address.recipient_name} · ${address.phone} · ${address.address_line}, ${address.ward}, ${address.district}, ${address.city}${address.is_default ? " · Mặc định" : ""}`;
                const edit = document.createElement("button");
                edit.className = "button button-outline";
                edit.type = "button";
                edit.textContent = "Sửa";
                edit.addEventListener("click", () => {
                    for (const [name, value] of Object.entries(address)) {
                        if (addressForm.elements[name]?.type === "checkbox") {
                            addressForm.elements[name].checked = Boolean(value);
                        } else if (addressForm.elements[name]) {
                            addressForm.elements[name].value = value ?? "";
                        }
                    }
                    addressForm.scrollIntoView({behavior: "smooth", block: "start"});
                });
                const remove = document.createElement("button");
                remove.className = "button button-outline";
                remove.type = "button";
                remove.textContent = "Xóa";
                remove.addEventListener("click", async () => {
                    if (!PassbookCommonComponents.confirmAction("Xóa địa chỉ này?")) return;
                    remove.disabled = true;
                    try {
                        await UsersAPI.deleteAddress(address.id);
                        await loadAddresses();
                    } catch (error) {
                        showToast(error.message);
                    } finally {
                        remove.disabled = false;
                    }
                });
                card.append(details, edit, remove);
                return card;
            });
            const controls = !addresses.length || Array.isArray(data)
                ? null
                : PassbookCommonComponents.pagination({
                    previous: data.previous,
                    next: data.next,
                    onPrevious: () => {
                        addressPage = Math.max(1, addressPage - 1);
                        void loadAddresses();
                    },
                    onNext: () => {
                        addressPage += 1;
                        void loadAddresses();
                    },
                });
            if (controls) nodes.push(controls);
            addressList.classList.toggle("report-list", addresses.length > 0);
            page.querySelector("[data-address-grid]").classList.toggle(
                "has-addresses",
                addresses.length > 0,
            );
            addressList.replaceChildren(...nodes);
        } catch (error) {
            addressList.classList.remove("report-list");
            page.querySelector("[data-address-grid]").classList.remove("has-addresses");
            const message = document.createElement("p");
            message.className = "form-error";
            message.textContent = error.message;
            addressList.replaceChildren(message);
        }
    };

    profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submit = profileForm.querySelector("button[type=submit]");
        submit.disabled = true;
        let uploadedAvatar = null;
        try {
            if (selectedAvatarFile) {
                submit.textContent = "Đang tải ảnh...";
                uploadedAvatar = await BooksAPI.uploadCloudinary(selectedAvatarFile);
            }
            submit.textContent = "Đang lưu...";
            const payload = {name: profileForm.elements.name.value.trim()};
            if (uploadedAvatar) payload.avatar = uploadedAvatar.image_url;
            const profile = await AuthAPI.updateProfile(payload);
            savedAvatarUrl = profile.avatar || null;
            selectedAvatarFile = null;
            avatarInput.value = "";
            if (selectedAvatarPreviewUrl) {
                URL.revokeObjectURL(selectedAvatarPreviewUrl);
                selectedAvatarPreviewUrl = null;
            }
            avatarMessage.textContent = "";
            applyProfile(profile);
            showToast("Đã cập nhật hồ sơ.");
        } catch (error) {
            if (uploadedAvatar?.cloudinary_public_id) {
                try {
                    await BooksAPI.cleanupCloudinary([uploadedAvatar.cloudinary_public_id]);
                } catch (cleanupError) {
                    showToast(
                        `${error.message} Ảnh tải lên chưa được dọn khỏi Cloudinary: ${cleanupError.message}`,
                    );
                    return;
                }
            }
            showToast(error.message);
        } finally {
            submit.disabled = false;
            submit.textContent = "Lưu thay đổi";
        }
    });

    passwordForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submit = passwordForm.querySelector("button[type=submit]");
        submit.disabled = true;
        try {
            await AuthAPI.changePassword({
                old_password: passwordForm.elements.old_password.value,
                new_password: passwordForm.elements.new_password.value,
            });
            passwordForm.reset();
            showToast("Đã đổi mật khẩu.");
        } catch (error) {
            showToast(error.message);
        } finally {
            submit.disabled = false;
        }
    });

    page.querySelectorAll("[data-contact-form]").forEach((form) => {
        const channel = form.dataset.contactForm;
        const valueInput = form.elements[channel];
        const otpInput = form.elements.otp;
        const otpFields = form.querySelector("[data-contact-otp]");
        const message = form.querySelector("[data-contact-message]");
        const submit = form.querySelector("button[type=submit]");
        const cancel = form.querySelector("[data-contact-cancel]");
        form.dataset.stage = "request";

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (!form.reportValidity()) return;
            submit.disabled = true;
            message.textContent = "";
            try {
                if (form.dataset.stage === "request") {
                    const target = valueInput.value.trim();
                    await AuthAPI.requestContactChange(channel, {[channel]: target});
                    form.dataset.target = target;
                    form.dataset.stage = "verify";
                    valueInput.readOnly = true;
                    otpFields.hidden = false;
                    otpInput.required = true;
                    cancel.hidden = false;
                    submit.textContent = "Xác minh và cập nhật";
                    otpInput.focus();
                    message.textContent = "Mã xác minh đã được gửi. Mã có hiệu lực trong thời gian giới hạn.";
                    return;
                }

                await AuthAPI.verifyOtp({
                    target: form.dataset.target,
                    purpose: channel === "email" ? "CHANGE_EMAIL" : "CHANGE_PHONE",
                    otp: otpInput.value.trim(),
                });
                const profile = await AuthAPI.profile();
                applyProfile(profile);
                form.dataset.stage = "request";
                delete form.dataset.target;
                valueInput.value = "";
                valueInput.readOnly = false;
                otpFields.hidden = true;
                otpInput.required = false;
                otpInput.value = "";
                cancel.hidden = true;
                submit.textContent = "Gửi mã xác minh";
                message.textContent = "";
                showToast(channel === "email"
                    ? "Đã xác minh và cập nhật email."
                    : "Đã xác minh và cập nhật số điện thoại.");
            } catch (error) {
                showToast(error.message);
                message.textContent = error.message;
            } finally {
                submit.disabled = false;
            }
        });

        cancel.addEventListener("click", () => {
            form.dataset.stage = "request";
            delete form.dataset.target;
            valueInput.value = "";
            valueInput.readOnly = false;
            otpFields.hidden = true;
            otpInput.required = false;
            otpInput.value = "";
            cancel.hidden = true;
            submit.textContent = "Gửi mã xác minh";
            message.textContent = "";
        });
    });

    addressForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!addressForm.reportValidity()) return;
        const formData = new FormData(addressForm);
        const id = formData.get("id").toString();
        const payload = Object.fromEntries(
            ["recipient_name", "phone", "address_line", "ward", "district", "city", "postal_code"]
                .map((name) => [name, formData.get(name).toString().trim()]),
        );
        payload.is_default = formData.has("is_default");
        const submit = addressForm.querySelector("button[type=submit]");
        submit.disabled = true;
        try {
            if (id) await UsersAPI.updateAddress(id, payload);
            else {
                await UsersAPI.createAddress(payload);
                addressPage = 1;
            }
            addressForm.reset();
            await loadAddresses();
            showToast("Đã lưu địa chỉ.");
        } catch (error) {
            showToast(error.message);
        } finally {
            submit.disabled = false;
        }
    });
    addressForm.querySelector("[data-address-reset]").addEventListener("click", () => {
        addressForm.elements.id.value = "";
    });

    void Promise.all([loadProfile(), loadAddresses()]);
});
