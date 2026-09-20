document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-sell-form]");
    if (!form) return;
    const imageFileInput = form.querySelector("#book-image-file");
    const submitButton = form.querySelector("button[type='submit']");
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

    const validateImageFile = (file) => {
        if (!file) return "Vui lòng chọn ảnh.";
        const allowedTypes = ["image/jpeg", "image/png", "image/webp", "image/gif"];
        if (!allowedTypes.includes(file.type)) return "Chỉ chấp nhận ảnh JPG, PNG, WebP hoặc GIF.";
        if (file.size > 10 * 1024 * 1024) return "Ảnh không được vượt quá 10 MB.";
        return "";
    };

    imageFileInput?.addEventListener("change", () => {
        setError("images");
        const file = imageFileInput.files[0];
        previews.innerHTML = file
            ? `<img src="${URL.createObjectURL(file)}" alt="Ảnh xem trước">`
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
        const imageFile = imageFileInput?.files[0];
        if (!editing) {
            const imageError = validateImageFile(imageFile);
            if (imageError) errors.images = imageError;
        }
        Object.entries(errors).forEach(([field, message]) => setError(field, message));
        if (Object.keys(errors).length) return;

        submitButton.disabled = true;
        submitButton.textContent = "Đang đăng...";
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
            if (imageFile) {
                submitButton.textContent = "Đang tải ảnh...";
                const signatureData = await api.get("/uploads/cloudinary/signature/");
                const uploadData = new FormData();
                uploadData.append("file", imageFile);
                uploadData.append("api_key", signatureData.api_key);
                uploadData.append("timestamp", signatureData.timestamp);
                uploadData.append("folder", signatureData.folder);
                uploadData.append("signature", signatureData.signature);
                const uploadResponse = await fetch(
                    `https://api.cloudinary.com/v1_1/${encodeURIComponent(signatureData.cloud_name)}/image/upload`,
                    {method: "POST", body: uploadData},
                );
                const uploadedImage = await uploadResponse.json();
                if (!uploadResponse.ok || !uploadedImage.secure_url) {
                    throw new Error(uploadedImage.error?.message || "Không thể tải ảnh lên Cloudinary.");
                }
                await api.post(`/books/${book.id}/images/`, {
                    image_url: uploadedImage.secure_url,
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
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = "Đăng tin";
        }
    });
});
