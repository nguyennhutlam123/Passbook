# Passbook v1.2 Lite – Django Audit

## 1. Schema

The Lite DDL defines 41 tables. All 41 have an unmanaged Django model with an
explicit `db_table`; every non-generated DDL column is represented by a model
field. `otp_verifications` is the new 41st table and its SQL DDL remains the
source of truth. The full non-Lite v1.2 DDL was not modified. The Lite DDL
was updated to add sale-listing moderation states without changing table or
column counts:

- [`passbook_v1.2_lite.sql`](./passbook_v1.2_lite.sql)
- [`passbook_v1.2.sql`](./passbook_v1.2.sql)

The Lite DDL uses `utf8mb4_unicode_ci` for XAMPP/MariaDB compatibility. The
local verification target is XAMPP database `passbook_v12_lite_test` on
MariaDB 10.4.28.

Django 4.2 cannot express composite primary keys or generated columns as model
fields. Generated columns remain DDL-owned. The `BookWorkSubject` and
`ConversationMember` mappings use one FK as the ORM primary key and therefore
produce Django `fields.W342` warnings; their actual composite keys remain
enforced by MySQL. Their Admin CRUD is implemented with a composite-key-aware
admin base that identifies and updates/deletes rows using both key columns.
Ordinary ORM lookups that assume the first FK is unique must still include both
key columns.

## 2. Model Mapping

| Django Model | Lite Table | Status |
|---|---|---|
| University | `universities` | MODIFY |
| Faculty | `faculties` | CREATE MODEL |
| Major | `majors` | CREATE MODEL |
| User | `users` | MODIFY |
| OtpVerification | `otp_verifications` | CREATE MODEL |
| UserAddress | `user_addresses` | CREATE MODEL |
| UserViolation | `user_violations` | CREATE MODEL |
| Subject | `subjects` | MODIFY |
| Language | `languages` | CREATE MODEL |
| Category | `categories` | MODIFY |
| BookWork | `book_works` | CREATE MODEL |
| BookWorkSubject | `book_work_subjects` | CREATE MODEL |
| BookEdition | `book_editions` | CREATE MODEL |
| BookIdentifier | `book_identifiers` | CREATE MODEL |
| Book | `books` | MODIFY |
| BookImage | `book_images` | MODIFY |
| SaleListing | `sale_listings` | CREATE MODEL |
| LendListing | `lend_listings` | CREATE MODEL |
| BorrowTerms | `borrow_terms` | CREATE MODEL |
| BookRequest | `book_requests` | CREATE MODEL |
| RequestInterest | `request_interests` | CREATE MODEL |
| RequestMatch | `request_matches` | CREATE MODEL |
| Cart | `carts` | CREATE MODEL |
| CartItem | `cart_items` | CREATE MODEL |
| CheckoutGroup | `checkout_groups` | CREATE MODEL |
| Order | `orders` | CREATE MODEL |
| SaleOrderItem | `sale_order_items` | CREATE MODEL |
| BorrowOrder | `borrow_orders` | CREATE MODEL |
| Payment | `payments` | CREATE MODEL |
| Shipment | `shipments` | CREATE MODEL |
| ShipmentTracking | `shipment_tracking` | CREATE MODEL |
| Return | `returns` | CREATE MODEL |
| Refund | `refunds` | CREATE MODEL |
| Favorite | `favorites` | MODIFY |
| Conversation | `conversations` | MODIFY |
| ConversationMember | `conversation_members` | CREATE MODEL |
| Message | `messages` | MODIFY |
| Notification | `notifications` | MODIFY |
| Review | `reviews` | CREATE MODEL |
| Report | `reports` | MODIFY |
| BookReservation | `book_reservations` | CREATE MODEL |

The former `Location` model/table has no Lite counterpart and was removed.
Registration/profile compatibility is mapped from legacy `name`/`avatar` to
`full_name`/`avatar_url`; the schema has no `is_verified` column, so the
compatibility property reports true only when account status is `ACTIVE`.
`Subject` no longer has a `university_id`.

