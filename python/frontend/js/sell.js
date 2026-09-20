document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-sell-form]");
    if (!form) return;
    const imageUrlInput = form.querySelector("#book-image-url");
    const previews = form.querySelector("[data-upload-previews]");
    const success = document.querySelector("[data-sell-success]");
    const editing = JSON.parse(localStorage.getItem("editingListing") || "null");
    const setError = (field, message = "") => {
        const target = form.querySelector(`[data-error-for="${field}"]`);
        if (target) target.textContent = message;
    };

    if (!isLoggedIn()) {
        window.location.href = "login.html";
        return;
    }
    if (editing) {
        Object.entries({
            title: editing.title,
            description: editing.description,
            price: editing.price,
            condition: editing.condition_status,
            edition: editing.edition,
            publication_year: editing.publication_year,
            subject_id: editing.subject?.id,
            category_id: editing.category?.id,
            pickup_location_id: editing.pickup_location?.id,
            pickup_note: editing.pickup_note,
        }).forEach(([name, value]) => {
            if (value !== undefined && value !== null && form.elements[name]) form.elements[name].value = value;
        });
    }

    imageUrlInput?.addEventListener("input", () => {
        setError("images");
        previews.innerHTML = imageUrlInput.value.trim()
            ? `<img src="${imageUrlInput.value.trim()}" alt="Ảnh xem trước">`
            : "";
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(form);
        ["title", "subject_id", "price", "condition", "description"].forEach((field) => setError(field));
        const errors = {};
        if (!data.get("title")?.toString().trim()) errors.title = "Tên giáo trình không được để trống.";
        if (!Number(data.get("subject_id"))) errors.subject_id = "Vui lòng chọn môn học.";
        if (!Number(data.get("price")) || Number(data.get("price")) <= 0) errors.price = "Giá phải lớn hơn 0.";
        if (!data.get("condition")) errors.condition = "Vui lòng chọn tình trạng.";
        if (!data.get("description")?.toString().trim()) errors.description = "Mô tả không được để trống.";
        if (!editing && !imageUrlInput?.value.trim()) errors.images = "Vui lòng nhập URL ảnh.";
        Object.entries(errors).forEach(([field, message]) => setError(field, message));
        if (Object.keys(errors).length) return;

        const payload = {
            title: data.get("title").toString().trim(),
            description: data.get("description").toString().trim(),
            price: data.get("price"),
            condition_status: data.get("condition"),
            edition: data.get("edition") || null,
            publication_year: data.get("publication_year") ? Number(data.get("publication_year")) : null,
            subject_id: Number(data.get("subject_id")),
            category_id: data.get("category_id") ? Number(data.get("category_id")) : null,
            pickup_location_id: data.get("pickup_location_id") ? Number(data.get("pickup_location_id")) : null,
            pickup_note: data.get("pickup_note") || "",
        };
        try {
            const book = editing
                ? await api.patch(`/books/${editing.id}/`, payload)
                : await api.post("/books/", payload);
            if (imageUrlInput?.value.trim()) {
                await api.post(`/books/${book.id}/images/`, {
                    image_url: imageUrlInput.value.trim(),
                    is_primary: true,
                    sort_order: 0,
                });
            }
            localStorage.removeItem("editingListing");
            form.hidden = true;
            success.hidden = false;
            showToast(editing ? "Đã cập nhật tin đăng." : "Đăng tin thành công.");
        } catch (error) {
            showToast(error.message);
        }
    });
});
