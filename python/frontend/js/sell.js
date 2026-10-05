document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-sell-form]");
    if (!form) return;
    const imageFileInput = form.querySelector("#book-image-file");
    const submitButton = form.querySelector("button[type='submit']");
    const previews = form.querySelector("[data-upload-previews]");
    const success = document.querySelector("[data-sell-success]");
    const maximumImages = 10;
    const imageEntries = [];
    let editing = null;
    let originalImages = [];
    let imagesReady = Promise.resolve();
    let imageProcessing = Promise.resolve();
    let catalogOptionsReady = false;
    let catalogOptionsPromise = null;
    let isSubmitting = false;
    let subjectOptions = [];

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

    const renderImages = () => {
        previews.replaceChildren();
        imageEntries.forEach((entry, index) => {
            const card = document.createElement("div");
            card.className = "upload-preview";
            const image = document.createElement("img");
            image.alt = `Ảnh xem trước ${index + 1}`;
            image.src = entry.previewUrl || entry.image_url;
            card.append(image);
            const caption = document.createElement("span");
            caption.className = "caption";
            caption.textContent = `${index + 1}. ${entry.is_primary ? "Ảnh chính" : "Ảnh phụ"}`;
            card.append(caption);
            const actions = document.createElement("div");
            actions.className = "upload-preview__actions";
            const makeAction = (label, callback, disabled = false) => {
                const button = document.createElement("button");
                button.className = "button button-outline";
                button.type = "button";
                button.textContent = label;
                button.disabled = disabled;
                button.addEventListener("click", callback);
                actions.append(button);
            };
            makeAction("Ảnh chính", () => {
                imageEntries.forEach((item) => { item.is_primary = false; });
                entry.is_primary = true;
                renderImages();
            }, entry.is_primary);
            makeAction("↑", () => {
                if (index === 0) return;
                [imageEntries[index - 1], imageEntries[index]] =
                    [imageEntries[index], imageEntries[index - 1]];
                renderImages();
            }, index === 0);
            makeAction("↓", () => {
                if (index >= imageEntries.length - 1) return;
                [imageEntries[index], imageEntries[index + 1]] =
                    [imageEntries[index + 1], imageEntries[index]];
                renderImages();
            }, index >= imageEntries.length - 1);
            makeAction("Xóa", () => {
                if (entry.previewUrl) URL.revokeObjectURL(entry.previewUrl);
                imageEntries.splice(index, 1);
                if (imageEntries.length && !imageEntries.some((item) => item.is_primary)) {
                    imageEntries[0].is_primary = true;
                }
                renderImages();
            });
            card.append(actions);
            previews.append(card);
        });
    };

    const transactionType = () => form.elements.listing_type.value || "BUY";
    const updateTransactionFields = () => {
        const selected = transactionType();
        form.querySelectorAll("[data-transaction-fields]").forEach((group) => {
            const visible = group.dataset.transactionFields === selected;
            group.hidden = !visible;
            group.querySelectorAll("input, select, textarea").forEach((field) => {
                field.required = visible && (
                    field.name === "price"
                    || field.name === "rental_fee"
                    || field.name === "max_days"
                    || field.name === "shipping_paid_by"
                    || field.name === "return_method"
                );
            });
        });
    };

    const populateOptions = (select, placeholder, options, formatLabel) => {
        select.replaceChildren(new Option(placeholder, ""));
        options.forEach((option) => {
            select.add(new Option(formatLabel(option), String(option.id)));
        });
    };

    const subjectInput = form.elements.subject_name;
    const subjectIdInput = form.elements.subject_id;
    const subjectDatalist = form.querySelector("#book-subject-options");
    const retryCatalogOptions = form.querySelector("[data-retry-catalog-options]");
    const normalizedSubjectName = (name) => name
        .normalize("NFKC")
        .trim()
        .replace(/\s+/g, " ")
        .toLocaleLowerCase();
    const updateSubjectId = () => {
        const enteredName = normalizedSubjectName(subjectInput.value);
        const matchingSubject = subjectOptions.find(
            (subject) => normalizedSubjectName(subject.name) === enteredName,
        );
        subjectIdInput.value = matchingSubject ? String(matchingSubject.id) : "";
    };
    subjectInput.addEventListener("input", updateSubjectId);

    const loadCatalogOptions = () => {
        if (catalogOptionsPromise) return catalogOptionsPromise;
        catalogOptionsReady = false;
        submitButton.disabled = true;
        retryCatalogOptions.hidden = true;
        catalogOptionsPromise = BooksAPI.options().then((options) => {
            const supportedSlugs = [
                "tieu-thuyet",
                "tho",
                "kich",
                "sach-giao-khoa",
                "giao-trinh",
                "tai-lieu",
                "truyen-tranh",
            ];
            const categoriesBySlug = new Map(
                (Array.isArray(options.categories) ? options.categories : [])
                    .map((category) => [category.slug, category]),
            );
            const categories = supportedSlugs.map((slug) => categoriesBySlug.get(slug));
            if (categories.some((category) => !category || !category.id || !category.name)) {
                throw new Error("Danh mục chưa tải đầy đủ.");
            }
            subjectOptions = Array.isArray(options.subjects)
                ? options.subjects.filter((subject) => subject?.id && subject.name)
                : [];
            subjectDatalist.replaceChildren(...subjectOptions.map((subject) => {
                const option = document.createElement("option");
                option.value = subject.name;
                option.label = subject.code || subject.name;
                return option;
            }));
            populateOptions(
                form.elements.category_id,
                "Chọn danh mục",
                categories,
                (category) => category.name,
            );
            if (editing) {
                subjectInput.value = editing.subject?.name || "";
                form.elements.category_id.value = String(editing.category?.id || "");
                updateSubjectId();
            }
            catalogOptionsReady = true;
            setError("category_id");
            return true;
        }).catch((error) => {
            setError("category_id", "Không thể tải đầy đủ danh mục. Thử lại để tiếp tục.");
            retryCatalogOptions.hidden = false;
            showToast(`Không thể tải danh mục: ${error.message}`);
            return false;
        }).finally(() => {
            catalogOptionsPromise = null;
            submitButton.disabled = !catalogOptionsReady;
        });
        return catalogOptionsPromise;
    };
    retryCatalogOptions.addEventListener("click", () => {
        void loadCatalogOptions();
    });
    submitButton.disabled = true;
    void loadCatalogOptions();

    if (editing) {
        Object.entries({
            title: editing.title,
            description: editing.description,
            listing_type: editing.listing_type || "BUY",
            price: editing.listing_type === "BORROW" ? null : editing.price,
            rental_fee: editing.listing_type === "BORROW"
                ? (editing.rental_fee ?? editing.price)
                : null,
            condition: editing.condition_status,
            edition: editing.edition,
            author: editing.author,
            publisher: editing.publisher,
            isbn: editing.isbn,
            condition_description: editing.condition_description,
            publication_year: editing.publication_year,
            subject_name: editing.subject?.name,
            category_id: editing.category?.id,
        }).forEach(([name, value]) => {
            if (value !== undefined && value !== null && form.elements[name]) {
                form.elements[name].value = value;
            }
        });
        imagesReady = BooksAPI.images(editing.id).then((response) => {
            originalImages = response.images;
            response.images.forEach((image) => imageEntries.push({
                ...image,
                kind: "existing",
                is_primary: Boolean(image.is_primary),
            }));
            renderImages();
        }).catch((error) => {
            setError("images", `Không thể tải ảnh hiện tại: ${error.message}`);
            throw error;
        });
        const terms = editing.borrow_terms || {};
        Object.entries({
            max_days: terms.max_days,
            late_fee_per_day: terms.late_fee_per_day,
            deposit_amount: editing.deposit_amount,
            shipping_paid_by: terms.shipping_paid_by,
            return_method: terms.return_method,
            terms_notes: terms.notes,
        }).forEach(([name, value]) => {
            if (value !== undefined && value !== null && form.elements[name]) {
                form.elements[name].value = value;
            }
        });
    }
    form.querySelectorAll("input[name='listing_type']").forEach((field) =>
        field.addEventListener("change", updateTransactionFields),
    );
    updateTransactionFields();

    const validateImageFile = async (file) => {
        if (!file) return "Vui lòng chọn ảnh.";
        const formats = {
            jpg: {mime: "image/jpeg", bytes: [0xff, 0xd8, 0xff]},
            jpeg: {mime: "image/jpeg", bytes: [0xff, 0xd8, 0xff]},
            png: {mime: "image/png", bytes: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]},
            webp: {mime: "image/webp", bytes: [0x52, 0x49, 0x46, 0x46]},
            gif: {mime: "image/gif", bytes: [0x47, 0x49, 0x46, 0x38]},
        };
        const extension = file.name.split(".").pop()?.toLowerCase();
        const format = formats[extension];
        if (!format || file.type !== format.mime) {
            return "File không phải ảnh hợp lệ. Chỉ chấp nhận JPG, PNG, WebP hoặc GIF.";
        }
        if (file.size > 10 * 1024 * 1024) return "Ảnh không được vượt quá 10 MB.";
        if (file.size === 0) return "File ảnh không được để trống.";
        try {
            const bytes = new Uint8Array(await file.slice(0, 12).arrayBuffer());
            const matchesHeader = format.bytes.every((byte, index) => bytes[index] === byte);
            const matchesWebp = extension !== "webp"
                || String.fromCharCode(...bytes.slice(8, 12)) === "WEBP";
            if (!matchesHeader || !matchesWebp) {
                return "File không phải ảnh hợp lệ hoặc ảnh bị hỏng.";
            }
            const decoded = await createImageBitmap(file);
            const validDimensions = decoded.width > 0 && decoded.height > 0;
            decoded.close();
            return validDimensions ? "" : "File ảnh không hợp lệ.";
        } catch {
            return "File không phải ảnh hợp lệ hoặc ảnh bị hỏng.";
        }
    };

    imageFileInput?.addEventListener("change", () => {
        const selectedFiles = Array.from(imageFileInput.files || []);
        imageFileInput.value = "";
        imageProcessing = imageProcessing.then(async () => {
            setError("images");
            for (const file of selectedFiles) {
                const validationError = await validateImageFile(file);
                if (validationError) {
                    setError("images", validationError);
                    continue;
                }
                if (imageEntries.length >= maximumImages) {
                    setError("images", `Mỗi tin đăng được đăng tối đa ${maximumImages} ảnh.`);
                    break;
                }
                imageEntries.push({
                    kind: "new",
                    file,
                    previewUrl: URL.createObjectURL(file),
                    is_primary: imageEntries.length === 0,
                });
            }
            renderImages();
        }).catch((error) => {
            setError("images", `Không thể xử lý ảnh đã chọn: ${error.message}`);
        });
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (isSubmitting || submitButton.disabled || !catalogOptionsReady) return;
        isSubmitting = true;
        submitButton.disabled = true;
        submitButton.textContent = editing ? "Đang cập nhật..." : "Đang đăng...";
        imageFileInput.disabled = true;
        previews.querySelectorAll("button").forEach((button) => { button.disabled = true; });
        const releaseSubmit = () => {
            isSubmitting = false;
            imageFileInput.disabled = false;
            previews.querySelectorAll("button").forEach((button) => { button.disabled = false; });
            submitButton.disabled = !catalogOptionsReady;
            submitButton.textContent = editing ? "Cập nhật tin" : "Đăng tin";
        };
        try {
            await Promise.all([imagesReady, imageProcessing]);
        } catch (error) {
            showToast(`Không thể tải ảnh hiện tại: ${error.message}`);
            releaseSubmit();
            return;
        }

        const data = new FormData(form);
        [
            "title", "subject_name", "category_id", "price", "rental_fee",
            "max_days", "shipping_paid_by", "return_method", "condition",
            "description",
        ].forEach((field) => setError(field));
        const errors = {};
        const selectedType = transactionType();
        if (!data.get("title")?.toString().trim()) errors.title = "Tên sách không được để trống.";
        if (!data.get("subject_name")?.toString().trim()) {
            errors.subject_name = "Vui lòng nhập môn học.";
        }
        if (!Number(data.get("category_id"))) errors.category_id = "Vui lòng chọn danh mục.";
        if (selectedType === "BUY" && (!Number(data.get("price")) || Number(data.get("price")) <= 0)) {
            errors.price = "Giá bán phải lớn hơn 0.";
        }
        if (selectedType === "BORROW" && (
            data.get("rental_fee") === ""
            || !Number.isFinite(Number(data.get("rental_fee")))
            || Number(data.get("rental_fee")) < 0
        )) {
            errors.rental_fee = "Phí mượn phải là số không âm.";
        }
        if (selectedType === "BORROW" && (!Number.isInteger(Number(data.get("max_days")))
            || Number(data.get("max_days")) < 1)) {
            errors.max_days = "Thời hạn mượn phải ít nhất 1 ngày.";
        }
        if (!data.get("condition")) errors.condition = "Vui lòng chọn tình trạng.";
        if (!data.get("description")?.toString().trim()) errors.description = "Mô tả không được để trống.";
        if (imageEntries.length > maximumImages) {
            errors.images = `Mỗi tin đăng được đăng tối đa ${maximumImages} ảnh.`;
        }
        Object.entries(errors).forEach(([field, message]) => setError(field, message));
        if (Object.keys(errors).length) {
            releaseSubmit();
            return;
        }

        const payload = {
            listing_type: selectedType,
            title: data.get("title").toString().trim(),
            description: data.get("description").toString().trim(),
            condition_status: data.get("condition"),
            edition: data.get("edition") || null,
            author: data.get("author")?.toString().trim() || null,
            publisher: data.get("publisher")?.toString().trim() || null,
            isbn: data.get("isbn")?.toString().trim() || null,
            condition_description: data.get("condition_description")?.toString().trim() || null,
            publication_year: data.get("publication_year") ? Number(data.get("publication_year")) : null,
            category_id: Number(data.get("category_id")),
        };
        if (Number(data.get("subject_id"))) {
            payload.subject_id = Number(data.get("subject_id"));
        } else {
            payload.subject_name = data.get("subject_name").toString().trim();
        }
        if (selectedType === "BUY") {
            payload.price = data.get("price");
        } else {
            payload.rental_fee = data.get("rental_fee");
            payload.max_days = Number(data.get("max_days"));
            payload.deposit_amount = data.get("deposit_amount")
                ? data.get("deposit_amount")
                : null;
            payload.late_fee_per_day = data.get("late_fee_per_day")
                ? data.get("late_fee_per_day")
                : null;
            payload.deposit_required = Boolean(data.get("deposit_required"));
            payload.shipping_paid_by = data.get("shipping_paid_by");
            payload.return_method = data.get("return_method");
            payload.terms_notes = data.get("terms_notes") || "";
        }

        let operation = editing ? "cập nhật tin đăng" : "tạo tin đăng";
        const uploadedImages = [];
        try {
            for (const entry of imageEntries) {
                if (entry.kind === "new") {
                    operation = "tải ảnh lên Cloudinary";
                    submitButton.textContent = `Đang tải ảnh ${uploadedImages.length + 1}...`;
                    const uploaded = await BooksAPI.uploadCloudinary(entry.file);
                    entry.uploaded = uploaded;
                    uploadedImages.push(uploaded);
                }
            }
            const currentUser = PassbookAuth.getCurrentUser() || {};
            payload.images = imageEntries.map((entry, sortOrder) => ({
                ...(entry.kind === "existing" ? {id: entry.id} : {}),
                ...(entry.uploaded || entry),
                sort_order: sortOrder,
                is_primary: Boolean(entry.is_primary),
            }));
            operation = editing ? "lưu ảnh và cập nhật tin" : "tạo tin và lưu ảnh";
            const book = editing
                ? await BooksAPI.update(editing.id, payload)
                : await BooksAPI.create(payload);
            if (editing) {
                const retainedIds = new Set(
                    imageEntries.filter((entry) => entry.kind === "existing")
                        .map((entry) => entry.id),
                );
                const deletedCloudinaryIds = originalImages
                    .filter((image) => !retainedIds.has(image.id))
                    .map((image) => image.cloudinary_public_id)
                    .filter((publicId) => publicId
                        && publicId.startsWith(`user-${currentUser.id}-`));
                if (deletedCloudinaryIds.length) {
                    try {
                        await BooksAPI.cleanupCloudinary(deletedCloudinaryIds);
                    } catch (cleanupError) {
                        showToast(`Ảnh đã được xóa khỏi tin nhưng chưa dọn được trên Cloudinary: ${cleanupError.message}`);
                    }
                }
            }

            localStorage.removeItem("editingListing");
            const detailLink = document.querySelector("[data-sell-detail-link]");
            if (detailLink) {
                detailLink.href = book.listing_type === "BORROW"
                    ? `book-detail.html?id=${book.id}&listing_type=borrow&listing_id=${book.listing_id}`
                    : `book-detail.html?id=${book.id}`;
            }
            form.hidden = true;
            success.hidden = false;
            showToast(editing ? "Đã cập nhật tin đăng." : "Đăng tin thành công.");
        } catch (error) {
            const uploadedPublicIds = uploadedImages
                .map((image) => image.cloudinary_public_id)
                .filter(Boolean);
            if (uploadedPublicIds.length) {
                try {
                    await BooksAPI.cleanupCloudinary(uploadedPublicIds);
                } catch (cleanupError) {
                    showToast(`Không thể dọn ảnh tải lên chưa gắn với tin: ${cleanupError.message}`);
                }
            }
            const fieldErrors = error.payload && typeof error.payload === "object" ? error.payload : {};
            Object.entries(fieldErrors).forEach(([field, message]) => {
                const formField = field === "condition_status" ? "condition" : field;
                setError(formField, Array.isArray(message) ? message.join(" ") : String(message));
            });
            showToast(`Lỗi khi ${operation}: ${error.message}`);
        } finally {
            releaseSubmit();
        }
    });

    document.querySelector("[data-new-listing]")?.addEventListener("click", () => {
        imageEntries.forEach((entry) => {
            if (entry.previewUrl) URL.revokeObjectURL(entry.previewUrl);
        });
        imageEntries.length = 0;
        editing = null;
        originalImages = [];
        imagesReady = Promise.resolve();
        imageProcessing = Promise.resolve();
        localStorage.removeItem("editingListing");
        form.reset();
        updateTransactionFields();
        form.querySelectorAll("[data-error-for]").forEach((element) => { element.textContent = ""; });
        previews.replaceChildren();
        form.hidden = false;
        success.hidden = true;
        submitButton.disabled = !catalogOptionsReady;
        submitButton.textContent = "Đăng tin";
    });
});