## 3. Modified Files

- [`books/models.py`](../../python/backend/books/models.py), [`books/serializers.py`](../../python/backend/books/serializers.py), [`books/api_views.py`](../../python/backend/books/api_views.py): map physical books through works, editions, and listings; retain list/detail/image/favorite API shapes and pagination.
- [`books/commerce_api_views.py`](../../python/backend/books/commerce_api_views.py), [`books/services.py`](../../python/backend/books/services.py): add separate reservation, lending, cart/checkout, order, payment-intent, shipment/tracking, return/refund-request, review, and lifecycle endpoints/services.
- [`books/sale_api_views.py`](../../python/backend/books/sale_api_views.py), [`books/request_api_views.py`](../../python/backend/books/request_api_views.py): add moderated sale-listing CRUD/search and book-request, interest, and BUY/SELL_INTENT/BORROW matching APIs.
- [`books/tests.py`](../../python/backend/books/tests.py): schema mapping and fee/input tests.
- [`config/api_urls.py`](../../python/backend/config/api_urls.py): wire new endpoints.
- [`config/settings.py`](../../python/backend/config/settings.py): configure OTP limits, SMTP/SMS adapters, and `PASSBOOK_PLATFORM_FEE_RATE`; no credentials were added.
- [`config/composite_admin.py`](../../python/backend/config/composite_admin.py): row-safe Django Admin CRUD for Lite's two composite-key tables.
- [`users/management/commands/seed_lite_acceptance_data.py`](../../python/backend/users/management/commands/seed_lite_acceptance_data.py), [`users/management/commands/run_lite_acceptance.py`](../../python/backend/users/management/commands/run_lite_acceptance.py): guarded synthetic fixture and repeatable local database acceptance.
- [`users/otp_api_views.py`](../../python/backend/users/otp_api_views.py), [`users/services/otp.py`](../../python/backend/users/services/otp.py): separate OTP issue/delivery/verification from auth views, with hashed storage and attempt/resend limits.
- [`users/models.py`](../../python/backend/users/models.py), [`users/serializers.py`](../../python/backend/users/serializers.py), [`users/api_views.py`](../../python/backend/users/api_views.py), [`users/authentication.py`](../../python/backend/users/authentication.py): map Lite user and address fields while preserving auth response aliases.
- [`messaging/models.py`](../../python/backend/messaging/models.py), [`messaging/serializers.py`](../../python/backend/messaging/serializers.py), [`messaging/api_views.py`](../../python/backend/messaging/api_views.py): use conversation membership and Lite message timestamps.
- [`notifications/models.py`](../../python/backend/notifications/models.py), [`notifications/serializers.py`](../../python/backend/notifications/serializers.py): map notification/entity fields to the existing response names.
- [`reports/models.py`](../../python/backend/reports/models.py), [`reports/serializers.py`](../../python/backend/reports/serializers.py), [`reports/api_views.py`](../../python/backend/reports/api_views.py): support Lite polymorphic report targets and validate exactly one target.
- [`users/management/commands/seed_demo_data.py`](../../python/backend/users/management/commands/seed_demo_data.py): update the generic demo-data command to create Lite-shaped records; final acceptance used the separate guarded `seed_lite_acceptance_data` command.
- State-only unmanaged initial migrations are under `books`, `messaging`, `notifications`, `reports`, and `users`. They record `OtpVerification` for Django model-state checks, but no migration was applied and Django does not create Lite tables.

Frontend auth now verifies registration and supports password reset; sell
supports multiple images. Obsolete pickup-location controls/references were
removed from the frontend. No references to the 18 Lite-removed financial,
verification, combo, coupon, or notification-delivery tables remain under
`python/backend`.

### Backend architecture

