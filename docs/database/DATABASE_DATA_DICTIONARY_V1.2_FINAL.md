# Passbook Database Data Dictionary — v1.2 FINAL

**Status:** Owner decisions incorporated; remaining `[NEEDS CONFIRMATION]` items are explicitly listed. This is a data dictionary, not executable DDL.

**Scope:** 57 tables, C2C sale and lending, VND only, MySQL 8.0.16+. This file documents the v1.2 architecture described in the design conversation. The repository currently documents a legacy 12-table unmanaged Django schema; it does not contain a persisted 57-table v1.2 specification. The legacy models are not treated as the target schema.

> **Do not generate DDL while any `[NEEDS CONFIRMATION]` item remains unresolved.** No schema is created or migrated by this document.

## 1. Conventions

### 1.1 Types

| Alias | MySQL type |
|---|---|
| `ID` | `BIGINT UNSIGNED` |
| `MONEY` | `DECIMAL(19,4)` |
| `RATE` | `DECIMAL(9,6)` |
| `UTC_TS` | `DATETIME(3)`; values represent UTC |
| `JSON` | `JSON` |

- `!` means `NOT NULL`; `?` means nullable.
- `created_at` columns are `DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)`.
- Mutable `updated_at` columns are `DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)`.
- Nullable business-event timestamps such as `paid_at`, `completed_at`, `approved_at`, `processed_at`, and `delivered_at` default to NULL. Non-null business-event timestamps have no implicit default.
- Other unprovided defaults are not silently assumed.
- Currency is explicitly represented as `CHAR(3)`, default/allowed value `VND`; no FX or other currency is supported in v1.2.
- `MONEY` must not be implemented with FLOAT/DOUBLE. Payment/transfer rounding is not fully specified; see open questions.
- Every FK has `ON UPDATE CASCADE`. `ON DELETE` is documented for every FK below: `RESTRICT`, `CASCADE`, or `SET NULL`.
- Every FK must have an index; an existing composite index may serve when the FK columns are its leftmost prefix.
- CHECK constraints require MySQL 8.0.16+ and must be verified as enforced on the deployed test server.
- Status/type columns are strings, not MySQL ENUMs. Where the architecture did not define the full allowed set, it is marked `[NEEDS CONFIRMATION]`.
- Generated-column expressions below are logical MySQL-compatible expressions; uniqueness columns are `STORED`.
- Timestamps are UTC; creation/update defaults follow the explicit rules above. No automatic default is assigned to a non-null business-event timestamp.

### 1.2 Delete-policy codes

- **R — RESTRICT:** prevent deleting a referenced row; transaction/audit history is preserved.
- **C — CASCADE:** delete dependent non-financial child/junction data with the parent.
- **N — SET NULL:** preserve the child row while detaching an optional actor/reference.
- All FKs use `ON UPDATE CASCADE`.
- Financial, order, payment, payout, refund, and audit records are never cascade-deleted.

### 1.3 Shared requirements

- Table names, column names, and the 57-table count are fixed in this candidate.
- All `id` primary keys use `ID`. Join tables may instead use the composite PK specified in their table section.
- All amounts include a currency column in their own table or explicitly inherit currency from a parent. No amount may be stored without a known VND denomination.
- For optional profile fields, NULL means “not supplied”; it must not prevent register/buy/sell/lend/borrow/request workflows.
- Composite-FK nullable behavior in MySQL must be supplemented by CHECK constraints where needed: a nullable component may otherwise cause the FK check to be skipped.

## 2. User and education

## 1. `users`

### Purpose
Shared identity for buyer, seller, borrower, lender, and admin roles.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | User identifier |
| email | VARCHAR(254) | NO | — | UQ | Normalized email |
| password_hash | VARCHAR(255) | NO | — | | Password hash |
| full_name | VARCHAR(150) | NO | — | | Display/legal name |
| phone | VARCHAR(30) | YES | NULL | | Optional phone |
| avatar_url | VARCHAR(2048) | YES | NULL | | Optional avatar |
| role | VARCHAR(20) | NO | [NEEDS CONFIRMATION] | | User/admin role model |
| status | VARCHAR(20) | NO | [NEEDS CONFIRMATION] | | Account status |
| university_id | ID | YES | NULL | FK | Optional education profile |
| faculty_id | ID | YES | NULL | FK | Optional faculty |
| major_id | ID | YES | NULL | FK | Optional major |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Last update |

### Foreign Keys

| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| university_id | universities(id) | RESTRICT | CASCADE |
| (faculty_id, university_id) | faculties(id, university_id) | RESTRICT | CASCADE |
| (major_id, faculty_id) | majors(id, faculty_id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(email)` after application normalization to lowercase/trimmed canonical form. Case-insensitive collation choice: [NEEDS CONFIRMATION].

### Indexes
- Unique index on `email`.
- Indexes supporting all three education FKs; `(university_id,status)`, `(faculty_id)`, `(major_id)`.

### Check Constraints
- Role/status allowlists: [NEEDS CONFIRMATION].
- `(faculty_id IS NULL OR university_id IS NOT NULL)`.
- `(major_id IS NULL OR (faculty_id IS NOT NULL AND university_id IS NOT NULL))`.

### Generated Columns
- None.

### Business Rules
- A user has one account and may act in multiple marketplace roles.
- Education data is optional and never required for registration or transactions.
- Email normalization is a service invariant; database uniqueness protects canonical values.
- Composite FKs ensure selected faculty belongs to selected university and selected major belongs to selected faculty.

## 2. `user_addresses`

### Purpose
Saved user addresses; orders retain independent address snapshots.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Address identifier |
| user_id | ID | NO | — | FK | Address owner |
| recipient_name | VARCHAR(150) | NO | — | | Recipient |
| phone | VARCHAR(30) | NO | — | | Delivery phone |
| address_line | VARCHAR(500) | NO | — | | Street/building |
| ward | VARCHAR(150) | NO | — | | Ward |
| district | VARCHAR(150) | NO | — | | District |
| city | VARCHAR(150) | NO | — | | City/province |
| postal_code | VARCHAR(30) | YES | NULL | | Optional postal code |
| is_default | BOOLEAN | NO | FALSE | | Default address flag |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Last update |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| user_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(default_address_user_key)`; generated column is STORED.

### Indexes
- `(user_id,is_default)`.

### Check Constraints
- Boolean domain for `is_default`.

### Generated Columns
- `default_address_user_key` STORED: `CASE WHEN is_default = 1 THEN user_id ELSE NULL END`; ensures at most one default address per user.

### Business Rules
- Address edits do not alter any existing order’s `shipping_address_snapshot`.
- User deletion/anonymization policy for retained addresses: [NEEDS CONFIRMATION].

## 3. `user_violations`

### Purpose
Moderation and enforcement history for a user.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Violation identifier |
| user_id | ID | NO | — | FK | Violating user |
| violation_type | VARCHAR(50) | NO | — | | Violation category |
| reason | VARCHAR(255) | NO | — | | Short reason |
| description | TEXT | YES | NULL | | Details |
| severity | VARCHAR(20) | NO | [NEEDS CONFIRMATION] | | Severity |
| status | VARCHAR(20) | NO | OPEN | | Case status |
| expires_at | UTC_TS | YES | NULL | | Optional expiry |
| created_by | ID | YES | NULL | FK | Admin/actor |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| resolved_at | UTC_TS | YES | NULL | | Resolution time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| user_id | users(id) | RESTRICT | CASCADE |
| created_by | users(id) | SET NULL | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(user_id,status,created_at)`.
- `(status,severity,created_at)`.

### Check Constraints
- Allowed `severity` values: [NEEDS CONFIRMATION].
- `status` allowlist: [NEEDS CONFIRMATION].
- Resolved status requires `resolved_at`; unresolved status must not have a resolution timestamp unless policy permits it: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Violation history is retained; user deletion is restricted or anonymized by a separately approved privacy policy.

## 4. `universities`

### Purpose
Education reference catalog.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | University identifier |
| name | VARCHAR(255) | NO | — | | Name |
| code | VARCHAR(50) | NO | — | UQ | Stable code |
| address | VARCHAR(500) | YES | NULL | | Optional address |
| website | VARCHAR(2048) | YES | NULL | | Optional website |
| status | VARCHAR(20) | NO | ACTIVE | | Availability |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
- None.

### Unique Constraints
- `UNIQUE(code)`.

### Indexes
- Unique `code`; `(status,name)`.

### Check Constraints
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Referenced universities cannot be hard-deleted.

## 5. `faculties`

### Purpose
Faculties belonging to a university.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Faculty identifier |
| university_id | ID | NO | — | FK | Parent university |
| name | VARCHAR(255) | NO | — | | Name |
| code | VARCHAR(50) | NO | — | | University-scoped code |
| status | VARCHAR(20) | NO | ACTIVE | | Availability |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| university_id | universities(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(university_id,code)`.
- `UNIQUE(id,university_id)` for the users composite FK.

### Indexes
- `(university_id,status,name)`.

### Check Constraints
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Faculty university association is immutable while referenced by user profiles unless reassignment is explicitly performed.

## 6. `majors`

### Purpose
Majors belonging to faculties.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Major identifier |
| faculty_id | ID | NO | — | FK | Parent faculty |
| name | VARCHAR(255) | NO | — | | Name |
| code | VARCHAR(50) | NO | — | | Faculty-scoped code |
| status | VARCHAR(20) | NO | ACTIVE | | Availability |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| faculty_id | faculties(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(faculty_id,code)`.
- `UNIQUE(id,faculty_id)` for the users composite FK.

### Indexes
- `(faculty_id,status,name)`.

### Check Constraints
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Major’s faculty is the authority for the major’s university hierarchy.

## 7. `subjects`

### Purpose
Global subject catalog.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Subject identifier |
| name | VARCHAR(255) | NO | — | | Name |
| code | VARCHAR(50) | NO | — | UQ | Global subject code |
| description | TEXT | YES | NULL | | Optional description |
| credits | SMALLINT UNSIGNED | YES | NULL | | Optional credit count |
| status | VARCHAR(20) | NO | ACTIVE | | Availability |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Last update |

### Foreign Keys
- None.

### Unique Constraints
- `UNIQUE(code)`.

### Indexes
- Unique code; `(status,name)`.

### Check Constraints
- `credits IS NULL OR credits > 0`.
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Subject is global in v1.2; university-specific subject catalogs are not specified.

## 3. Catalog and book

## 8. `categories`

### Purpose
Hierarchical book taxonomy.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Category identifier |
| parent_id | ID | YES | NULL | FK | Parent category |
| name | VARCHAR(150) | NO | — | | Name |
| slug | VARCHAR(180) | NO | — | UQ | URL-safe key |
| description | TEXT | YES | NULL | | Optional details |
| status | VARCHAR(20) | NO | ACTIVE | | Availability |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Last update |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| parent_id | categories(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(slug)`.

### Indexes
- Unique slug; `(parent_id,status,name)`.

### Check Constraints
- `parent_id IS NULL OR parent_id <> id`.
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Multi-row cycles cannot be prevented by a simple CHECK; service must validate category ancestry.

## 9. `languages`

### Purpose
Language reference catalog.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Language identifier |
| name | VARCHAR(100) | NO | — | | Display name |
| code | VARCHAR(20) | NO | — | UQ | Language code |
| status | VARCHAR(20) | NO | ACTIVE | | Availability |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
- None.

### Unique Constraints
- `UNIQUE(code)`.

### Indexes
- Unique code; `(status,name)`.

### Check Constraints
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Language is stored at edition level.

## 10. `book_works`

### Purpose
Logical work or textbook independent of a specific edition/copy.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Work identifier |
| title | VARCHAR(500) | NO | — | | Work title |
| subtitle | VARCHAR(500) | YES | NULL | | Subtitle |
| description | TEXT | YES | NULL | | Description |
| author_name | VARCHAR(500) | YES | NULL | | Author label |
| publisher_name | VARCHAR(255) | YES | NULL | | Catalog publisher label |
| category_id | ID | YES | NULL | FK | Category |
| created_by | ID | NO | — | FK | Catalog creator |
| status | VARCHAR(20) | NO | ACTIVE | | Catalog status |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Last update |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| category_id | categories(id) | RESTRICT | CASCADE |
| created_by | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(status,created_at,id)`.
- `(category_id,status,created_at)`.

### Check Constraints
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Language and edition identifiers belong to editions, not the work.

## 11. `book_work_subjects`

### Purpose
Many-to-many mapping of works to subjects.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| book_work_id | ID | NO | — | PK, FK | Work |
| subject_id | ID | NO | — | PK, FK | Subject |
| is_primary | BOOLEAN | NO | FALSE | | Primary subject flag |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| book_work_id | book_works(id) | CASCADE | CASCADE |
| subject_id | subjects(id) | RESTRICT | CASCADE |

### Unique Constraints
- Composite PK `(book_work_id,subject_id)`.
- `UNIQUE(primary_subject_work_key)`; generated column is STORED.

### Indexes
- PK index; `(subject_id,book_work_id)`.

### Check Constraints
- `is_primary IN (0,1)`.

### Generated Columns
- `primary_subject_work_key`: `CASE WHEN is_primary = 1 THEN book_work_id ELSE NULL END`; at most one primary subject/work.

### Business Rules
- A work may have zero or more subjects.

## 12. `book_editions`

### Purpose
Published edition/version of a logical work.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Edition identifier |
| book_work_id | ID | NO | — | FK | Logical work |
| edition_name | VARCHAR(100) | YES | NULL | | Edition label |
| edition_number | SMALLINT UNSIGNED | YES | NULL | | Numeric edition |
| publisher_name | VARCHAR(255) | YES | NULL | | Edition publisher |
| publication_year | SMALLINT UNSIGNED | YES | NULL | | Year |
| publication_date | DATE | YES | NULL | | Date |
| page_count | INT UNSIGNED | YES | NULL | | Pages |
| format | VARCHAR(30) | YES | NULL | | Print/digital format |
| language_id | ID | YES | NULL | FK | Edition language |
| description | TEXT | YES | NULL | | Edition details |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Last update |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| book_work_id | book_works(id) | RESTRICT | CASCADE |
| language_id | languages(id) | RESTRICT | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(book_work_id,publication_year)`.
- Index on `language_id`.

### Check Constraints
- `edition_number IS NULL OR edition_number > 0`.
- `page_count IS NULL OR page_count > 0`.
- Publication year bounds: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- ISBN/identifiers are stored only in `book_identifiers`.

## 13. `book_identifiers`

### Purpose
ISBN and other edition identifiers.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Identifier row |
| book_edition_id | ID | NO | — | FK | Edition |
| identifier_type | VARCHAR(30) | NO | — | | ISBN_10/ISBN_13/other |
| identifier_value | VARCHAR(100) | NO | — | | Normalized value |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| book_edition_id | book_editions(id) | CASCADE | CASCADE |

### Unique Constraints
- `UNIQUE(identifier_type,identifier_value)`.

### Indexes
- Unique identifier index; `(book_edition_id)`.

### Check Constraints
- Non-empty type and value.
- Identifier type allowlist/namespace: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- ISBN normalization/checksum is service-level.
- Global uniqueness for non-ISBN identifier types: [NEEDS CONFIRMATION].

## 14. `books`

### Purpose
One physical copy, with owner and condition; no price or quantity.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Physical copy |
| book_edition_id | ID | NO | — | FK | Edition |
| owner_id | ID | NO | — | FK | Current owner |
| condition_label | VARCHAR(30) | NO | — | | Condition |
| condition_description | TEXT | YES | NULL | | Condition details |
| acquisition_type | VARCHAR(30) | YES | NULL | | Acquisition provenance |
| status | VARCHAR(20) | NO | AVAILABLE | | Inventory lifecycle |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Last update |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| book_edition_id | book_editions(id) | RESTRICT | CASCADE |
| owner_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- None; multiple copies may share an edition.

### Indexes
- `(status,created_at,id)`.
- `(owner_id,status,created_at,id)`.
- `(book_edition_id)`.

### Check Constraints
- Status exactly `AVAILABLE, RESERVED, ON_LOAN, SOLD, UNAVAILABLE`.
- Condition/acquisition allowlists: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- `AVAILABLE → RESERVED → SOLD` for sale; `AVAILABLE → RESERVED → ON_LOAN → AVAILABLE` for borrow; timeout/cancel releases reservation; admin may mark unavailable.
- A RESERVED book must be associated with one live checkout/order reservation.

## 15. `book_images`

### Purpose
Images of a physical copy.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Image |
| book_id | ID | NO | — | FK | Physical copy |
| image_url | VARCHAR(2048) | NO | — | | Image URL |
| cloudinary_public_id | VARCHAR(255) | YES | NULL | | Cloudinary asset |
| is_primary | BOOLEAN | NO | FALSE | | Primary image |
| sort_order | INT UNSIGNED | NO | 0 | | Display order |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| book_id | books(id) | CASCADE | CASCADE |

### Unique Constraints
- `UNIQUE(primary_image_book_key)`; generated column is STORED.

### Indexes
- `(book_id,is_primary,sort_order)`.

### Check Constraints
- `sort_order >= 0`; boolean domain.

### Generated Columns
- `primary_image_book_key` STORED: `CASE WHEN is_primary = 1 THEN book_id ELSE NULL END`.

### Business Rules
- At most one primary image/book; image URL and Cloudinary public ID are not credentials.

## 16. `book_verifications`

### Purpose
Verification status and notes for a physical copy.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Verification |
| book_id | ID | NO | — | FK | Copy |
| verifier_id | ID | YES | NULL | FK | Verifier |
| status | VARCHAR(20) | NO | PENDING | | Status |
| verification_type | VARCHAR(30) | NO | — | | Verification method |
| notes | TEXT | YES | NULL | | Notes |
| verified_at | UTC_TS | YES | NULL | | Verification time |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| book_id | books(id) | RESTRICT | CASCADE |
| verifier_id | users(id) | SET NULL | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(book_id,status,created_at)`; `(verifier_id,status)`.

### Check Constraints
- Status/type allowlists: [NEEDS CONFIRMATION].
- Verified status requires `verified_at`.

### Generated Columns
- None.

### Business Rules
- Verification history is retained.

## 17. `verification_evidences`

### Purpose
Evidence attached to a verification.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Evidence |
| verification_id | ID | NO | — | FK | Parent verification |
| evidence_type | VARCHAR(30) | NO | — | | Type |
| evidence_url | VARCHAR(2048) | NO | — | | URL |
| description | TEXT | YES | NULL | | Description |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| verification_id | book_verifications(id) | CASCADE | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(verification_id,created_at)`.

### Check Constraints
- Evidence type allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Evidence records are children of verification; external object retention/deletion policy: [NEEDS CONFIRMATION].

## 4. Sale and lending

## 18. `sale_listings`

### Purpose
Offer to sell exactly one physical copy.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Listing |
| book_id | ID | NO | — | FK | Physical book |
| seller_id | ID | NO | — | FK | Seller |
| title | VARCHAR(500) | NO | — | | Listing title snapshot/current content |
| description | TEXT | YES | NULL | | Listing description |
| price | MONEY | NO | — | | Asking price |
| currency | CHAR(3) | NO | VND | | Price currency |
| status | VARCHAR(20) | NO | DRAFT | | Listing lifecycle |
| published_at | UTC_TS | YES | NULL | | Publish time |
| expires_at | UTC_TS | YES | NULL | | Expiry |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| book_id | books(id) | RESTRICT | CASCADE |
| seller_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(active_sale_book_key)`; generated column is STORED.
- `UNIQUE(id,seller_id)` for combo same-seller composite FK.

### Indexes
- `(seller_id,status,created_at,id)`.
- `(status,price,id)`.
- `(status,created_at,id)`.
- Active-book unique index.

### Check Constraints
- `price > 0`; `currency='VND'`.
- Status exactly `DRAFT, ACTIVE, RESERVED, SOLD, CLOSED, EXPIRED`.
- `expires_at IS NULL OR published_at IS NULL OR expires_at > published_at`.

### Generated Columns
- `active_sale_book_key` STORED: `CASE WHEN status IN ('ACTIVE','RESERVED') THEN book_id ELSE NULL END`.

### Business Rules
- One listing sells one physical copy; no quantity column.
- Seller must be owner at listing creation; ownership verification is service-level.
- Cross-table SALE/LEND exclusivity is service-level with a lock on `books`.

## 19. `sale_combos`

### Purpose
Offer grouping multiple sale listings from one seller.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Combo |
| seller_id | ID | NO | — | FK | Owner/seller |
| name | VARCHAR(255) | NO | — | | Combo name |
| description | TEXT | YES | NULL | | Description |
| price | MONEY | NO | — | | Combo price |
| currency | CHAR(3) | NO | VND | | Currency |
| status | VARCHAR(20) | NO | DRAFT | | Lifecycle |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| seller_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(id,seller_id)`.

### Indexes
- `(seller_id,status,created_at,id)`.

### Check Constraints
- `price > 0`; `currency='VND'`; status allowlist [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- All combo constituents must have same seller and currency; availability revalidated at checkout.

## 20. `sale_combo_items`

### Purpose
Constituent sale listings in a combo.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| combo_id | ID | NO | — | PK, FK | Combo |
| sale_listing_id | ID | NO | — | PK, FK | Constituent listing |
| seller_id | ID | NO | — | FK | Denormalized for composite consistency FK |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| (combo_id,seller_id) | sale_combos(id,seller_id) | CASCADE | CASCADE |
| (sale_listing_id,seller_id) | sale_listings(id,seller_id) | RESTRICT | CASCADE |
| seller_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- Composite PK `(combo_id,sale_listing_id)`.

### Indexes
- PK index; `(sale_listing_id,combo_id)`.

### Check Constraints
- Same-seller condition enforced by composite FKs.

### Generated Columns
- None.

### Business Rules
- Duplicate listing in the same combo is prevented by PK.
- Combo must contain at least one item: [NEEDS CONFIRMATION] (cross-row/service rule).

## 21. `lend_listings`

### Purpose
Offer to lend one physical copy.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Lend offer |
| book_id | ID | NO | — | FK | Physical copy |
| lender_id | ID | NO | — | FK | Lender |
| title | VARCHAR(500) | NO | — | | Offer title |
| description | TEXT | YES | NULL | | Description |
| status | VARCHAR(20) | NO | DRAFT | | Listing lifecycle |
| deposit_amount | MONEY | YES | NULL | | Refundable security amount |
| rental_fee | MONEY | NO | — | | Rental charge |
| currency | CHAR(3) | NO | VND | | Currency |
| published_at | UTC_TS | YES | NULL | | Publish time |
| expires_at | UTC_TS | YES | NULL | | Expiry |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| book_id | books(id) | RESTRICT | CASCADE |
| lender_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(active_lend_book_key)`; generated column is STORED.

### Indexes
- `(lender_id,status,created_at,id)`.
- `(status,rental_fee,id)`.
- `(status,created_at,id)`.
- Active-book unique index.

### Check Constraints
- `rental_fee >= 0`; `deposit_amount IS NULL OR deposit_amount >= 0`; currency VND.
- Status exactly `DRAFT, ACTIVE, RESERVED, ON_LOAN, CLOSED, EXPIRED`.

### Generated Columns
- `active_lend_book_key` STORED: `CASE WHEN status IN ('ACTIVE','RESERVED','ON_LOAN') THEN book_id ELSE NULL END`.

### Business Rules
- Lender must be owner at listing creation.
- Active SALE/LEND exclusivity is service-level; the generated unique key only prevents duplicate LEND rows.

## 22. `borrow_terms`

### Purpose
Terms applicable to one lend listing.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Terms |
| lend_listing_id | ID | NO | — | UQ, FK | Parent listing |
| max_days | SMALLINT UNSIGNED | NO | — | | Maximum loan duration |
| late_fee_per_day | MONEY | YES | NULL | | Late fee |
| deposit_required | BOOLEAN | NO | FALSE | | Whether deposit is required |
| shipping_paid_by | VARCHAR(20) | NO | [NEEDS CONFIRMATION] | | Shipping payer |
| return_method | VARCHAR(30) | NO | [NEEDS CONFIRMATION] | | Return method |
| notes | TEXT | YES | NULL | | Extra terms |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| lend_listing_id | lend_listings(id) | CASCADE | CASCADE |

### Unique Constraints
- `UNIQUE(lend_listing_id)`.

### Indexes
- Unique FK index.

### Check Constraints
- `max_days > 0`; `late_fee_per_day IS NULL OR late_fee_per_day >= 0`; boolean domain.
- Shipping payer and return method allowlists: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Currency is inherited from `lend_listings.currency`.
- Checkout snapshots terms; later listing-term changes do not alter an existing borrow.

## 5. Requests, cart, checkout

## 23. `book_requests`

### Purpose
BUY/BORROW demand or SELL_INTENT.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Request |
| user_id | ID | NO | — | FK | Author |
| request_type | VARCHAR(20) | NO | — | | BUY, BORROW, SELL_INTENT |
| book_work_id | ID | YES | NULL | FK | Requested work |
| category_id | ID | YES | NULL | FK | Requested category |
| title_keyword | VARCHAR(500) | YES | NULL | | Text query |
| description | TEXT | YES | NULL | | Request details |
| budget_max | MONEY | YES | NULL | | BUY/BORROW maximum |
| asking_price | MONEY | YES | NULL | | SELL_INTENT price |
| currency | CHAR(3) | YES | NULL | | Required when either amount exists |
| condition_preference | VARCHAR(30) | YES | NULL | | Preferred condition |
| status | VARCHAR(20) | NO | OPEN | | Request status |
| expires_at | UTC_TS | YES | NULL | | Optional expiry |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| user_id | users(id) | RESTRICT | CASCADE |
| book_work_id | book_works(id) | RESTRICT | CASCADE |
| category_id | categories(id) | RESTRICT | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(user_id,status,created_at,id)`.
- `(request_type,status,expires_at)`.
- `(category_id,status,created_at)`.
- `(book_work_id,status)`.

### Check Constraints
- Type allowlist `BUY,BORROW,SELL_INTENT`.
- At least one of work/category/keyword must be supplied.
- BUY/BORROW: `asking_price IS NULL`; SELL_INTENT: `budget_max IS NULL`.
- Amounts must be nonnegative; amount present requires `currency='VND'`.
- Status/condition allowlists: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- BUY request ≠ SELL_INTENT ≠ sale listing.
- Interest on SELL_INTENT is a signal, not an automatically created listing.

## 24. `request_interests`

### Purpose
Users interested in a SELL_INTENT request.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Interest |
| request_id | ID | NO | — | FK | Request |
| user_id | ID | NO | — | FK | Interested user |
| note | TEXT | YES | NULL | | Optional note |
| status | VARCHAR(20) | NO | ACTIVE | | Interest status |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| request_id | book_requests(id) | CASCADE | CASCADE |
| user_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(request_id,user_id)`.

### Indexes
- `(request_id,status,created_at)`; `(user_id,status,created_at)`.

### Check Constraints
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- User cannot express interest in their own request; service validation.

## 25. `request_matches`

### Purpose
Matching BUY/BORROW requests to listings.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Match |
| request_id | ID | NO | — | FK | Request |
| sale_listing_id | ID | YES | NULL | FK | Sale target |
| lend_listing_id | ID | YES | NULL | FK | Lend target |
| match_type | VARCHAR(20) | NO | — | | Match category |
| score | DECIMAL(6,5) | YES | NULL | | Match score |
| status | VARCHAR(20) | NO | SUGGESTED | | Match state |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| request_id | book_requests(id) | CASCADE | CASCADE |
| sale_listing_id | sale_listings(id) | RESTRICT | CASCADE |
| lend_listing_id | lend_listings(id) | RESTRICT | CASCADE |

### Unique Constraints
- No match deduplication key specified: [NEEDS CONFIRMATION].

### Indexes
- `(request_id,status,created_at)`.
- `(sale_listing_id,status)`.
- `(lend_listing_id,status)`.

### Check Constraints
- Exactly one of `sale_listing_id`,`lend_listing_id`.
- Score NULL or between 0 and 1.
- Type/status allowlists: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Request/listing type compatibility is service-level.

## 26. `carts`

### Purpose
One active cart per user; past carts may remain for history.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Cart |
| user_id | ID | NO | — | FK | Owner |
| status | VARCHAR(20) | NO | ACTIVE | | Cart lifecycle |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| user_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(active_cart_user_key)`; generated column is STORED.

### Indexes
- `(user_id,status,updated_at)`.

### Check Constraints
- Status exactly `ACTIVE,CHECKED_OUT,ABANDONED`.

### Generated Columns
- `active_cart_user_key` STORED: `CASE WHEN status = 'ACTIVE' THEN user_id ELSE NULL END`.

### Business Rules
- Cart does not reserve inventory.

## 27. `cart_items`

### Purpose
Temporary sale/lend/combo intent and price snapshot.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Cart line |
| cart_id | ID | NO | — | FK | Cart |
| sale_listing_id | ID | YES | NULL | FK | Sale target |
| lend_listing_id | ID | YES | NULL | FK | Lend target |
| sale_combo_id | ID | YES | NULL | FK | Combo target |
| unit_price | MONEY | NO | — | | Price snapshot |
| currency | CHAR(3) | NO | VND | | Snapshot currency |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| cart_id | carts(id) | CASCADE | CASCADE |
| sale_listing_id | sale_listings(id) | RESTRICT | CASCADE |
| lend_listing_id | lend_listings(id) | RESTRICT | CASCADE |
| sale_combo_id | sale_combos(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(cart_id,sale_listing_id)`, `UNIQUE(cart_id,lend_listing_id)`, `UNIQUE(cart_id,sale_combo_id)`; MySQL permits multiple NULL values, while the XOR CHECK ensures exactly one target is populated.

### Indexes
- `(cart_id,created_at,id)` and indexes supporting all target FKs.

### Check Constraints
- Exactly one target is non-NULL.
- `unit_price >= 0`; currency VND.

### Generated Columns
- None required; the three target-specific composite unique indexes are sufficient with the XOR CHECK.

### Business Rules
- Price is revalidated at checkout; cart never reserves.

## 28. `checkout_groups`

### Purpose
Idempotent checkout attempt, inventory reservation parent, and snapshot container.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Checkout |
| checkout_code | VARCHAR(64) | NO | — | UQ | Public/internal code |
| idempotency_key | VARCHAR(128) | NO | — | UQ | Retry key |
| cart_id | ID | NO | — | FK | Source cart |
| buyer_id | ID | NO | — | FK | Buyer |
| status | VARCHAR(20) | NO | [NEEDS CONFIRMATION] | | Checkout state |
| currency | CHAR(3) | NO | VND | | Checkout currency |
| subtotal | MONEY | NO | — | | Pre-discount sum |
| shipping_total | MONEY | NO | 0 | | Shipping |
| discount_total | MONEY | NO | 0 | | Discount |
| total_amount | MONEY | NO | — | | Amount payable |
| shipping_address_snapshot | JSON | NO | — | | Immutable address |
| pricing_snapshot | JSON | NO | — | | Pricing breakdown |
| coupon_snapshot | JSON | YES | NULL | | Applied coupon details |
| reservation_expires_at | UTC_TS | YES | NULL | | NULL: no current inventory reservation; non-NULL: group reservation expiry |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |
| completed_at | UTC_TS | YES | NULL | | Checkout completion |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| cart_id | carts(id) | RESTRICT | CASCADE |
| buyer_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(checkout_code)`.
- `UNIQUE(buyer_id,idempotency_key)`.

### Indexes
- `(buyer_id,status,created_at,id)`.
- `(cart_id,created_at)`.
- `(status,reservation_expires_at)`.

### Check Constraints
- Currency VND.
- Amounts nonnegative; `total_amount = subtotal + shipping_total - discount_total` subject to pricing policy [NEEDS CONFIRMATION].
- Reservation expiry NULL or later than creation.
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Retry for same buyer/idempotency key returns the same checkout group.
- `reservation_expires_at IS NULL` means the checkout group currently holds no inventory reservation.
- Non-NULL means a reservation is active until that UTC expiry.
- Reservation starts after the checkout transaction has locked and validated inventory and committed the group/orders.
- Timeout/expiry/cancel releases all reservations in the group atomically. Partial expiry across split orders is not supported in v1.

## 6. Orders, payment, fulfillment

## 29. `orders`

### Purpose
Order split by seller and transaction type.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Order |
| order_code | VARCHAR(64) | NO | — | UQ | Order code |
| checkout_group_id | ID | NO | — | FK | Parent checkout |
| buyer_id | ID | NO | — | FK | Buyer |
| seller_id | ID | YES | NULL | FK | SALE seller only |
| order_type | VARCHAR(20) | NO | — | | SALE or BORROW |
| status | VARCHAR(30) | NO | PENDING_PAYMENT | | Order lifecycle |
| currency | CHAR(3) | NO | VND | | Order currency |
| subtotal | MONEY | NO | — | | Items before shipping/discount |
| shipping_fee | MONEY | NO | 0 | | Shipping |
| discount_amount | MONEY | NO | 0 | | Discount |
| total_amount | MONEY | NO | — | | Total |
| shipping_address_snapshot | JSON | NO | — | | Address snapshot |
| pricing_snapshot | JSON | NO | — | | Detailed pricing |
| coupon_snapshot | JSON | YES | NULL | | Coupon snapshot |
| note | TEXT | YES | NULL | | Buyer note |
| placed_at | UTC_TS | YES | NULL | | Order placement |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |
| completed_at | UTC_TS | YES | NULL | | Completion |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| checkout_group_id | checkout_groups(id) | RESTRICT | CASCADE |
| buyer_id | users(id) | RESTRICT | CASCADE |
| seller_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(order_code)`.
- `UNIQUE(checkout_group_id,sale_seller_key)` where `sale_seller_key` is generated.
- Borrow uniqueness is `UNIQUE(checkout_group_id,lend_listing_id)` on `borrow_orders`.

### Indexes
- `(buyer_id,status,created_at,id)`.
- `(seller_id,status,created_at,id)`.
- `(checkout_group_id,order_type)`.
- `(order_type,status,created_at,id)`.

### Check Constraints
- `order_type='SALE'` ⇒ seller non-NULL; `order_type='BORROW'` ⇒ seller NULL.
- Order status allowlist: `PENDING_PAYMENT, CONFIRMED, PROCESSING, COMPLETED, CANCELLED, DISPUTED`.
- Currency VND; amounts nonnegative and total arithmetic policy: [NEEDS CONFIRMATION].

### Generated Columns
- `sale_seller_key` STORED: `CASE WHEN order_type = 'SALE' THEN seller_id ELSE NULL END`; unique with checkout_group_id to ensure at most one SALE order/seller/checkout.

### Business Rules
- A checkout produces at most one SALE order per seller and one BORROW order per lend listing.
- Borrow lender is `borrow_orders.lender_id`; `orders.seller_id` is NULL.
- Snapshot fields do not change after order confirmation.

## 30. `sale_order_items`

### Purpose
One sold physical copy per order line.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Line |
| order_id | ID | NO | — | FK | Sale order |
| sale_listing_id | ID | NO | — | FK | Listing |
| book_id | ID | NO | — | FK | Physical copy |
| seller_id | ID | NO | — | FK | Seller snapshot/reference |
| combo_order_item_id | ID | YES | NULL | FK | Optional combo parent |
| title_snapshot | VARCHAR(500) | NO | — | | Title at checkout |
| condition_snapshot | VARCHAR(30) | NO | — | | Condition at checkout |
| unit_price | MONEY | NO | — | | Unit price snapshot |
| combo_allocated_amount | MONEY | YES | NULL | | Combo net allocation |
| discount_allocated | MONEY | NO | 0 | | Allocated discount |
| quantity | SMALLINT UNSIGNED | NO | 1 | | Must remain one physical copy |
| subtotal | MONEY | NO | — | | Line total |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| order_id | orders(id) | RESTRICT | CASCADE |
| sale_listing_id | sale_listings(id) | RESTRICT | CASCADE |
| book_id | books(id) | RESTRICT | CASCADE |
| seller_id | users(id) | RESTRICT | CASCADE |
| combo_order_item_id | sale_combo_order_items(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(order_id,sale_listing_id)`.
- `UNIQUE(id,order_id)` for order-scoped refund relation if required.

### Indexes
- `(order_id,seller_id)`.
- `(seller_id,created_at)`.
- `(sale_listing_id)`, `(book_id)`, `(combo_order_item_id)`.

### Check Constraints
- `quantity=1`.
- Amounts nonnegative; combo allocated amount non-NULL iff combo parent is non-NULL: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- `seller_id` and `book_id` must match sale listing; service invariant unless composite FKs are added.
- Item price/title/condition are snapshots.

## 31. `sale_combo_order_items`

### Purpose
Immutable combo purchase snapshot; parent of constituent sale lines.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Combo order line |
| order_id | ID | NO | — | FK | Parent SALE order |
| combo_id | ID | NO | — | FK | Source combo |
| seller_id | ID | NO | — | FK | Seller |
| combo_name_snapshot | VARCHAR(255) | NO | — | | Name snapshot |
| combo_price_snapshot | MONEY | NO | — | | Listed price snapshot |
| combo_discount_snapshot | MONEY | NO | 0 | | Discount |
| combo_net_amount | MONEY | NO | — | | Net payable for combo |
| currency | CHAR(3) | NO | VND | | Currency |
| rounding_policy_version | VARCHAR(30) | NO | [NEEDS CONFIRMATION] | | Allocation algorithm version |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| order_id | orders(id) | RESTRICT | CASCADE |
| combo_id | sale_combos(id) | RESTRICT | CASCADE |
| seller_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `(order_id,combo_id)` uniqueness: [NEEDS CONFIRMATION] (same combo twice in one order allowed or not).

### Indexes
- `(order_id)`; `(combo_id,created_at)`.

### Check Constraints
- `combo_price_snapshot >= combo_discount_snapshot >= 0`.
- `combo_net_amount = combo_price_snapshot - combo_discount_snapshot`.
- `currency='VND'`.

### Generated Columns
- None.

### Business Rules
- Sum of constituent `combo_allocated_amount` equals combo net amount after rounding.
- Allocation and rounding policy are immutable.

## 32. `borrow_orders`

### Purpose
Borrow contract, return lifecycle, and deposit accounting state.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Borrow obligation |
| order_id | ID | NO | — | UQ, FK | BORROW order |
| checkout_group_id | ID | NO | — | FK | Checkout |
| lend_listing_id | ID | NO | — | FK | Lend offer |
| lender_id | ID | NO | — | FK | Recipient/lender |
| borrower_id | ID | NO | — | FK | Borrower |
| status | VARCHAR(30) | NO | PENDING | | Borrow lifecycle |
| borrow_terms_snapshot | JSON | NO | — | | Terms at checkout |
| borrow_start_at | UTC_TS | YES | NULL | | Start |
| borrow_due_at | UTC_TS | YES | NULL | | Due |
| returned_at | UTC_TS | YES | NULL | | Accepted return |
| rental_fee | MONEY | NO | — | | Rental charge |
| deposit_amount | MONEY | NO | 0 | | Collected/required deposit |
| deposit_refunded_amount | MONEY | NO | 0 | | Refunded deposit |
| deposit_forfeited_amount | MONEY | NO | 0 | | Forfeited amount |
| late_fee_amount | MONEY | NO | 0 | | Assessed late fee |
| return_requested_by | ID | YES | NULL | FK | Requester |
| return_status | VARCHAR(20) | YES | NULL | | Return substate |
| return_method | VARCHAR(30) | YES | NULL | | Return method snapshot |
| return_tracking_code | VARCHAR(100) | YES | NULL | | Return tracking |
| return_requested_at | UTC_TS | YES | NULL | | Request time |
| return_approved_at | UTC_TS | YES | NULL | | Approval time |
| return_notes | TEXT | YES | NULL | | Return notes |
| currency | CHAR(3) | NO | VND | | Currency |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| order_id | orders(id) | RESTRICT | CASCADE |
| checkout_group_id | checkout_groups(id) | RESTRICT | CASCADE |
| lend_listing_id | lend_listings(id) | RESTRICT | CASCADE |
| lender_id | users(id) | RESTRICT | CASCADE |
| borrower_id | users(id) | RESTRICT | CASCADE |
| return_requested_by | users(id) | SET NULL | CASCADE |

### Unique Constraints
- `UNIQUE(order_id)`.
- `UNIQUE(checkout_group_id,lend_listing_id)`.
- `UNIQUE(id,order_id)` for order-scoped refund reference.

### Indexes
- `(lender_id,status,borrow_due_at)`.
- `(borrower_id,status,created_at)`.
- `(lend_listing_id,status)`.

### Check Constraints
- Amounts nonnegative; `deposit_refunded_amount + deposit_forfeited_amount <= deposit_amount`.
- `borrow_due_at > borrow_start_at` when both non-NULL.
- Currency VND; status/return status allowlists: [NEEDS CONFIRMATION].
- Order must be BORROW and lender must match listing: service invariant or composite FK.

### Generated Columns
- None.

### Business Rules
- Borrow terms, rent, deposit, late fee policy, return policy and lender are checkout snapshots.
- Deposit is liability until refunded/forfeited; it is not automatically lender revenue.
- Deposit is a liability until valid forfeiture. In v1 the default beneficiary is lender. Forfeiture reclassifies already collected deposit and creates no new buyer cash IN; any subsequent transfer to lender uses payout/financial-transaction logic.

## 33. `payments`

### Purpose
Buyer payment attempts for a checkout group; never seller payout.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Payment attempt |
| checkout_group_id | ID | NO | — | FK | Checkout |
| payer_id | ID | NO | — | FK | Buyer |
| provider | VARCHAR(50) | NO | — | | Provider |
| payment_method | VARCHAR(30) | NO | — | | Method |
| provider_transaction_code | VARCHAR(150) | YES | NULL | UQ | Provider reference |
| payment_purpose | VARCHAR(30) | NO | CHECKOUT | | Checkout charge classification |
| amount | MONEY | NO | — | | Charged amount |
| currency | CHAR(3) | NO | VND | | Currency |
| status | VARCHAR(20) | NO | PENDING | | Attempt state |
| idempotency_key | VARCHAR(128) | NO | — | UQ | Request idempotency |
| paid_at | UTC_TS | YES | NULL | | Successful payment time |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| checkout_group_id | checkout_groups(id) | RESTRICT | CASCADE |
| payer_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(provider,provider_transaction_code)` where reference is non-NULL.
- `UNIQUE(provider,idempotency_key)`.

### Indexes
- `(checkout_group_id,status,created_at)`.
- `(payer_id,paid_at)`.

### Check Constraints
- `amount > 0`; currency VND.
- Status exactly `PENDING, PROCESSING, PAID, FAILED, REFUNDED, REVERSED, CANCELLED`; `PAID` is successful final payment.
- Paid status requires `paid_at`.

### Generated Columns
- None.

### Business Rules
- Payment callbacks are idempotent.
- Multiple successful payment attempts jointly funding one checkout group: [NEEDS CONFIRMATION].

## 34. `payment_allocations`

### Purpose
Allocate completed buyer payment amounts to split orders and payment purposes.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Allocation |
| payment_id | ID | NO | — | FK | Payment |
| order_id | ID | NO | — | FK | Allocated order |
| allocation_type | VARCHAR(20) | NO | — | | SALE/RENT/DEPOSIT/SHIPPING/OTHER |
| amount | MONEY | NO | — | | Allocated amount |
| currency | CHAR(3) | NO | VND | | Currency |
| idempotency_key | VARCHAR(128) | NO | — | UQ | Allocation retry identity |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| payment_id | payments(id) | RESTRICT | CASCADE |
| order_id | orders(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(payment_id,order_id,allocation_type)`.
- `UNIQUE(idempotency_key)`.

### Indexes
- `(payment_id)`; `(order_id,allocation_type)`.

### Check Constraints
- Type exactly `SALE, RENT, DEPOSIT, SHIPPING, OTHER`.
- `amount > 0`; currency VND.

### Generated Columns
- None.

### Business Rules
- Payment and order must belong to the same checkout group; currency must match.
- Payment `PAID` requires allocations whose sum equals payment amount. `PENDING`/`PROCESSING` allocations are not completed; `FAILED`/`CANCELLED` contribute nothing to completed allocations. `REFUNDED`/`REVERSED` leave original allocations immutable; refunds/reversals are represented in `refunds` and `financial_transactions`.
- `payment_allocations` intentionally has no status column; completion is derived from payment status. Do not add an allocation status.
- Deposit allocation is liability, never automatic seller revenue.
- SUM equality and preventing allocations above payment amount are service transaction invariants, not single-row CHECKs.

## 35. `shipments`

### Purpose
One shipment/parcel belonging to an order.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Shipment |
| order_id | ID | NO | — | FK | Parent order |
| carrier | VARCHAR(100) | YES | NULL | | Carrier |
| tracking_code | VARCHAR(150) | YES | NULL | | Tracking code |
| shipping_fee | MONEY | NO | 0 | | Fee |
| status | VARCHAR(20) | NO | [NEEDS CONFIRMATION] | | Shipment state |
| shipped_at | UTC_TS | YES | NULL | | Ship time |
| delivered_at | UTC_TS | YES | NULL | | Delivery time |
| currency | CHAR(3) | NO | VND | | Currency |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| order_id | orders(id) | RESTRICT | CASCADE |

### Unique Constraints
- Tracking uniqueness/scope: [NEEDS CONFIRMATION].

### Indexes
- `(order_id,status)`; `(tracking_code)`.

### Check Constraints
- Fee >= 0; currency VND; delivered timestamp not before shipped.
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Multiple shipments per order are allowed by this candidate.

## 36. `shipment_tracking`

### Purpose
Append-only shipment status events.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Tracking event |
| shipment_id | ID | NO | — | FK | Shipment |
| status | VARCHAR(30) | NO | — | | Carrier/status event |
| location | VARCHAR(255) | YES | NULL | | Location |
| description | TEXT | YES | NULL | | Details |
| occurred_at | UTC_TS | NO | — | | Event time |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Recorded time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| shipment_id | shipments(id) | RESTRICT | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(shipment_id,occurred_at,id)`.

### Check Constraints
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Tracking history is append-only; shipments with history cannot be hard-deleted.

## 7. Return, refund, coupon

## 37. `returns`

### Purpose
Sale-item return case only. Borrow returns belong to `borrow_orders`.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Return |
| order_id | ID | NO | — | FK | SALE order |
| sale_order_item_id | ID | NO | — | FK | Returned line |
| reason | VARCHAR(100) | NO | — | | Reason |
| description | TEXT | YES | NULL | | Details |
| status | VARCHAR(20) | NO | REQUESTED | | Lifecycle |
| requested_by | ID | NO | — | FK | Requesting user |
| requested_at | UTC_TS | NO | — | | Request time |
| approved_at | UTC_TS | YES | NULL | | Approval |
| completed_at | UTC_TS | YES | NULL | | Completion |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| order_id | orders(id) | RESTRICT | CASCADE |
| sale_order_item_id | sale_order_items(id) | RESTRICT | CASCADE |
| requested_by | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- Unique active/open return per item requires generated predicate over statuses; exact status set/predicate [NEEDS CONFIRMATION].

### Indexes
- `(order_id,status,requested_at)`.
- `(sale_order_item_id,status)`.

### Check Constraints
- Return status allowlist: [NEEDS CONFIRMATION].
- Composite relationship item belongs to order; use composite FK or service invariant.

### Generated Columns
- Open-return key expression depends on confirmed open statuses: [NEEDS CONFIRMATION].

### Business Rules
- Sale return is separate from borrow return.

## 38. `refunds`

### Purpose
Buyer refund request/provider execution tied to an exact payment allocation.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Refund |
| order_id | ID | NO | — | FK | Order |
| payment_allocation_id | ID | NO | — | FK | Source allocation |
| sale_order_item_id | ID | YES | NULL | FK | Optional sale item target |
| borrow_order_id | ID | YES | NULL | FK | Optional borrow target |
| return_id | ID | YES | NULL | FK | Optional sale return case |
| requested_by | ID | YES | NULL | FK | Requester |
| provider | VARCHAR(50) | NO | — | | Refund provider |
| provider_refund_reference | VARCHAR(150) | YES | NULL | UQ | Provider refund ID |
| idempotency_key | VARCHAR(128) | NO | — | UQ | Refund retry identity |
| reason | VARCHAR(100) | NO | — | | Refund reason |
| amount | MONEY | NO | — | | Refund amount |
| currency | CHAR(3) | NO | VND | | Currency |
| status | VARCHAR(20) | NO | REQUESTED | | Refund lifecycle |
| requested_at | UTC_TS | NO | — | | Request time |
| approved_at | UTC_TS | YES | NULL | | Approval |
| completed_at | UTC_TS | YES | NULL | | Provider completion |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| order_id | orders(id) | RESTRICT | CASCADE |
| payment_allocation_id | payment_allocations(id) | RESTRICT | CASCADE |
| sale_order_item_id | sale_order_items(id) | RESTRICT | CASCADE |
| borrow_order_id | borrow_orders(id) | RESTRICT | CASCADE |
| return_id | returns(id) | RESTRICT | CASCADE |
| requested_by | users(id) | SET NULL | CASCADE |

### Unique Constraints
- `UNIQUE(provider,provider_refund_reference)` where provider ref non-NULL.
- `UNIQUE(provider,idempotency_key)`.

### Indexes
- `(order_id,status,created_at)`.
- `(payment_allocation_id,status)`.
- `(return_id)`.

### Check Constraints
- `amount > 0`; currency VND.
- At most one sale-item/borrow target.
- Refund allocation/order/target relationships must agree.
- Status allowlist: [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Completed refunds are immutable.
- Cumulative completed refunds cannot exceed refundable allocation.
- Refund completion creates a new financial transaction/reversal; never edits a completed transaction.
- Whether order-level refunds with both optional item targets NULL are allowed: [NEEDS CONFIRMATION].

## 39. `coupons`

### Purpose
Discount policy scoped globally or to seller/listing/category.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Coupon |
| seller_id | ID | YES | NULL | FK | Optional seller owner |
| code | VARCHAR(64) | NO | — | UQ | Redeem code |
| name | VARCHAR(150) | NO | — | | Name |
| description | TEXT | YES | NULL | | Details |
| discount_type | VARCHAR(20) | NO | — | | PERCENT/FIXED_AMOUNT |
| discount_rate | RATE | YES | NULL | | Percent rate |
| fixed_discount_amount | MONEY | YES | NULL | | Fixed VND amount |
| min_order_amount | MONEY | YES | NULL | | Minimum |
| max_discount_amount | MONEY | YES | NULL | | Cap |
| currency | CHAR(3) | YES | NULL | | Required for fixed/min/max money |
| usage_limit | INT UNSIGNED | YES | NULL | | Global limit |
| usage_per_user | INT UNSIGNED | YES | NULL | | User limit |
| start_at | UTC_TS | NO | — | | Start |
| end_at | UTC_TS | NO | — | | End |
| status | VARCHAR(20) | NO | ACTIVE | | State |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation time |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| seller_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(code)`; normalization/collation [NEEDS CONFIRMATION].

### Indexes
- `(status,start_at,end_at)`.
- `(seller_id,status)`.

### Check Constraints
- Type exactly PERCENT/FIXED_AMOUNT.
- PERCENT requires rate and no fixed amount; FIXED_AMOUNT requires fixed amount and no rate.
- Percent range, amount caps, and nullable currency semantics: [NEEDS CONFIRMATION].
- `end_at > start_at`; limits NULL or positive.

### Generated Columns
- None.

### Business Rules
- Coupon application and discount are snapshotted in checkout/orders.
- Coupon usage counts once per checkout group.

## 40. `coupon_listings`

### Purpose
Coupon-to-listing scope.

### Columns
`coupon_id ID!` (PK, FK); `sale_listing_id ID!` (PK, FK); `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| coupon_id | coupons(id) | CASCADE | CASCADE |
| sale_listing_id | sale_listings(id) | RESTRICT | CASCADE |

### Unique Constraints
- Composite PK `(coupon_id,sale_listing_id)`.

### Indexes
- PK index; `(sale_listing_id,coupon_id)`.

### Check Constraints
- None.

### Generated Columns
- None.

### Business Rules
- Listing must satisfy seller/currency coupon policy; service validation.

## 41. `coupon_categories`

### Purpose
Coupon-to-category scope.

### Columns
`coupon_id ID!` (PK, FK); `category_id ID!` (PK, FK); `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| coupon_id | coupons(id) | CASCADE | CASCADE |
| category_id | categories(id) | RESTRICT | CASCADE |

### Unique Constraints
- Composite PK `(coupon_id,category_id)`.

### Indexes
- PK index; `(category_id,coupon_id)`.

### Check Constraints
- None.

### Generated Columns
- None.

### Business Rules
- Category eligibility is evaluated from the order item snapshot/catalog relation.

## 42. `coupon_usages`

### Purpose
One coupon redemption per user/checkout group.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Usage |
| coupon_id | ID | NO | — | FK | Coupon |
| user_id | ID | NO | — | FK | Redeemer |
| checkout_group_id | ID | NO | — | FK | Checkout redemption scope |
| discount_amount | MONEY | NO | — | | Applied discount |
| currency | CHAR(3) | NO | VND | | Currency |
| used_at | UTC_TS | NO | — | | Redemption time |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| coupon_id | coupons(id) | RESTRICT | CASCADE |
| user_id | users(id) | RESTRICT | CASCADE |
| checkout_group_id | checkout_groups(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(coupon_id,user_id,checkout_group_id)`.

### Indexes
- Unique redemption index; `(user_id,used_at)`.

### Check Constraints
- Discount nonnegative; currency VND.

### Generated Columns
- None.

### Business Rules
- Coupon usage cap is locked and checked atomically at checkout.

## 8. Social, messaging, notification, moderation

## 43. `favorites`

### Purpose
User’s favorite book or offer.

### Columns
`id ID! PK`; `user_id ID! FK`; `book_id ID? FK`; `sale_listing_id ID? FK`; `lend_listing_id ID? FK`; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3).

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| user_id | users(id) | RESTRICT | CASCADE |
| book_id | books(id) | RESTRICT | CASCADE |
| sale_listing_id | sale_listings(id) | RESTRICT | CASCADE |
| lend_listing_id | lend_listings(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(user_id,book_id)`, `UNIQUE(user_id,sale_listing_id)`, `UNIQUE(user_id,lend_listing_id)`. Multiple NULLs are permitted; XOR requires exactly one non-NULL target.

### Indexes
- `(user_id,created_at,id)`; unique target indexes.

### Check Constraints
- Exactly one target non-NULL.

### Generated Columns
- None required; the three target-specific unique indexes and XOR CHECK enforce no duplicates.

### Business Rules
- Duplicate favorite for same user and target is not allowed.

## 44. `conversations`

### Purpose
Conversation container.

### Columns
`id ID! PK`; `conversation_type VARCHAR(20)!` default [NEEDS CONFIRMATION]; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`; `updated_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)`.

### Foreign Keys
- None.

### Unique Constraints
- None specified.

### Indexes
- `(updated_at,id)`.

### Check Constraints
- Conversation type allowed values [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Membership is represented in `conversation_members`.

## 45. `conversation_members`

### Purpose
Conversation membership and read position.

### Columns
`conversation_id ID!`; `user_id ID!`; `joined_at UTC_TS!`; `last_read_at UTC_TS?`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| conversation_id | conversations(id) | RESTRICT | CASCADE |
| user_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- Composite PK `(conversation_id,user_id)`.

### Indexes
- PK index; `(user_id,last_read_at)`.

### Check Constraints
- None.

### Generated Columns
- None.

### Business Rules
- Membership is the authority for message sender authorization.

## 46. `messages`

### Purpose
Conversation messages and optional attachment.

### Columns
`id ID! PK`; `conversation_id ID! FK`; `sender_id ID! FK`; `message_type VARCHAR(20)!`; `content TEXT!`; `attachment_url VARCHAR(2048)?`; `sent_at UTC_TS!`; `edited_at UTC_TS?`; `deleted_at UTC_TS?`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| conversation_id | conversations(id) | RESTRICT | CASCADE |
| sender_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(conversation_id,sent_at,id)`; `(sender_id,sent_at)`.

### Check Constraints
- Message type allowlist [NEEDS CONFIRMATION].
- edited/deleted timestamps cannot precede sent time.

### Generated Columns
- None.

### Business Rules
- Sender must be a conversation member; service invariant checked transactionally.

## 47. `notifications`

### Purpose
In-app notification with optional polymorphic entity reference.

### Columns
`id ID! PK`; `user_id ID! FK`; `notification_type VARCHAR(50)!`; `title VARCHAR(255)!`; `content TEXT!`; `entity_type VARCHAR(50)?`; `entity_id ID?`; `is_read BOOLEAN!=FALSE`; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| user_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(user_id,is_read,created_at,id)`.

### Check Constraints
- Entity type and ID are both NULL or both non-NULL.

### Generated Columns
- None.

### Business Rules
- Polymorphic entity reference is best-effort; it is not a hard FK.

## 48. `notification_deliveries`

### Purpose
Delivery state per notification/channel.

### Columns
`id ID! PK`; `notification_id ID! FK`; `channel VARCHAR(20)!`; `status VARCHAR(20)!` default PENDING; `delivered_at UTC_TS?`; `read_at UTC_TS?`; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| notification_id | notifications(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(notification_id,channel)`.

### Indexes
- `(status,created_at)`; unique key.

### Check Constraints
- Channel/status allowlists [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Delivery rows are operational delivery state; notification itself remains authoritative content.

## 49. `reviews`

### Purpose
Review after a completed sale or borrow order.

### Columns
`id ID! PK`; `reviewer_id ID! FK`; `order_id ID! FK`; `sale_listing_id ID? FK`; `lend_listing_id ID? FK`; `rating TINYINT UNSIGNED!`; `comment TEXT?`; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`; `updated_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| reviewer_id | users(id) | RESTRICT | CASCADE |
| order_id | orders(id) | RESTRICT | CASCADE |
| sale_listing_id | sale_listings(id) | RESTRICT | CASCADE |
| lend_listing_id | lend_listings(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(order_id,reviewer_id)`.

### Indexes
- `(sale_listing_id,created_at)`; `(lend_listing_id,created_at)`.

### Check Constraints
- Exactly one sale/lend target; `rating BETWEEN 1 AND 5`.

### Generated Columns
- None.

### Business Rules
- Reviewer must be order buyer; order must be completed; target must belong to order. These are service/composite-FK invariants.

## 50. `reports`

### Purpose
Moderation report on one target.

### Columns
`id ID! PK`; `reporter_id ID! FK`; `reported_user_id ID? FK`; `book_id ID? FK`; `sale_listing_id ID? FK`; `lend_listing_id ID? FK`; `message_id ID? FK`; `reason VARCHAR(100)!`; `description TEXT?`; `status VARCHAR(20)!` default OPEN; `handled_by ID? FK`; `resolution_note TEXT?`; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`; `resolved_at UTC_TS?`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| reporter_id | users(id) | RESTRICT | CASCADE |
| reported_user_id | users(id) | RESTRICT | CASCADE |
| book_id | books(id) | RESTRICT | CASCADE |
| sale_listing_id | sale_listings(id) | RESTRICT | CASCADE |
| lend_listing_id | lend_listings(id) | RESTRICT | CASCADE |
| message_id | messages(id) | RESTRICT | CASCADE |
| handled_by | users(id) | SET NULL | CASCADE |

### Unique Constraints
- None specified.

### Indexes
- `(status,created_at)`; `(reported_user_id,status)`; indexes for each target FK.

### Check Constraints
- Exactly one target among user/book/sale/lend/message.
- Status allowlist [NEEDS CONFIRMATION].
- Resolved status requires `resolved_at`.

### Generated Columns
- None.

### Business Rules
- A report has exactly one target. Audit history is retained.

## 9. Financial and settlement

## 51. `platform_fees`

### Purpose
Fee assessment and policy snapshot. It is not automatically a cash movement.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Fee assessment |
| order_id | ID | NO | — | FK | Order |
| sale_order_item_id | ID | YES | NULL | FK | Optional sale item scope |
| borrow_order_id | ID | YES | NULL | FK | Optional borrow scope |
| payment_id | ID | YES | NULL | FK | Optional payment fee scope |
| recipient_user_id | ID | NO | — | FK | User whose proceeds are associated with fee base; not fee beneficiary |
| fee_type | VARCHAR(30) | NO | — | | SALE_COMMISSION/PAYMENT_FEE/OTHER |
| fee_rate | RATE | YES | NULL | | Applied rate |
| fee_base | MONEY | NO | — | | Calculation base |
| fee_amount | MONEY | NO | — | | Assessed fee |
| currency | CHAR(3) | NO | VND | | Fee currency |
| charged_to | VARCHAR(20) | NO | — | | BUYER/SELLER/PLATFORM |
| cash_impact | BOOLEAN | NO | FALSE | | Whether this row is actual cash movement |
| status | VARCHAR(20) | NO | [NEEDS CONFIRMATION] | | Assessment/reversal state |
| fee_policy_snapshot | JSON | NO | — | | Immutable fee policy |
| idempotency_key | VARCHAR(128) | NO | — | UQ | Assessment retry key |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| order_id | orders(id) | RESTRICT | CASCADE |
| sale_order_item_id | sale_order_items(id) | RESTRICT | CASCADE |
| borrow_order_id | borrow_orders(id) | RESTRICT | CASCADE |
| payment_id | payments(id) | RESTRICT | CASCADE |
| recipient_user_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(idempotency_key)`.

### Indexes
- `(recipient_user_id,status,created_at)`.
- `(order_id,fee_type)`.
- `(sale_order_item_id)`, `(borrow_order_id)`, `(payment_id)`.

### Check Constraints
- Fee type allowlist; `fee_base>=0`, `fee_amount>=0`; rate NULL or nonnegative; currency VND.
- Scope is one of sale item, borrow order, payment, or order-level fee; fee-type-specific scope restrictions: [NEEDS CONFIRMATION].
- `charged_to` exactly `BUYER,SELLER,PLATFORM`.
- Fee status allowlist [NEEDS CONFIRMATION].
- `charged_to=BUYER`: fee must be included in checkout/payment snapshot; it may use allocation type OTHER if no dedicated type applies. It does not create a second BUYER_PAYMENT cash inflow.
- `charged_to=SELLER`: fee is deducted from seller/lender proceeds; it is attribution, not another buyer cash collection.
- `charged_to=PLATFORM`: platform bears/subsidizes the fee; this is neither buyer nor seller collection.
- `cash_impact=TRUE` only when this fee row corresponds to a separate actual cash movement. Otherwise FALSE.

### Generated Columns
- None.

### Business Rules
- `recipient_user_id` always identifies the user whose proceeds are related to the fee base, usually seller/lender; it is not the fee beneficiary.
- `charged_to=BUYER` is included in checkout/payment pricing snapshot.
- `charged_to=SELLER` is withheld from seller/lender proceeds and creates no additional buyer cash IN.
- `charged_to=PLATFORM` is platform-funded/subsidized, not collected from buyer or seller.
- `PLATFORM` means Passbook bears/subsidizes the amount; this is not buyer or seller collection.
- Fee assessment and cash movement remain separate; the `financial_transactions` mapping below determines actual cash impact.

## 52. `seller_payout_accounts`

### Purpose
Seller/lender payout destination with tokenized or encrypted reference.

### Columns
`id ID! PK`; `user_id ID! FK`; `provider VARCHAR(50)!`; `account_type VARCHAR(30)!`; `account_name VARCHAR(150)!`; `account_token VARCHAR(512)!`; `account_last4 CHAR(4)?`; `bank_code VARCHAR(50)?`; `version INT UNSIGNED!` default 1; `is_default BOOLEAN!` default FALSE; `verification_status VARCHAR(20)!` default [NEEDS CONFIRMATION]; `status VARCHAR(20)!` default ACTIVE; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`; `updated_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| user_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(default_active_account_user_key)`; generated column is STORED.
- Provider-scoped token uniqueness: [NEEDS CONFIRMATION].

### Indexes
- `(user_id,status,verification_status)`.

### Check Constraints
- Version >0; status and verification allowlists [NEEDS CONFIRMATION].
- Account token must not be raw plaintext bank credential; this cannot be guaranteed by SQL.

### Generated Columns
- `default_active_account_user_key` STORED: `CASE WHEN is_default=1 AND status='ACTIVE' THEN user_id ELSE NULL END`.

### Business Rules
- Payout snapshots preserve destination at transfer time; never reconstruct paid payout from current account row.
- Token encryption/key management is an infrastructure/service invariant.

## 53. `seller_payouts`

### Purpose
One payout obligation per order and recipient. A provider transfer attempt is not a new obligation.

### Columns

| Column | Type | Null | Default | Key | Description |
|---|---|---:|---|---|---|
| id | ID | NO | — | PK | Payout obligation |
| order_id | ID | NO | — | UQ, FK | Source order |
| recipient_user_id | ID | NO | — | FK | Seller for SALE, lender for BORROW |
| payout_account_id | ID | NO | — | FK | Account used |
| provider_snapshot | VARCHAR(50) | NO | — | | Provider snapshot |
| account_type_snapshot | VARCHAR(30) | NO | — | | Account type |
| account_name_snapshot | VARCHAR(150) | NO | — | | Name |
| account_reference_snapshot | VARCHAR(512) | NO | — | | Encrypted/tokenized provider reference required for payout retry |
| account_last4_snapshot | CHAR(4) | YES | NULL | | Masked account |
| bank_code_snapshot | VARCHAR(50) | YES | NULL | | Bank |
| account_version_snapshot | INT UNSIGNED | NO | — | | Version |
| gross_amount | MONEY | NO | — | | Gross proceeds |
| platform_fee_amount | MONEY | NO | 0 | | Deducted fee |
| refund_amount | MONEY | NO | 0 | | Refund share deducted |
| net_amount | MONEY | NO | — | | Payable amount |
| currency | CHAR(3) | NO | VND | | Currency |
| status | VARCHAR(20) | NO | PENDING | | Obligation lifecycle |
| eligible_at | UTC_TS | YES | NULL | | Eligibility |
| processing_at | UTC_TS | YES | NULL | | Processing start |
| processed_at | UTC_TS | YES | NULL | | Processing result time |
| paid_at | UTC_TS | YES | NULL | | Paid time |
| provider_reference | VARCHAR(150) | YES | NULL | | Successful/latest reference |
| failure_reason | TEXT | YES | NULL | | Last failure |
| idempotency_key | VARCHAR(128) | NO | — | UQ | Obligation creation key |
| created_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) | | Creation |
| updated_at | UTC_TS | NO | CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) | | Update |

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| order_id | orders(id) | RESTRICT | CASCADE |
| recipient_user_id | users(id) | RESTRICT | CASCADE |
| payout_account_id | seller_payout_accounts(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(order_id)` — one obligation/order.
- `UNIQUE(idempotency_key)`.
- Provider transfer reference is recorded on each `financial_transactions` attempt; uniqueness is provider-scoped there. The payout-level `provider_reference` is the successful/final reference and is not the attempt history.

### Indexes
- `(recipient_user_id,status,created_at)`.
- `(status,eligible_at)`.
- `(status,paid_at)`.

### Check Constraints
- Amounts nonnegative; `net_amount=gross_amount-platform_fee_amount-refund_amount` subject to adjustments policy.
- Currency VND.
- Status exactly `PENDING,ELIGIBLE,PROCESSING,PAID,FAILED,CANCELLED`.
- PAID requires `paid_at`; PROCESSING requires `processing_at`.

### Generated Columns
- None.

### Business Rules
- SALE recipient is order seller; BORROW recipient is lender.
- `UNIQUE(order_id)` stays: one payout obligation per order. Retries do not create payout obligations.
- Provider transfer failure transitions payout `PROCESSING → FAILED`; retry transitions `FAILED → PROCESSING`. Each attempt is a separate `financial_transactions` row with `transaction_type=SELLER_PAYOUT`, `payout_id`, provider, reference, status, amount, idempotency key, and event history.
- Payout eligibility waits for fulfillment, return window, and dispute checks.
- `account_reference_snapshot` is an encrypted/tokenized provider reference required for retries. Never store raw bank credentials, passwords, or PINs.
- A PAID payout and its destination snapshot are immutable.

## 54. `financial_transactions`

### Purpose
Operational financial transaction/audit ledger. **Not double-entry accounting.**

### Columns
`id ID! PK`; `transaction_code VARCHAR(64)! UQ`; `idempotency_key VARCHAR(128)! UQ`; `checkout_group_id ID? FK`; `order_id ID? FK`; `payment_id ID? FK`; `payment_allocation_id ID? FK`; `payout_id ID? FK`; `platform_fee_id ID? FK`; `refund_id ID? FK`; `payout_adjustment_id ID? FK`; `borrow_order_id ID? FK`; `recipient_user_id ID? FK`; `user_id ID? FK`; `provider VARCHAR(50)?`; `provider_reference VARCHAR(150)?`; `transaction_type VARCHAR(40)!`; `direction VARCHAR(3)!`; `amount MONEY!`; `currency CHAR(3)!`; `cash_impact BOOLEAN!`; `status VARCHAR(20)!`; `reference_code VARCHAR(150)?`; `description VARCHAR(1000)?`; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`; `completed_at UTC_TS?`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| checkout_group_id | checkout_groups(id) | RESTRICT | CASCADE |
| order_id | orders(id) | RESTRICT | CASCADE |
| payment_id | payments(id) | RESTRICT | CASCADE |
| payment_allocation_id | payment_allocations(id) | RESTRICT | CASCADE |
| payout_id | seller_payouts(id) | RESTRICT | CASCADE |
| platform_fee_id | platform_fees(id) | RESTRICT | CASCADE |
| refund_id | refunds(id) | RESTRICT | CASCADE |
| payout_adjustment_id | seller_payout_adjustments(id) | RESTRICT | CASCADE |
| borrow_order_id | borrow_orders(id) | RESTRICT | CASCADE |
| recipient_user_id | users(id) | RESTRICT | CASCADE |
| user_id | users(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(transaction_code)`.
- `UNIQUE(idempotency_key)`.
- `UNIQUE(provider,transaction_type,provider_reference)` where provider reference is non-NULL; exact scope [NEEDS CONFIRMATION].

### Indexes
- `(status,created_at)`.
- `(transaction_type,status,completed_at)`.
- `(recipient_user_id,transaction_type,completed_at)`.
- `(order_id,created_at)`.
- `(payment_id)`, `(payout_id)`, `(refund_id)`.

### Check Constraints
- `amount > 0`; currency VND; direction IN/OUT; status allowlist.
- Completed status requires `completed_at`.
- Type/source/direction/cash-impact mapping below; rows with wrong source must fail.

### Generated Columns
- None.

### Transaction Type Mapping

| Transaction type | Required source | Direction | `cash_impact` | Notes |
|---|---|---|---:|---|
| BUYER_PAYMENT | `payment_id` | IN | TRUE | Actual successful buyer funds received |
| PLATFORM_FEE | `platform_fee_id` | IN attribution for buyer/seller-borne fee; OUT attribution for platform-funded subsidy | TRUE only for a separate actual cash movement; otherwise FALSE | Direction is not itself proof of cash movement. Buyer-paid fee is already in checkout/payment; seller-paid fee is deducted from proceeds |
| SELLER_PAYOUT | `payout_id` | OUT | TRUE only for successful actual transfer; failed attempt is non-cash | One row per attempt; provider/ref/status/amount audited |
| REFUND | `refund_id` | OUT | TRUE when funds actually returned | Must not exceed refundable allocation |
| PAYMENT_REVERSAL | `payment_id` | OUT | TRUE only if settled funds are returned | Authorization void with no cash movement is provider/event history, not cash flow |
| PAYMENT_PROCESSOR_FEE | `payment_id` | OUT | TRUE when processor actually charges | Provider charge reconciliation |
| SELLER_PAYOUT_ADJUSTMENT | `payout_adjustment_id` | IN for cash recovery; OUT for cash credit or non-cash offset attribution | TRUE for cash movement; FALSE for internal offset | Direction depends on adjustment execution |
| DEPOSIT_FORFEITURE | `borrow_order_id` | OUT attribution | FALSE for reclassification of already collected deposit | Beneficiary defaults to lender; no new buyer cash IN; a later lender transfer is SELLER_PAYOUT |

### Business Rules
- A transaction must reference only source tables valid for its type. Type-to-source CHECK/service validation must enforce unrelated source FKs are NULL.
- Dashboard cash flow filters `cash_impact=TRUE` and completed status.
- Platform fee revenue is calculated from fee assessments/reversals, not by adding seller-paid fee to buyer cash IN.
- Status/source/type rows are immutable once completed; corrections create reversal/adjustment rows.
- This table has no accounts or debit/credit lines and must not be called double-entry accounting.

## 55. `financial_transaction_events`

### Purpose
Append-only provider/internal transaction lifecycle events.

### Columns
`id ID! PK`; `financial_transaction_id ID! FK`; `provider VARCHAR(50)?`; `provider_event_id VARCHAR(150)?`; `event_type VARCHAR(40)!`; `from_status VARCHAR(20)?`; `to_status VARCHAR(20)!`; `actor_user_id ID? FK`; `details JSON?`; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| financial_transaction_id | financial_transactions(id) | RESTRICT | CASCADE |
| actor_user_id | users(id) | SET NULL | CASCADE |

### Unique Constraints
- `UNIQUE(provider,provider_event_id)` for provider events with both columns non-NULL.

### Indexes
- `(financial_transaction_id,created_at,id)`.
- Unique `(provider,provider_event_id)`; MySQL permits repeated NULLs, which are reserved for internal events.
- `(to_status,created_at)`.

### Check Constraints
- Provider and provider_event_id both NULL (internal event) or both non-NULL (provider event).
- Event type/status allowlists [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Provider event deduplication uses `UNIQUE(provider,provider_event_id)`.
- Internal events store `provider=NULL,provider_event_id=NULL`. Do not rely on MySQL UNIQUE/NULL behavior for internal idempotency; if an internal operation requires idempotency, enforce it in service logic. Do not add a schema identity column without approval.
- Event payload retention/redaction policy: [NEEDS CONFIRMATION].

## 56. `seller_payout_adjustments`

### Purpose
Post-payout seller recovery or credit without changing a PAID payout.

### Columns
`id ID! PK`; `recipient_user_id ID! FK`; `original_payout_id ID! FK`; `refund_id ID? FK`; `adjustment_type VARCHAR(30)!`; `amount MONEY!`; `currency CHAR(3)!`; `status VARCHAR(20)!` default OPEN; `reason VARCHAR(500)!`; `idempotency_key VARCHAR(128)! UQ`; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`; `updated_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| recipient_user_id | users(id) | RESTRICT | CASCADE |
| original_payout_id | seller_payouts(id) | RESTRICT | CASCADE |
| refund_id | refunds(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(idempotency_key)`.

### Indexes
- `(recipient_user_id,status,created_at)`.
- `(original_payout_id)`; `(refund_id)`.

### Check Constraints
- Amount >0; currency VND.
- Type exactly `RECOVER_FROM_SELLER,CREDIT_TO_SELLER`.
- Status allowlist [NEEDS CONFIRMATION].

### Generated Columns
- None.

### Business Rules
- Adjustment recipient must match original payout recipient; service/composite FK invariant.
- Cash recovery versus offset and corresponding direction/status mapping: [NEEDS CONFIRMATION].

## 57. `seller_payout_adjustment_allocations`

### Purpose
Apply an adjustment against an eligible future payout.

### Columns
`id ID! PK`; `adjustment_id ID! FK`; `payout_id ID! FK`; `amount MONEY!`; `currency CHAR(3)!`; `created_at UTC_TS! DEFAULT CURRENT_TIMESTAMP(3)`.

### Foreign Keys
| Column(s) | References | On Delete | On Update |
|---|---|---|---|
| adjustment_id | seller_payout_adjustments(id) | RESTRICT | CASCADE |
| payout_id | seller_payouts(id) | RESTRICT | CASCADE |

### Unique Constraints
- `UNIQUE(adjustment_id,payout_id)`.

### Indexes
- Unique pair; `(payout_id)`.

### Check Constraints
- `amount > 0`; currency VND.

### Generated Columns
- None.

### Business Rules
- `payout_id` is the canonical FK name.
- Adjustment and payout must have same recipient and currency.
- Total allocated amount must not exceed outstanding adjustment or offsettable payout amount. This is a locked service transaction invariant.
- Allocation rows are immutable once recorded. To reverse an allocation, create a new adjustment/reversal record and corresponding allocation; do not mutate or delete the historical allocation row.
- No status or idempotency column is added to this table without owner approval.

## 10. Generated unique-key expressions

Expressions below are logical definitions for MySQL generated nullable columns. All uniqueness generated columns are STORED.

| Rule | Generated expression | Unique index |
|---|---|---|
| One default address/user | `CASE WHEN is_default = 1 THEN user_id ELSE NULL END` | `UNIQUE(default_address_user_key)` |
| One primary image/book | `CASE WHEN is_primary = 1 THEN book_id ELSE NULL END` | `UNIQUE(primary_image_book_key)` |
| One primary subject/work | `CASE WHEN is_primary = 1 THEN book_work_id ELSE NULL END` | `UNIQUE(primary_subject_work_key)` |
| One active cart/user | `CASE WHEN status = 'ACTIVE' THEN user_id ELSE NULL END` | `UNIQUE(active_cart_user_key)` |
| One active sale listing/book | `CASE WHEN status IN ('ACTIVE','RESERVED') THEN book_id ELSE NULL END` | `UNIQUE(active_sale_book_key)` |
| One active lend listing/book | `CASE WHEN status IN ('ACTIVE','RESERVED','ON_LOAN') THEN book_id ELSE NULL END` | `UNIQUE(active_lend_book_key)` |
| One default active payout account/user | `CASE WHEN is_default = 1 AND status = 'ACTIVE' THEN user_id ELSE NULL END` | `UNIQUE(default_active_account_user_key)` |
| One SALE order/seller/checkout | `CASE WHEN order_type = 'SALE' THEN seller_id ELSE NULL END` | `UNIQUE(checkout_group_id,sale_seller_key)` |

Active predicates are confirmed: sale `ACTIVE,RESERVED`; lend `ACTIVE,RESERVED,ON_LOAN`. The sale/lend cross-table exclusivity is not enforceable by these separate unique indexes and remains a service transaction invariant.

## 11. Financial event and payment state semantics

### 11.1 Payment allocation

Required allocation columns are `payment_id`, `order_id`, `allocation_type`, `amount`, `currency`, and idempotency identity. Proposed unique constraint: `UNIQUE(payment_id,order_id,allocation_type)`.

| Payment state | Allocation behavior |
|---|---|
| PENDING/PROCESSING | Not completed; do not count toward settled allocation totals |
| FAILED/CANCELLED | Do not contribute to completed allocations |
| PAID | Completed allocations must sum exactly to payment amount |
| REFUNDED/REVERSED | Original allocations remain immutable; refund/reversal records are additional rows |

`payment_allocations` has no status column. Completion is derived from payment state; do not add an allocation status. Unique `(payment_id,order_id,allocation_type)` is retained.

### 11.2 Reservation semantics

`checkout_groups.reservation_expires_at`:

- NULL means the checkout group currently holds no inventory reservation.
- Non-NULL means a reservation is active until that UTC timestamp.
- Checkout transaction creates group and split orders, locks inventory and atomically sets book/listing states to RESERVED.
- A timeout worker locks the group/inventory, confirms the reservation is still active, marks child orders/group expired/cancelled and returns inventory/listings to available states atomically.
- Reservation expiry/release is atomic for the entire checkout group; partial expiry/release across split orders is not allowed in v1.
- No reservation table is introduced.

### 11.3 Payout obligation and transfer attempts

- One order has one payout obligation (`UNIQUE(order_id)`), one recipient and one currency.
- `seller_payouts.status` represents obligation/overall lifecycle.
- Each provider transfer attempt is a separate `financial_transactions` row with `transaction_type=SELLER_PAYOUT`, `payout_id`, provider, reference, amount, status, idempotency key, and event history. Retry does not create another payout row.
- Transfer failure transitions payout `PROCESSING → FAILED`; retry transitions `FAILED → PROCESSING`.
- Account reference snapshot is an encrypted/tokenized provider reference needed for retry; raw bank credentials/passwords/PINs must not be stored. Paid payout snapshot is immutable.

## 12. Financial transaction type mapping

The following mapping is required for DDL and dashboard implementation. Rows marked unresolved must not be guessed.

| `transaction_type` | Required source | Direction | `cash_impact` | Notes |
|---|---|---|---|---|
| BUYER_PAYMENT | `payment_id` | IN | TRUE when settled | Amount is actual received funds |
| PLATFORM_FEE | `platform_fee_id` | IN attribution for buyer/seller-borne fee; OUT attribution for platform-funded subsidy | TRUE only for a separate real cash movement; otherwise FALSE | Direction is not itself proof of cash movement. Buyer-paid fee is in checkout/payment total; seller-paid deduction is not a new buyer cash IN |
| SELLER_PAYOUT | `payout_id` | OUT | TRUE only on successful transfer | Failed attempts are audit events, not cash out |
| REFUND | `refund_id` | OUT | TRUE when provider completes refund | Must reconcile to payment allocation |
| PAYMENT_REVERSAL | `payment_id` | OUT | TRUE only when settled funds are actually returned | An authorization void with no cash movement is provider/event history, not cash flow |
| PAYMENT_PROCESSOR_FEE | `payment_id` | OUT | TRUE when charged | Provider expense |
| SELLER_PAYOUT_ADJUSTMENT | `payout_adjustment_id` | IN for cash recovery / OUT for cash credit; OUT attribution for non-cash offset | TRUE for cash movement; FALSE for internal netting | Amount and direction depend on adjustment execution |
| DEPOSIT_FORFEITURE | `borrow_order_id` | OUT attribution | FALSE for reclassification of already collected deposit | Beneficiary defaults to lender; no new buyer cash IN; subsequent transfer uses SELLER_PAYOUT |

`financial_transactions` is an operational transaction/audit ledger, not double-entry accounting. Completed records are immutable; corrections use new reversal/adjustment rows.

## 13. Final consistency and unresolved decisions

### Table count

The dictionary contains exactly **57 tables**, numbered 1–57.

### Consistency checklist

| Category | Status | Detail |
|---|---|---|
| 57 tables exactly | PASS | Numbered 1–57 |
| PK | PASS | Each table defines a primary key or composite primary key |
| FK and delete/update actions | PASS | Every listed FK specifies `ON DELETE` and `ON UPDATE`; composite/cross-row business consistency remains service-enforced where noted |
| UNIQUE | NEEDS CONFIRMATION | Defined constraints are listed; provider-reference uniqueness scope and a few domain-specific uniqueness policies remain open |
| CHECK | NEEDS CONFIRMATION | Structural/XOR/money checks are described; multiple domain status/type allowlists and some business predicates remain open |
| Generated columns | NEEDS CONFIRMATION | Approved uniqueness expressions are specified as STORED; return/open-state generated uniqueness still depends on its unresolved status set |
| Currency | PASS | VND only; no FX |
| Money/rate precision | PASS | MONEY is `DECIMAL(19,4)` and RATE is `DECIMAL(9,6)` |
| UTC timestamps | PASS | `DATETIME(3)`; creation/update defaults and business-event timestamp nullability documented |
| Reservation | PASS | Group-level expiry, NULL meaning, atomic expiry/release, and inventory transitions are specified |
| Payment allocations | PASS | No status column; completion is derived from payment state, exact `UNIQUE(payment_id,order_id,allocation_type)`, and PAID sum invariant |
| Payment retry/funding policy | NEEDS CONFIRMATION | Whether multiple successful payment attempts can jointly fund one checkout group is unspecified |
| Refund | NEEDS CONFIRMATION | Order-level refund target and refund status/provider constraints need confirmation |
| Payout | PASS | One obligation/order; exact states and retry transitions; attempts are separate financial transaction rows; destination snapshot is protected and immutable after PAID |
| Financial transactions | NEEDS CONFIRMATION | Required types and cash-impact rules are mapped; a provider-reference uniqueness scope and some adjustment execution semantics remain open |
| Financial events | NEEDS CONFIRMATION | Provider identity uniqueness and internal NULL behavior are fixed; event allowlists and retention remain unspecified |
| Adjustments | NEEDS CONFIRMATION | Canonical `payout_id` and immutable allocation rule are fixed; adjustment status and cash-recovery/offset details remain open |
| Concurrency | PASS | Checkout-group reservation and payout/idempotency transaction boundaries are documented; remaining domain-specific invariants are service-layer rules |

### Remaining `[NEEDS CONFIRMATION]` items

The table-level markers are intentional and must not be guessed for DDL. They identify unspecified source decisions, including:

- **User and moderation:** `users.role/status` allowed values, email collation, address retention/anonymization; report severity/status and resolution timestamp rules.
- **Education, books, and verification:** subject/work/listing status sets, publication-year bounds, identifier namespaces/global uniqueness, book condition/acquisition values, verification type/status/evidence allowlists and evidence retention.
- **Sale, combo, shipping, and orders:** listing/order status sets, combo minimum/duplicate-item policy, shipping payer/return method values, checkout-group status, order total arithmetic/pricing policy, combo amount rules and rounding-policy version.
- **Cart and request matching:** cart-item target/amount invariants, duplicate combo policy, request-match type/status values and match deduplication identity.
- **Borrow, payment, and fulfillment:** borrow/return state allowlists, multiple successful payments jointly funding one checkout group, shipment state/tracking uniqueness scope.
- **Return, refund, coupon, and favorites:** open-return status predicate, refund statuses and whether order-level refunds may have NULL item targets, coupon normalization/collation and value/cap/currency rules.
- **Messaging and notifications/reviews:** conversation/message/channel/status allowlists and unresolved defaults.
- **Fee and payout accounts:** fee assessment status and fee-type/scope mapping; provider-token uniqueness scope; payout-account verification values.
- **Financial audit/adjustments:** provider-reference uniqueness scope for financial transactions; financial event type/status and payload retention; payout adjustment status and cash-recovery versus offset direction/status mapping.

These questions concern actual unspecified allowlists, defaults, uniqueness scopes, and business policies. Confirm them in the listed table/column entries before generating DDL.

## 14. DDL handoff gate

**DDL HANDOFF NOT READY.** The owner-confirmed payment allocation, payment state, reservation, payout retry, payout snapshot, active listing, STORED generated-column, platform-fee, deposit forfeiture, internal financial event, adjustment allocation, and timestamp decisions are incorporated. However, unresolved `[NEEDS CONFIRMATION]` items above still prevent a no-guess DDL handoff. Do not generate DDL until those entries are decided.
