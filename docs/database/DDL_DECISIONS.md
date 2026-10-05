# Passbook v1.2 DDL decisions and open items

## Scope and status

`passbook_v1.2.sql` and `verify_passbook_v1.2.sql` are best-effort, schema-only
deliverables based on the full `DATABASE_DATA_DICTIONARY_V1.2_FINAL.md`. The
dictionary was not edited. It numbers exactly 57 tables, and this DDL defines
those same 57 names; no reservations table or hard-coded database name is
included. The existing 57-table count agrees with the dictionary; no count
discrepancy was found.

The DDL is not owner approval of decisions the dictionary marks unresolved.
These files have not been applied to any database. No production/Aiven/database
connection, DDL execution, or seed-data operation was performed.
The dictionary's own “DDL HANDOFF NOT READY” gate therefore remains in force
for production use; this requested best-effort draft does not clear it.

Static inventory from the generated files: 57 tables, 592 declared columns,
134 foreign keys, 54 UNIQUE constraints, 104 row-local CHECK constraints,
eight STORED generated columns, 45 `DECIMAL(19,4)` columns, and two
`DECIMAL(9,6)` columns. All eight generated keys and their UNIQUE constraints
are included; the count excludes primary keys.

## Implemented conventions

- `ID`, `MONEY`, `RATE`, and `UTC_TS` are implemented as `BIGINT UNSIGNED`,
  `DECIMAL(19,4)`, `DECIMAL(9,6)`, and `DATETIME(3)`, respectively.
- Every table uses InnoDB and `utf8mb4`, with schema-default collation
  `utf8mb4_0900_ai_ci`. `users.email` and `coupons.code` use `utf8mb4_bin` so
  their unresolved comparison/case-folding policy is not silently broadened
  by the table collation. Email lowercase/trim normalization remains a
  service invariant as the dictionary says.
- Creation/update timestamps use the dictionary's `CURRENT_TIMESTAMP(3)` and
  `ON UPDATE CURRENT_TIMESTAMP(3)` defaults. Nullable business-event
  timestamps default to NULL. Required business-event timestamps and other
  columns with no decided default have no default; callers must provide them.
  No default value is invented for a `[NEEDS CONFIRMATION]` column.
- All dictionary foreign keys and their listed `ON DELETE` and `ON UPDATE`
  actions are carried through. Required parent/unique-key indexes are present.
  Tables are emitted in FK dependency order; `ALTER TABLE` is reserved for
  actual cycles, and none was needed in this dependency graph.
- The eight generated-key expressions specified in the dictionary are STORED
  and uniquely indexed. Their SQL types are an implementation assumption:
  each is `BIGINT UNSIGNED`, inferred because every expression returns an ID
  or nullable ID. Please review this type inference before adoption.
- Explicit, unambiguous row-local constraints are included. Checks needing
  unresolved domain values, scopes, or policy are omitted rather than
  guessed. Cross-row totals, lifecycle transitions, retention, and service
  invariants are not asserted as row-local SQL checks.
- Nullable provider reference uniqueness is implemented where the dictionary
  declares it. In particular, the candidate unique key on
  `(provider, transaction_type, provider_reference)` is retained for
  `financial_transactions`, although its scope is explicitly unresolved and
  requires owner review.
- Where a column's `UQ` marker could imply a global unique key but its table's
  Unique Constraints section specifies a scoped composite key (for example
  checkout/payment/refund idempotency or the sale-order generated key), the
  explicit scoped constraint is used instead of adding a stricter global
  unique constraint.
- The DDL retains the specified lifecycle shape without pretending to enforce
  it with row checks: payment allocations have no status column; checkout
  reservation expiry is group-level and nullable; payout retries are attempts
  under one order payout; internal financial events have both provider
  identity columns NULL; and payout-adjustment allocations remain separate
  immutable records. No reservation table is introduced.
- Fee attribution is not treated as a second buyer cash-in: `charged_to` is
  constrained to the specified three values, while transaction direction and
  actual `cash_impact` mapping remain unresolved. Deposit forfeiture remains a
  reclassification of the already-collected deposit, with lender as
  beneficiary by default; it does not imply a new buyer cash inflow.
- `financial_transactions` remains an operational transaction/audit ledger,
  not a double-entry accounting system. Its completed-record immutability,
  payout snapshot immutability, payment-allocation reconciliation, and
  adjustment reconciliation need service enforcement or separately approved
  database mechanisms.

## Decisions intentionally deferred

The following remain open in the authoritative dictionary and must be decided
before treating the DDL as production-ready. Their related allowlist or
policy checks are omitted or explicitly labeled as candidate implementations
in the SQL.