Models remain schema mappings (`managed = False`) and do not contain workflow
logic. Serializers validate input; views retain existing app-level API modules.
OTP delivery, hashing and verification are isolated in `users/services/otp.py`.
Sale-listing and book-request endpoints are isolated from the legacy book API.
Reservation and borrow transitions are in `books/services.py`; routing is
centralized in `config/api_urls.py`. Checkout and much of the commerce
workflow still live in a large API-view module, and authorization is not yet
consistently extracted into reusable permission classes.

## 4. Endpoint Compatibility

Existing frontend calls were inventoried in `js/api.js`, `js/auth.js`,
`js/books.js`, `js/book-detail.js`, `js/sell.js`, `js/profile.js`, and
`js/main.js`. Existing auth, `/books/`, book detail, image, favorite, messaging,
notification, report, and Cloudinary-signature routes remain wired. List APIs
retain DRF pagination envelopes and the book page-size cap.

The book list uses `Exists` subqueries for subject/search matches rather than
join-driven `DISTINCT`; images, seller/university, edition/work/category,
primary subject, and listings are selected/prefetched for serialization.
Substring `LIKE`/`icontains` search remains functionally compatible but is not
made index-fast by a B-tree. Full-text search was not introduced.

The former `pickup_location_id` filter/write input is explicitly rejected when
non-empty for legacy clients, and the response alias `pickup_location` remains
`null`. Frontend controls and query parameters have been removed because Lite
has no locations table or replacement field.

### API changes

- Added paginated `/sale-listings/` list/create and `/sale-listings/<id>/`
  read/update/soft-close routes. `/books/` remains compatible with existing
  frontend create/edit/image flows.
- Added book-request CRUD, interest and paginated BUY/SELL_INTENT/BORROW matching
  routes; added mark-all-read for notifications.
- Existing cart supports add/remove/view and revalidates listing state/price at
  checkout. Cart-item selection is not available in the schema.
- Search/filter/sort runs in SQL; no FULLTEXT index or API response rewrite was
  introduced. Sale and lend listing routes have pagination and relevant filters.

### KEEP / MODIFY / DELETE / CREATE

| Action | Scope |
|---|---|
| KEEP | Existing book, image, favorite, chat, notification, report, address, and commerce flows where their schema mappings remain valid. |
| MODIFY | User registration/status, login by email or phone, profile contact writes, lightweight list images, pagination, search/filter/sort, and legacy pickup-location compatibility. |
| DELETE | Frontend pickup-location controls/query dependencies; no tables or backend module were deleted solely for not having direct callers. |
| CREATE | `otp_verifications` DDL/model/service/admin/endpoints; sale-listing CRUD; book-request/interest/matching endpoints; notification mark-all-read. |

### OTP architecture and API

Six-digit OTPs are generated with `secrets`, stored only as Django password
hashes, and delivered through Django email or a configured SMS callable. Defaults
are five-minute expiry, five failed attempts, 60-second resend cooldown, five
resends per one-hour window, and a ten-minute signed password-reset token.
Issuing a replacement expires the previous pending row. Verification is locked
and one-time; OTP values are write-only, never returned in API responses, and
are not logged. Registration creates a `PENDING_VERIFICATION` user; successful
REGISTER verification activates it.

| Purpose | Support |
|---|---|
| REGISTER | Email OTP required before account activation. |
| LOGIN | Optional second-factor challenge after correct password; not enforced by default for backward compatibility. |
| FORGOT_PASSWORD | Generic initiation response; successful verification returns a short-lived signed reset token. |
| CHANGE_EMAIL / CHANGE_PHONE | Authenticated request and verification endpoints; profile serializer cannot directly change contact fields. |

Endpoints: `POST /auth/verify-otp/`, `POST /auth/resend-otp/`,
`POST /auth/forgot-password/`, `POST /auth/reset-password/`,
`POST /auth/change-email/request/`, and `POST /auth/change-phone/request/`.
Email/SMS delivery is not configured in this workspace, so live delivery was
not tested; the API returns an explicit service-unavailable response when a
delivery backend is missing or fails.

## Security

