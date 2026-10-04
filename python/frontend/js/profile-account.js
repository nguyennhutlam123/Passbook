document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-profile-page]");
    if (!page || !PassbookGuards.requireAuth()) return;
    const profileForm = page.querySelector("[data-profile-form]");
    const passwordForm = page.querySelector("[data-password-form]");
    const addressForm = page.querySelector("[data-address-form]");
    const addressList = page.querySelector("[data-address-list]");
    let addressPage = 1;

    const loadProfile = async () => {
        try {
            const profile = await AuthAPI.profile();
            profileForm.elements.name.value = profile.name || "";
            profileForm.elements.avatar.value = profile.avatar || "";
            page.querySelector("[data-profile-name]").firstChild.textContent = `${profile.name || "Người dùng"} `;
            page.querySelector("[data-profile-school]").textContent = profile.university?.name || profile.email || "";
            page.querySelector("[data-profile-student-id]").textContent = profile.email || "—";
            page.querySelector(".profile-avatar").textContent =
                (profile.name || "NG").slice(0, 2).toUpperCase();
            PassbookAuth.updateUser({...PassbookAuth.getCurrentUser(), ...profile});
        } catch (error) {
            showToast(error.message);
        }
    };

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
            const controls = Array.isArray(data) ? null : PassbookCommonComponents.pagination({
                previous: data.previous,
                next: data.next,
                onPrevious: () => { addressPage = Math.max(1, addressPage - 1); void loadAddresses(); },
                onNext: () => { addressPage += 1; void loadAddresses(); },
            });
            if (!nodes.length) nodes.push(PassbookCommonComponents.emptyState("Chưa lưu địa chỉ giao hàng."));
            if (controls) nodes.push(controls);
            addressList.replaceChildren(...nodes);
        } catch (error) {
            addressList.replaceChildren(PassbookCommonComponents.emptyState(error.message));
        }
    };

    profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submit = profileForm.querySelector("button[type=submit]");
        submit.disabled = true;
        try {
            const profile = await AuthAPI.updateProfile({
                name: profileForm.elements.name.value.trim(),
                avatar: profileForm.elements.avatar.value.trim() || null,
            });
            PassbookAuth.updateUser({...PassbookAuth.getCurrentUser(), ...profile});
            await loadProfile();
            showToast("Đã cập nhật hồ sơ.");
        } catch (error) {
            showToast(error.message);
        } finally {
            submit.disabled = false;
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