1. **Identity, education, moderation, and catalog**
   - Defaults and allowed values for `users.role`, `users.status`, and
     `user_violations.severity`; `user_violations.status` values and the
     status-to-`resolved_at` rule.
   - Case/collation behavior for canonical email; user-address retention or
     anonymization.
   - Status values for `universities.status`, `faculties.status`,
     `majors.status`, `subjects.status`, `categories.status`,
     `languages.status`, and `book_works.status`.
   - `book_editions.publication_year` bounds; `book_identifiers` type
     namespace and whether non-ISBN identifiers are globally unique.
   - `books.condition_label` and `acquisition_type` values;
     `book_verifications.status`, `verification_type`, and the value that
     qualifies as verified; `verification_evidences.evidence_type` and
     external evidence retention/deletion.
2. **Listings, requests, carts, checkout, and orders**
   - `sale_combos.status` and whether a combo must contain an item.
   - Defaults and allowed values for `borrow_terms.shipping_paid_by` and
     `return_method`.
   - `book_requests.status` / `condition_preference`,
     `request_interests.status`, and `request_matches.match_type` /
     `status` / deduplication identity.
   - `checkout_groups.status` default/allowlist and pricing arithmetic; whether
     multiple successful payments can jointly fund one checkout.
   - Order amount arithmetic policy; whether
     `sale_combo_order_items(order_id,combo_id)` is unique; required
     `rounding_policy_version`; whether combo allocation NULLability must
     match its parent. The optional `sale_order_items(id,order_id)` composite
     unique key is omitted because no corresponding composite FK is included;
     confirm whether the refund/return relationship should use that pair.
   - Cross-table seller/listing/book/order consistency beyond the explicit
     FKs, including seller/book ownership, active sale-versus-lend
     exclusivity, and fee/funding/recipient relationships. Category ancestry
     cycle prevention also remains a service rule.
3. **Borrow, payment, fulfillment, returns, and refunds**
   - `borrow_orders.status` / `return_status`; `shipments.status` default and
     allowlist, `shipment_tracking.status`, and shipment tracking uniqueness
     scope.
   - `returns.status` and the active/open-return set/predicate. No generated
     open-return key or active-return unique constraint is emitted until this
     predicate is defined.
   - `refunds.status` / provider policies, whether an order-level refund can
     have both optional item targets NULL, and allocation/order/target
     consistency enforcement.
4. **Coupons, favorites, messaging, notifications, and reports**
   - Coupon code normalization/collation, percentage bounds, amount caps, and
     nullable currency semantics.
   - `conversations.conversation_type` default/allowlist,
     `messages.message_type`, `notification_deliveries.channel` / `status`,
     `reports.status`, and report resolution timestamp behavior.
   - Unspecified sets such as payment method/purpose, notification type, and
     other provider/account/message classifications must be specified if they
     are intended to be database allowlists.
   - Service-level eligibility for review/report targets and coupon scope.
5. **Fees, payouts, financial events, and adjustments**
   - `platform_fees.status` default/allowlist, fee type-to-scope restrictions,
     and full fee type list. The `charged_to` set is implemented exactly as
     documented; it does not infer a fee beneficiary or additional cash
     movement.
   - `seller_payout_accounts.verification_status` default/allowlist,
     account-status allowlist, and provider-token uniqueness scope.
   - Complete financial transaction source/type/direction/`cash_impact`
     mapping, provider-reference uniqueness scope, status allowlist, and
     completion-timestamp rule.
   - `financial_transaction_events` event/status values and payload
     retention/redaction.
   - `seller_payout_adjustments.status` and cash-recovery versus offset
     execution semantics.
   - Whether additional internal-event idempotency is required.

Explicit unresolved defaults were not invented: `users.role` / `status`,
`user_violations.severity`, `borrow_terms.shipping_paid_by` /
`return_method`, `checkout_groups.status`,
`sale_combo_order_items.rounding_policy_version`, `shipments.status`,
`conversations.conversation_type`, `platform_fees.status`, and
`seller_payout_accounts.verification_status` remain without a default where
the dictionary leaves the default unresolved. `NOT NULL` values therefore
must be supplied by the caller until the owner decides otherwise.

Other documented but not fully DDL-enforceable policies include payment
allocation totals versus payment state, immutable snapshots/history, payout
retry transitions, group-atomic inventory reservation/release, refund sums,
and adjustment-allocation reconciliation. These require service transactions
or a separately approved database mechanism.

## Validation limits

The local environment has Python but no `mysql`, `mariadb`, or `docker`
executable. The SQL was not parsed by MySQL, and no MySQL syntax or execution
validation is claimed. Static checks were limited to the tools available
locally and do not replace running the verification script and reviewing the
schema on the intended MySQL 8.0.16+ test server.