Passwords continue to use Django's password hashers. OTPs use cryptographic
random generation and password-hash verification, are never included in API
responses/admin fields/log messages, and reset tokens are signed, expire, and
consume the verified OTP row on reset. Registration/login state, contact-change
ownership, listing ownership, order roles, and request ownership are checked.
Forgot-password initiation returns the same response for known/unknown targets.
No OTP-specific per-IP throttling is configured.

The security acceptance tests now cover book/listing ownership, request
ownership, address ownership, order/payment/refund/return roles, reservation
and borrow-order actor checks, conversation membership, notification scoping,
report ownership/admin authorization, anonymous access to protected APIs, and
server-controlled payment/order fields. A reservation transition previously
performed expiry mutations before checking the actor; authorization now
precedes all state changes. Notification reads now scope the lookup to the
current user, avoiding an object-existence distinction for another user's
notification ID. These tests use mocks and assert that unauthorized paths do
not call write operations; they do not replace database-backed integration
tests.

## Performance

Book and listing endpoints preserve pagination with a 50-item maximum.
`/api/books/` uses a compact serializer with listing fields, minimal
subject/category/seller data, and one primary image; it omits long descriptions
and limits selected columns and related joins. Sale-listing list responses omit
descriptions and limit selected columns. Conversation and message lists,
addresses, reservation lists, and request-interest lists are paginated;
conversation membership filtering uses `Exists` instead of an avoidable join.
Expired sale/lend listings are filtered in the database before cart, checkout,
reservation, and request-match lookups. Search still uses `%keyword%` and may
scan data. Initial empty-database smoke measurements are superseded by the
populated local measurements in section 9.

## 5. Workflow Status

| Area | Result | Notes |
|---|---|---|
| Authentication / OTP | PASS (local acceptance) | Database-backed probes cover register, login, invalid password, token expiry/refresh/logout revocation, lock status, OTP expiry/attempt/resend limits, verification and password reset. Local email backend used; SMTP/SMS delivery remains an external configuration. Login OTP is optional. |
| Books and sale listings | PASS (local acceptance) | Database-backed listing/search/filter/sort/detail/pagination, seller update/denial and large-fixture probes pass. |
| Book images | PASS (local acceptance) | HTTPS image-record create/update/delete and ownership checks pass. This does not upload to Cloudinary; external credentials are not configured. |
| Book requests | PASS (local acceptance) | BUY/SELL_INTENT request matches and BUY/BORROW listing matches persist and return in both request directions; request-interest create/retry passes. |
| Reservation | PASS (local acceptance) | Reserve/cancel, invalid transition and two-user race probes pass; only one concurrent reservation wins. |
| Borrowing | PASS (local acceptance) | Database-backed payment, confirmation, ready, active, return-requested, returned and completed transitions pass; invalid repeat transition rejected. |
| Cart and orders | PASS (local acceptance) | Cart checkout, duplicate checkout idempotency, order cancellation and invalid repeat cancellation pass. Concurrent checkout returns one checkout group/orders. Lite has no quantity column, so cart items represent one listing each. |
| Payment / platform fee | PASS (local simulation) | Fake Provider intent, retry, success/failure/cancel, invalid transition, and refund failure/completion/retry exercise database state. Simulation is disabled outside `PASSBOOK_ENVIRONMENT=local|test`; no production provider/webhook exists. |
| Shipment / tracking | PASS (local acceptance) | Fake-paid sale order advances through shipment creation, shipped, in-transit and delivered before return/refund. |
| Chat | PASS (local acceptance) | Membership-authorized conversations and paginated messages are exercised. Lite `conversations` has no book/order target FK, so book context is `null` after conversation creation. |
| Notifications | PASS (local acceptance) | Database-backed list and read operations pass. |
| Favorites | PASS (local acceptance) | Create/idempotent retry/delete and 500-book performance query pass. |
| Reviews | PASS (local acceptance) | Review upsert on eligible completed order passes. |
| Reports | PASS (local acceptance) | Report create/idempotent retry and Admin report visibility pass. |

