(function (global) {
    "use strict";

    const client = global.api;
    const idPath = (id) => encodeURIComponent(id);
    global.BooksAPI = Object.freeze({
        options: () => client.get("/catalog/options/"),
        list: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/books/", query)),
        get: (bookId) => client.get(`/books/${idPath(bookId)}/`),
        intentSummary: (bookId) => client.get(`/books/${idPath(bookId)}/intents/`),
        setIntent: (bookId, requestType) =>
            client.post(`/books/${idPath(bookId)}/intents/`, {request_type: requestType}),
        cancelIntent: (bookId, requestType) =>
            client.delete(`/books/${idPath(bookId)}/intents/`, {
                body: JSON.stringify({request_type: requestType}),
                headers: {"Content-Type": "application/json"},
            }),
        create: (data) => client.post("/books/", data),
        update: (bookId, data) => client.patch(`/books/${idPath(bookId)}/`, data),
        delete: (bookId) => client.delete(`/books/${idPath(bookId)}/`),
        markSold: (bookId) => client.patch(`/books/${idPath(bookId)}/sold/`, {}),
        mine: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/my-books/", query)),
        listings: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/sale-listings/", query)),
        lendListings: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/lend-listings/", query)),
        lendListing: (listingId) =>
            client.get(`/lend-listings/${idPath(listingId)}/`),
        createListing: (data) => client.post("/sale-listings/", data),
        listing: (listingId) => client.get(`/sale-listings/${idPath(listingId)}/`),
        updateListing: (listingId, data) =>
            client.patch(`/sale-listings/${idPath(listingId)}/`, data),
        deleteListing: (listingId) => client.delete(`/sale-listings/${idPath(listingId)}/`),
        images: (bookId) => client.get(`/books/${idPath(bookId)}/images/`),
        addImage: (bookId, data) => client.post(`/books/${idPath(bookId)}/images/`, data),
        updateImage: (bookId, imageId, data) =>
            client.patch(`/books/${idPath(bookId)}/images/${idPath(imageId)}/`, data),
        deleteImage: (bookId, imageId) =>
            client.delete(`/books/${idPath(bookId)}/images/${idPath(imageId)}/`),
        cloudinarySignature: () => client.get("/uploads/cloudinary/signature/"),
        cleanupCloudinary: (publicIds) =>
            client.post("/uploads/cloudinary/cleanup/", {public_ids: publicIds}),
        uploadCloudinary: async (file) => {
            const signature = await client.get("/uploads/cloudinary/signature/");
            const body = new FormData();
            body.append("file", file);
            body.append("api_key", signature.api_key);
            body.append("timestamp", signature.timestamp);
            body.append("asset_folder", signature.asset_folder);
            body.append("public_id", signature.public_id);
            body.append("signature", signature.signature);
            const uploaded = await client.request(
                `https://api.cloudinary.com/v1_1/${encodeURIComponent(signature.cloud_name)}/image/upload`,
                {method: "POST", body, auth: false},
            );
            if (!uploaded?.secure_url || !/^https:\/\//i.test(uploaded.secure_url)) {
                throw new global.PassbookErrors.ApiError(
                    "Cloudinary không trả về secure URL hợp lệ.",
                    {status: 502, code: "invalid_upload_response"},
                );
            }
            return {
                image_url: uploaded.secure_url,
                cloudinary_public_id: uploaded.public_id || signature.public_id,
            };
        },
        uploadImage: async (bookId, file, options = {}) => {
            const uploaded = await global.BooksAPI.uploadCloudinary(file);
            return global.BooksAPI.addImage(bookId, {
                ...uploaded,
                is_primary: Boolean(options.isPrimary),
                sort_order: Number(options.sortOrder) || 0,
            });
        },
        requests: (query = {}) =>
            client.get(global.PassbookApiUtils.withQuery("/book-requests/", query)),
        createRequest: (data) => client.post("/book-requests/", data),
        updateRequest: (requestId, data) =>
            client.patch(`/book-requests/${idPath(requestId)}/`, data),
        deleteRequest: (requestId) => client.delete(`/book-requests/${idPath(requestId)}/`),
        requestMatches: (requestId) =>
            client.get(`/book-requests/${idPath(requestId)}/matches/`),
        requestInterests: (requestId, data) =>
            client.post(`/book-requests/${idPath(requestId)}/interests/`, data),
        requestInterestsList: (requestId) =>
            client.get(`/book-requests/${idPath(requestId)}/interests/`),
        removeRequestInterest: (requestId) =>
            client.delete(`/book-requests/${idPath(requestId)}/interests/`),
    });
})(window);
