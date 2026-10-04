document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-sell-form]");
    if (!form) return;
    const imageFileInput = form.querySelector("#book-image-file");
    const submitButton = form.querySelector("button[type='submit']");
    const previews = form.querySelector("[data-upload-previews]");
    const success = document.querySelector("[data-sell-success]");
    let previewUrls = [];
    let editing = null;

    try {
        editing = JSON.parse(localStorage.getItem("editingListing") || "null");
    } catch (error) {
        console.error("Failed to parse editingListing:", error);
    }

    const setError = (field, message = "") => {
        const target = form.querySelector(`[data-error-for="${field}"]`);
        if (target) target.textContent = message;
    };

    if (!PassbookGuards.requireAuth()) return;

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
        }).forEach(([name, value]) => {
            if (value !== undefined && value !== null && form.elements[name]) {
                form.elements[name].value = value;
            }
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
        previewUrls.forEach((url) => URL.revokeObjectURL(url));
        previewUrls = [];
        previews.replaceChildren();
        Array.from(imageFileInput.files || []).forEach((file) => {
            const validationError = validateImageFile(file);
            if (validationError) {
                setError("images", validationError);
                return;
            }
            const url = URL.createObjectURL(file);
            previewUrls.push(url);
            const preview = document.createElement("img");
            preview.alt = "Ảnh xem trước";
            preview.src = url;
            previews.append(preview);
        });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (submitButton.disabled) return;

        const data = new FormData(form);
        ["title", "subject_id", "price", "condition", "description"].forEach((field) => setError(field));
        const errors = {};
        if (!data.get("title")?.toString().trim()) errors.title = "Tên giáo trình không được để trống.";
        if (!Number(data.get("subject_id"))) errors.subject_id = "Vui lòng chọn môn học.";
        if (!Number(data.get("price")) || Number(data.get("price")) <= 0) errors.price = "Giá phải lớn hơn 0.";
        if (!data.get("condition")) errors.condition = "Vui lòng chọn tình trạng.";
        if (!data.get("description")?.toString().trim()) errors.description = "Mô tả không được để trống.";
        const imageFiles = Array.from(imageFileInput?.files || []);
        if (!editing && imageFiles.length === 0) {
            errors.images = "Vui lòng chọn ít nhất một ảnh.";
        }
        const invalidImage = imageFiles.map(validateImageFile).find(Boolean);
        if (invalidImage) errors.images = invalidImage;
        Object.entries(errors).forEach(([field, message]) => setError(field, message));
        if (Object.keys(errors).length) return;

        submitButton.disabled = true;
        submitButton.textContent = editing ? "Đang cập nhật..." : "Đang đăng...";
        const payload = {
            title: data.get("title").toString().trim(),
            description: data.get("description").toString().trim(),
            price: data.get("price"),
            condition_status: data.get("condition"),
            edition: data.get("edition") || null,
            publication_year: data.get("publication_year") ? Number(data.get("publication_year")) : null,
            subject_id: Number(data.get("subject_id")),
            category_id: data.get("category_id") ? Number(data.get("category_id")) : null,
        };

        let operation = editing ? "cập nhật tin đăng" : "tạo tin đăng";
        let createdBook = null;
        try {
            const book = editing
                ? await BooksAPI.update(editing.id, payload)
                : await BooksAPI.create(payload);
            if (!editing) createdBook = book;
            if (imageFiles.length) {
                operation = "lấy chữ ký Cloudinary";
                submitButton.textContent = "Đang tải ảnh...";
                const signature = await BooksAPI.cloudinarySignature();
                for (const [index, imageFile] of imageFiles.entries()) {
                    operation = "tải ảnh lên và lưu liên kết ảnh";
                    await BooksAPI.uploadImage(book.id, imageFile, {
                        signature,
                        isPrimary: index === 0,
                        sortOrder: index,
                    });
                }
            }

            localStorage.removeItem("editingListing");
            form.hidden = true;
            success.hidden = false;
            showToast(editing ? "Đã cập nhật tin đăng." : "Đăng tin thành công.");
        } catch (error) {
            if (createdBook) {
                editing = createdBook;
                localStorage.setItem("editingListing", JSON.stringify(createdBook));
            }
            const fieldErrors = error.payload && typeof error.payload === "object" ? error.payload : {};
            Object.entries(fieldErrors).forEach(([field, message]) => {
                const formField = field === "condition_status" ? "condition" : field;
                setError(formField, Array.isArray(message) ? message.join(" ") : String(message));
            });
            showToast(
                createdBook
                    ? `Tin đã tạo nhưng lỗi khi ${operation}. Đã lưu bản chỉnh sửa để bạn có thể tải ảnh/thử lại: ${error.message}`
                    : `Lỗi khi ${operation}: ${error.message}`,
            );
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = editing ? "Cập nhật tin" : "Đăng tin";
        }
    });

    document.querySelector("[data-new-listing]")?.addEventListener("click", () => {
        previewUrls.forEach((url) => URL.revokeObjectURL(url));
        previewUrls = [];
        editing = null;
        localStorage.removeItem("editingListing");
        form.reset();
        form.querySelectorAll("[data-error-for]").forEach((element) => { element.textContent = ""; });
        previews.replaceChildren();
        form.hidden = false;
        success.hidden = true;
        submitButton.disabled = false;
        submitButton.textContent = "Đăng tin";
    });
});