Return requests and seller approve/reject/complete actions are wired. Refunds
can be requested idempotently against a paid payment and one sale/borrow/return
target; the local/test Fake Provider can complete/fail a refund and marks a
payment `REFUNDED` once cumulative completed refunds reach the payment amount.
The acceptance runner verifies these transitions against MariaDB. Django
Admin is registered for all 41 Lite tables, including live add/edit/delete on
both composite-key relationship tables. OTP metadata is read-only, and its
hash is deferred/not displayed.

## 6. Removed Dependencies

Search of `python/backend` found no references to:

`financial_transactions`, `financial_transaction_events`,
`seller_payout_accounts`, `seller_payouts`, `seller_payout_adjustments`,
`seller_payout_adjustment_allocations`, `payment_allocations`, `platform_fees`,
`sale_combos`, `sale_combo_items`, `sale_combo_order_items`, `coupons`,
`coupon_listings`, `coupon_categories`, `coupon_usages`, `book_verifications`,
`verification_evidences`, or `notification_deliveries`.

## 7. Checks

- [x] 41 Lite DDL tables map to 41 Django model tables.
- [x] All non-generated DDL columns and nullability match Django model columns; primary keys match except the two documented composite-key mappings.
- [x] The three DDL ENUM fields match Django choices.
- [x] Static DDL checks: one `otp_verifications`, all three required indexes, nullable `user_id` FK to `users` with `SET NULL`/`CASCADE`, no database create/drop or FLOAT/DOUBLE.
- [x] Every Lite model is unmanaged; no migration was applied.
- [x] No Aiven connection. The authorized Lite schema changes add
  `PENDING`/`REJECTED` listing states and nullable
  `request_matches.matched_request_id` with its index/FK; the 41-table count
  is unchanged. Synthetic data was written only to local XAMPP; see section 9.
- [x] `python3 manage.py check` — exit 0; emits two documented `fields.W342` warnings for composite-key mappings.
- [x] `python3 manage.py makemigrations --check --dry-run` — `No changes detected`; no migration was generated.
- [x] Targeted security acceptance selection — 30 tests passed, including
  ownership/role checks, anonymous denial, server-controlled payment fields,
  and no-write assertions on unauthorized paths.
- [x] `python manage.py test` — latest full test count is recorded in section 14.
- [x] `python3 -m compileall -q python/backend` — pass.
- [x] `git diff --check` — pass.

- [x] Connection to XAMPP `passbook_v12_lite_test` verified
  `SELECT DATABASE(), VERSION()` as `passbook_v12_lite_test`,
  `10.4.28-MariaDB`; no schema or data was changed.
- [x] Live table names match the 41 Lite DDL tables. The 90 foreign-key
  constraints match the DDL. All 182 explicitly declared indexes are present;
  MariaDB also exposes one automatically created foreign-key support index on
  `book_reservations(book_id)`. The database has 41 primary keys and 37 unique
  constraints, matching the DDL. The 60 declared CHECK constraints are
  present; MariaDB reports five additional JSON-validity checks for JSON
  columns.
- [x] Initial empty-database `EXPLAIN` and smoke checks were run; section 9
  supersedes their measurements with the populated local fixture.

No Aiven endpoint was used. The search uses substring `LIKE`/`icontains`
patterns; ordinary B-tree indexes do not accelerate leading-wildcard searches.
No FULLTEXT index was added because multilingual search compatibility and
behavior have not been validated.

## 8. Scope and External Integrations

The local/test acceptance is complete; the following are explicit deployment
or schema boundaries, not untested local acceptance failures:

1. No real payment provider or webhook is configured. Only the guarded local/
   test Fake Provider may mark payments successful or simulate refunds.
2. SMTP/SMS delivery credentials are not configured. OTP verification,
   expiry, retry and resend limits are tested using the local email backend;
   production delivery requires provider configuration.
3. The local image acceptance verifies HTTPS metadata CRUD, not a live
   Cloudinary upload. Upload requires the external Cloudinary credentials.
4. JWT logout revocation is backed by the configured Django cache. The local
   cache behavior is tested; a shared production cache must be configured for
   cross-process revocation.
5. The current schema cannot persist book/order context on conversations or a
   selected/unselected cart-item flag. Checkout processes every active cart
   item; each cart item represents one listing because there is no quantity.
6. Composite primary keys cannot be represented natively by Django 4.2. The
   custom Admin supports row-safe CRUD, but the two model mappings continue to
   emit W342 warnings and generic ORM usage must include both key fields.
7. Substring `LIKE`/`icontains` searches were functionally and query-count
   tested on the local dataset; this is not a production latency guarantee.
   No FULLTEXT index was added because multilingual semantics are undefined.
8. `PASSBOOK_PLATFORM_FEE_RATE` is configurable; the business policy for fee
   treatment on deposits remains a product decision.
9. Existing Lite installations must apply the listing-moderation and request
   matching schema updates in
   [`passbook_v1.2_lite_listing_moderation_upgrade.sql`](./passbook_v1.2_lite_listing_moderation_upgrade.sql)
   and [`passbook_v1.2_lite_request_matching_upgrade.sql`](./passbook_v1.2_lite_request_matching_upgrade.sql)
   before deploying the backend. The canonical Lite DDL and local XAMPP test
   database support `PENDING`/`REJECTED` listings and request-to-request matches.

## 9. Local Seeded Acceptance Update

The measurements below describe earlier local probe runs. They are retained as
history; the final full-dataset and workflow run in section 9.4 supersedes the
initial fixture counts and incomplete acceptance notes.

Scope was restricted to Django backend. The acceptance fixture and all API
probes used XAMPP `passbook_v12_lite_test` (`127.0.0.1:3308`, MariaDB 10.4.28).
No Aiven or Render endpoint was contacted. The initial probes made no
schema/DDL change; the final acceptance update later added sale-listing
moderation states and the request-match FK/index as recorded in section 9.4.
API/admin probes were rolled back; the seed fixture remains in the local test
database.

### Fixture and secret handling

The guarded, rerunnable `seed_lite_acceptance_data` command created/retained
137 rows across 35 populated Lite tables (the other six mapped tables are
empty). Counts include 5 users, 2 universities, 5 subjects, 10 works/editions/
books/listings/images, 3 addresses/favorites/reservations/reports/notifications,
2 conversations, 10 messages, 2 carts, 3 cart items, 3 orders, 2 payments,
2 shipments/tracking events, 2 returns/refunds/reviews, 3 OTP records, and
the related request/lending/checkout rows. All five user password hashes and
all three OTP values use Django PBKDF2 hashes; neither credential plaintext
was stored or printed. Payment fixtures remain `PENDING`; no provider payment
was simulated.

### API and transaction probes

36 recorded API/security assertions passed in the broad local probe, including
listing create/edit/soft-delete and server-controlled status, owner denial with
unchanged rows, reservation create/cancel/outsider denial, expired listing
rejection, cart/checkout/payment pricing, checkout idempotency, pending-order
cancellation, pending-payment refund denial, request create/edit/match/cancel,
chat membership/message access, notification owner scoping, review eligibility,
report creation, and anonymous denial. A separate borrow probe verified valid
checkout (201), seller confirmation (200), unpaid ready-for-pickup rejection
(400), outsider denial (403), and invalid date rejection (400). The invalid
checkout left no checkout/order rows; enclosing probe transactions were rolled
back and fixture counts remained unchanged. A separate payment retry returned
the same pending payment ID (201 then 200); amount and status remained
server-calculated despite forged client fields.

Additional local probes passed inactive/self-purchase rejection, return seller
authorization/approve/complete sequence, unpaid shipment rejection without
creating a shipment, tracking update/member restrictions, review duplicate
prevention, and bounded message pagination. Matching returned an active
listing for a matching book-work request; a non-owner was denied (403).
Request-interest creation/listing succeeded, while self-interest was rejected
(400). A foreign-address GET probe first used an unsupported method (405); the
correct foreign-address PATCH returned 404 and left the row unchanged. These
results do not exercise every listed transition or true parallel concurrency.

One implementation defect was found and fixed: checkout treated ISO date-time
strings in borrow terms as Python datetime values, producing a 500. The API now
validates each borrow date with DRF `DateTimeField`; unit tests cover valid
parsing and malformed input. The favorites list previously reused the detail
serializer and exposed long description/all images. It now uses the compact
book-card serializer, with a regression test and local payload verification.

### Populated-data smoke measurements

These timings are one-off local observations with 5 active books/listings and
small result sets; they are not production latency guarantees. Query counts did
not grow between books page sizes 2 and 5, and the compact favorites response
omitted description and full images.

| API/query | HTTP | Rows | Queries | Response bytes | Elapsed ms |
|---|---:|---:|---:|---:|---:|
| Books list, page size 2 | 200 | 2 | 5 | 974 | 51.69 |
| Books list, page size 5 | 200 | 5 | 5 | 2,246 | 13.48 |
| Books search | 200 | 5 | 5 | 2,246 | 26.76 |
| Books price filter/sort | 200 | 5 | 5 | 2,246 | 11.38 |
| Book detail | 200 | 1 | 4 | 658 | 8.34 |
| Sale listing list | 200 | 5 | 3 | 2,331 | 5.05 |
| Favorites list (compact payload) | 200 | 2 | 5 | 1,047 | 49.62 |
| Notifications list | 200 | 1 | 2 | 243 | 3.10 |
| Orders list | 200 | 2 | 2 | 421 | 3.30 |
| Conversations list | 200 | 1 | 4 | 254 | 18.75 |
| Conversation messages | 200 | 5 | 4 | 766 | 9.88 |

Read-only MariaDB `EXPLAIN` ran against the seeded data for books, sale
listings, notifications, orders, conversations, and messages. At this fixture
size, books and sale listings scanned 10 rows, orders scanned 3, and messages
scanned 10; lookup joins to book/user/conversation rows used primary or
relationship indexes. These small table scans are expected at this scale and
cannot establish production index efficiency. Serializer query counts were
constant for the tested books page sizes; no N+1 growth was observed in these
sampled endpoints.

### Final live acceptance evidence

Executed against local XAMPP MariaDB `passbook_v12_lite_test` at
`127.0.0.1:3308` (MariaDB 10.4.28), using `PASSBOOK_ENVIRONMENT=test` and the
guarded Fake Provider. The repeatable command
`manage.py run_lite_acceptance --confirm-local-test-db` completed successfully.

- **Database:** all 41/41 Lite tables, columns, 90 foreign keys, 182 declared
  indexes (+1 MariaDB-generated FK index), and all 60 declared CHECK
  constraints verified against DDL; zero orphan rows. The repeatable seed
  populated all 41 tables with 3,815 fixture rows, including 500 books,
  50 users, and real pending/rejected listing records.
- **Authentication/OTP:** registration, valid/invalid login, expiry/refresh/
  logout, locked account, OTP expiry/attempt/resend limits, verification, and
  password reset passed against the database.
- **Workflows:** profile/address ownership, listing ownership/edit, new
  listings enter `PENDING`, sellers cannot self-approve, pending listings are
  hidden from public search, admin approve/reject publishes or rejects them,
  and rejected edits return to moderation. HTTPS image metadata CRUD,
  reservations, cart/checkout retry/cancel, Fake payment
  success/failure/cancel, shipment/tracking, return/refund, borrow, favorites,
  messaging, notifications, requests/matching/interests, reviews, reports and
  dashboard probes passed. Invalid transitions and unauthorized paths were
  rejected.
- **Idempotency/concurrency:** two-user reservation race yielded exactly one
  winner; concurrent checkout returned one checkout group; concurrent payment
  retry returned one payment; checkout/payment/refund/report retries did not
  duplicate their records.
- **Admin:** login, all 41 Lite model changelists, every permitted add/edit/delete
  form, and User/OTP search/filter pages passed. Add/edit/delete operations
  passed for a standard model and both composite-key models; duplicate
  composite rows were rejected without writes.
- **Performance:** with 500 books and a 15-query endpoint ceiling: book list
  5 queries, search 5, filter/sort 5, detail 4, favorites 5, orders 2,
  messages 4, dashboard 15. Measured local request time was 2.9–38.3 ms in
  this run; this is a query-regression probe, not a production load guarantee.
- **Regression suite:** `manage.py test` — **76 passed, 0 failed**.
- `manage.py check` — exit 0; two W342 warnings remain because Django 4.2
  cannot represent the database's composite primary keys. Replacing either
  FK with a OneToOneField would misrepresent the Lite schema. Composite Admin
  CRUD uses both key columns safely.
- `manage.py makemigrations --check --dry-run` — no changes detected.
- `python3 -m compileall -q .` and `git diff --check` — passed.

No Aiven, Render, real payment provider, Cloudinary upload or production
email/SMS endpoint was used. Those external integrations remain outside this
local/test acceptance target.

## 14. Final Acceptance Audit

| Module | Status | Evidence |
|---|---|---|
| Database (41/41 tables) | PASS | Live MariaDB schema, columns, 90 FKs, 182 indexes, 60 checks and orphan validation |
| Authentication | PASS | Database-backed register/login/invalid password/refresh/logout/status/reset probes |
| OTP | PASS | Database-backed expiry, invalid code, attempts, resend and verification probes |
| User/Profile | PASS | Profile/address update, ownership denial, seller profile and account status probes |
| Marketplace | PASS | Seller submission defaults to PENDING; approval/rejection, ownership, image metadata, search/filter/sort/page on 500 books |
| Commerce | PASS | Cart, checkout idempotency, order cancellation and invalid repeat transition |
| Payment simulation | PASS | Fake Provider intent/retry/success/failure/cancel/refund/retry; no real money |
| Reservation | PASS | Create/confirm/cancel, invalid repeat, two-user concurrency race |
| Borrow | PASS | Complete valid lifecycle and invalid repeat-state rejection |
| Shipping | PASS | Shipped/in-transit/delivered tracking workflow |
| Return/Refund | PASS | Return approval/completion; fake refund failed/completed/retry idempotently |
| Messaging | PASS | Conversation/message API and 4-query paginated message probe |
| Notification | PASS | Notification list and mark-read |
| Favorites | PASS | Create/idempotent retry/delete and 5-query list probe |
| Reviews/Reports/Matching | PASS | Review/report retries, BUY/SELL_INTENT and BUY/BORROW matches, request-interest create/retry |
| Admin | PASS | Login, all 41 changelists and permitted operation forms, search/filter, moderation approve/reject, standard CRUD and composite-key CRUD |
| Admin Dashboard API | PASS | Live pending/rejected counts supported and nonzero; aggregate endpoint uses 15 queries |
| Security | PASS | Invalid auth, ownership/role denial, locked user and fake-payment admin guard |
| Concurrency | PASS | Reservation one-winner, single checkout group, single payment under two-thread races |
| Performance | PASS | 500-book fixture; all eight measured endpoints at or below 15 SQL queries |
| Tests | PASS | 76 passed / 0 failed; system check, migrations, compile and diff checks passed |

**BACKEND ACCEPTANCE: PASS**

```
BACKEND ACCEPTANCE: PASS

41/41 tables: PASS
Authentication: PASS
OTP: PASS
Marketplace: PASS
Commerce: PASS
Payment simulation: PASS
Reservation: PASS
Borrow: PASS
Shipping: PASS
Return/Refund: PASS
Messaging: PASS
Notification: PASS
Admin: PASS
Admin Dashboard API: PASS
Security: PASS
Concurrency: PASS
Performance: PASS
Tests: 76 passed / 0 failed
```
