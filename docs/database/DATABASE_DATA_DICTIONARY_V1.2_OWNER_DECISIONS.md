# Passbook Database v1.2 — Owner Decision Sheet

## A. Instructions

This sheet gathers decisions needed to close the v1.2 Data Dictionary before anyone generates DDL. It is a decision record, **not DDL**.

- Do not infer an answer from an example, a default shown in the dictionary, or text previously drafted by an agent.
- Answer each listed field independently when a question contains a response matrix. Use the offered option where applicable, or write a custom decision.
- For status/type sets, provide the exact allowed values for each named column; columns in the same question do not automatically share an allowlist.
- “No default” is an explicit answer. “Use service validation” is an explicit enforcement assignment.
- Where a decision is already explicitly present in the owner’s instructions, it is recorded in the provenance audit as `CONFIRMED`; it is not re-asked as though undecided.
- `PROVENANCE CHECK REQUIRED` means the dictionary contains a proposed rule but this sheet cannot attribute that exact rule to an explicit owner decision. Confirm it or replace it.

Suggested answer form: `Q001: users.role = ...; users.status = ...`.

## B. Decision Questions

Questions are grouped by concern. Some questions group related columns to avoid one question per marker, but every named column still requires its own answer.

## Group 1 — Defaults

### Q001 — User role and account-status defaults
**Affected table:** `users`
**Affected columns:** `role`, `status`

**Current ambiguity:** Both columns are `NOT NULL`; neither default is specified.

**Question:** What is the default for each column?

**Options:**
- A. Provide an explicit default for each column.
- B. No default; application/service must provide each value.
- C. Other: ______

**DDL impact:** Yes
**Source:** `users.role`, `users.status`, lines 68–69.

### Q002 — Violation severity default
**Affected table:** `user_violations`
**Affected column:** `severity`

**Current ambiguity:** The column is `NOT NULL`; its default is unspecified.

**Question:** What is its default?

**Options:**
- A. Provide a default value.
- B. No default; application/service must provide it.
- C. Other: ______

**DDL impact:** Yes
**Source:** `user_violations.severity`, line 162.

### Q003 — Borrow-term defaults
**Affected table:** `borrow_terms`
**Affected columns:** `shipping_paid_by`, `return_method`

**Current ambiguity:** Both are `NOT NULL` and have no specified defaults.

**Question:** For each column, provide a default or explicitly choose no default.

**Options:**
- A. Provide a default for each.
- B. No default for each; application/service must provide them.
- C. Mixed: specify the default/no-default decision for each separately.
- D. Other: ______

**DDL impact:** Yes
**Source:** `borrow_terms.shipping_paid_by`, `borrow_terms.return_method`, lines 925–926.

### Q004 — Checkout-group status default
**Affected table:** `checkout_groups`
**Affected column:** `status`

**Current ambiguity:** `NOT NULL`; default unspecified.

**Question:** What is the default?

**Options:**
- A. Provide a default.
- B. No default; application/service must provide it.
- C. Other: ______

**DDL impact:** Yes
**Source:** `checkout_groups.status`, line 1183.

### Q005 — Combo allocation rounding-policy default
**Affected table:** `sale_combo_order_items`
**Affected column:** `rounding_policy_version`

**Current ambiguity:** `NOT NULL`; default/version policy is unspecified.

**Question:** What value or policy identifier is used by default, or must the caller always provide it?

**Options:**
- A. Provide a fixed default/version.
- B. No default; require an explicit version on insert.
- C. Other: ______

**DDL impact:** Yes
**Source:** `sale_combo_order_items.rounding_policy_version`, line 1362.

### Q006 — Shipment-status default
**Affected table:** `shipments`
**Affected column:** `status`

**Current ambiguity:** `NOT NULL`; default unspecified.

**Question:** What is the default?

**Options:**
- A. Provide a default.
- B. No default; application/service must provide it.
- C. Other: ______

**DDL impact:** Yes
**Source:** `shipments.status`, line 1569.

### Q007 — Conversation-type default
**Affected table:** `conversations`
**Affected column:** `conversation_type`

**Current ambiguity:** `NOT NULL`; default unspecified.

**Question:** What is the default, or should this be required from the application?

**Options:**
- A. Provide a default.
- B. No default; application/service must provide it.
- C. Other: ______

**DDL impact:** Yes
**Source:** `conversations.conversation_type`, line 1932.

### Q008 — Platform-fee status default
**Affected table:** `platform_fees`
**Affected column:** `status`

**Current ambiguity:** `NOT NULL`; default unspecified.

**Question:** What is the default?

**Options:**
- A. Provide a default.
- B. No default; application/service must provide it.
- C. Other: ______

**DDL impact:** Yes
**Source:** `platform_fees.status`, line 2158.

### Q009 — Payout-account verification default
**Affected table:** `seller_payout_accounts`
**Affected column:** `verification_status`

**Current ambiguity:** `NOT NULL`; default unspecified.

**Question:** What is the default, or must verification status always be explicitly supplied?

**Options:**
- A. Provide a default.
- B. No default; application/service must provide it.
- C. Other: ______

**DDL impact:** Yes
**Source:** `seller_payout_accounts.verification_status`, line 2208.

## Group 2 — Status / Type Allowlists

For each named column, provide the exact allowlist, or explicitly state that the value is intentionally unrestricted and must not have a database allowlist CHECK. A proposed value/default appearing elsewhere in the dictionary is not evidence of owner approval.

### Q010 — User and moderation allowlists
**Affected tables/columns:** `users.role`, `users.status`; `user_violations.severity`, `user_violations.status`

**Current ambiguity:** The dictionary does not establish complete allowed values. It also leaves the status-to-`resolved_at` rule open; answer that separately in Q022.

**Question:** What exact values are allowed for each of the four columns? Do not assume role and status sets are shared between tables.

**Options:**
- A. Supply a separate exact list for each column.
- B. State for each column that it is free-form/unrestricted (no allowlist CHECK).
- C. Other: ______

**DDL impact:** Yes
**Source:** lines 68–69, 92, 162, 183–184.

### Q011 — Reference-catalog status allowlists
**Affected tables/columns:** `universities.status`, `faculties.status`, `majors.status`, `subjects.status`, `categories.status`, `languages.status`, `book_works.status`

**Current ambiguity:** Each has a status field and a status index, but its accepted values are not defined. Answer each column independently.

**Question:** What exact allowed values apply to each catalog status?

**Options:**
- A. Supply a separate exact list for every column.
- B. For any named column, explicitly state no database allowlist.
- C. Other: ______

**DDL impact:** Yes
**Source:** lines 220, 257, 294, 331, 372, 405, 448.

### Q012 — Book, condition, verification, and evidence values
**Affected tables/columns:** `books.condition_label`, `books.acquisition_type`, `book_verifications.status`, `book_verifications.verification_type`, `verification_evidences.evidence_type`

**Current ambiguity:** Condition/acquisition and verification/evidence value sets are not complete.

**Question:** Provide the exact allowlist or explicitly no-allowlist decision for each named column.

**Options:**
- A. Supply a separate exact list for each column.
- B. Explicitly state which columns are intentionally unrestricted.
- C. Other: ______

**DDL impact:** Yes
**Source:** lines 611, 688, 725.

### Q013 — Sale-combo lifecycle values
**Affected table/column:** `sale_combos.status`

**Current ambiguity:** The dictionary names a lifecycle column but leaves its allowed values unresolved.

**Question:** What exact values are allowed?

**Options:**
- A. Supply the exact allowlist.
- B. No database allowlist; validate in service.
- C. Other: ______

**DDL impact:** Yes
**Source:** `sale_combos.status`, line 817.

### Q014 — Borrow-term and return-method values
**Affected table/columns:** `borrow_terms.shipping_paid_by`, `borrow_terms.return_method`, `borrow_orders.return_status`, `borrow_orders.return_method`

**Current ambiguity:** The dictionary does not specify complete payer/method/return-substate value sets.

**Question:** Provide the exact allowlist or no-allowlist choice independently for each column. Clarify whether the snapshot column uses the same set as the terms column.

**Options:**
- A. Supply a separate exact list for each column.
- B. Explicitly state which columns are unrestricted.
- C. Other: ______

**DDL impact:** Yes
**Source:** lines 925–926, 944, 1449.

### Q015 — Request, interest, and match allowlists
**Affected tables/columns:** `book_requests.status`, `book_requests.condition_preference`, `request_interests.status`, `request_matches.match_type`, `request_matches.status`

**Current ambiguity:** Status/type allowlists are incomplete; the request's `request_type` examples are not a complete confirmation of related fields.

**Question:** Provide exact values independently for every listed field, or explicitly state where no database allowlist is wanted.

**Options:**
- A. Supply a separate exact list for each column.
- B. Explicitly state which columns are unrestricted.
- C. Other: ______

**DDL impact:** Yes
**Source:** lines 1001, 1039, 1083.

### Q016 — Checkout-group status values
**Affected table/column:** `checkout_groups.status`

**Current ambiguity:** The status allowlist is unspecified, independently of its default in Q004.

**Question:** What exact values are allowed?

**Options:**
- A. Supply the exact allowlist.
- B. No database allowlist; validate in service.
- C. Other: ______

**DDL impact:** Yes
**Source:** `checkout_groups.status`, line 1216.

### Q017 — Payment-method and payment-purpose values
**Affected table/columns:** `payments.payment_method`, `payments.payment_purpose`

**Current ambiguity:** The columns and a `CHECKOUT` example/default are present, but accepted values and CHECK intent are not documented.

**Question:** Provide the exact allowlist for each column, or explicitly state that either is unrestricted.

**Options:**
- A. Supply a separate exact list for both.
- B. Explicitly state no allowlist for either/both.
- C. Other: ______

**DDL impact:** Yes if allowlists are required
**Source:** `payments.payment_method` and `payments.payment_purpose`, lines 1460–1508.

### Q018 — Shipment and tracking status values
**Affected tables/columns:** `shipments.status`, `shipment_tracking.status`

**Current ambiguity:** Shipment status allowlist and carrier-event status allowlist are not given. These may have different lifecycles.

**Question:** Provide a separate exact allowlist for each, or explicitly state no database allowlist for either.

**Options:**
- A. Supply separate lists.
- B. Explicitly state no allowlist for either/both.
- C. Other: ______

**DDL impact:** Yes
**Source:** `shipments.status`, `shipment_tracking.status`, lines 1589, 1626.

### Q019 — Return and refund status values
**Affected tables/columns:** `returns.status`, `refunds.status`

**Current ambiguity:** Both lifecycle allowlists are unresolved and must not be presumed identical.

**Question:** What exact values are allowed for each lifecycle?

**Options:**
- A. Supply separate exact lists.
- B. Explicitly state no database allowlist for either/both.
- C. Other: ______

**DDL impact:** Yes
**Source:** `returns.status`, `refunds.status`, lines 1671, 1732.

### Q020 — Conversation and message types
**Affected tables/columns:** `conversations.conversation_type`, `messages.message_type`

**Current ambiguity:** Neither exact type set is specified.

**Question:** Provide an exact allowlist for each column or explicitly state no database allowlist.

**Options:**
- A. Supply separate exact lists.
- B. Explicitly state no allowlist for either/both.
- C. Other: ______

**DDL impact:** Yes
**Source:** lines 1944, 2002.

### Q021 — Notification type, delivery channel/status, and violation type
**Affected tables/columns:** `notifications.notification_type`, `notification_deliveries.channel`, `notification_deliveries.status`, `user_violations.violation_type`

**Current ambiguity:** The dictionary does not say whether the type/category fields are finite sets or unrestricted strings. Delivery channel/status allowlists are also open.

**Question:** For every named column, provide exact values or explicitly choose no database allowlist.

**Options:**
- A. Supply a separate exact list for each column.
- B. Explicitly state which columns are unrestricted.
- C. Other: ______

**DDL impact:** Yes for CHECK/allowlist columns
**Source:** `notification_type` line 2036; `notification_deliveries` line 2059; `violation_type` line 159; delivery status/channel allowlist line 2059.

### Q022 — Report status values
**Affected table/column:** `reports.status`

**Current ambiguity:** The report lifecycle set is not specified.

**Question:** What exact values are allowed?

**Options:**
- A. Supply the exact allowlist.
- B. No database allowlist; validate in service.
- C. Other: ______

**DDL impact:** Yes
**Source:** `reports.status`, line 2125.

### Q023 — Platform fee type and status values
**Affected table/columns:** `platform_fees.fee_type`, `platform_fees.status`

**Current ambiguity:** Examples `SALE_COMMISSION`, `PAYMENT_FEE`, `OTHER` appear, but fee-type extensibility and assessment/reversal status values are not finalized.

**Question:** Confirm an exact `fee_type` allowlist or explicitly choose extensible/unrestricted values; separately provide the exact fee status allowlist.

**Options:**
- A. Exact, closed allowlist for both columns.
- B. Closed fee-status allowlist; extensible fee types without database CHECK.
- C. Other: ______

**DDL impact:** Yes
**Source:** `platform_fees.fee_type/status`, lines 2154–2158, 2183–2185.

### Q024 — Payout-account status and verification values
**Affected table/columns:** `seller_payout_accounts.status`, `seller_payout_accounts.verification_status`

**Current ambiguity:** Status and verification allowlists are unspecified, separately from the verification default in Q009.

**Question:** Provide exact values independently for both columns.

**Options:**
- A. Supply separate exact lists.
- B. Explicitly state no database allowlist for either/both.
- C. Other: ______

**DDL impact:** Yes
**Source:** `seller_payout_accounts`, line 2223.

### Q025 — Financial transaction types, statuses, and source matrix
**Affected table/columns:** `financial_transactions.transaction_type`, `direction`, `cash_impact`, `status`, all nullable source FKs

**Current ambiguity:** The table says status has an allowlist but gives no values. The source/direction/cash-impact map is drafted in the dictionary but its complete owner provenance is not established. See the blank decision matrix in Group 10 and provenance audit.

**Question:** Confirm the exact transaction-type and status allowlists, and complete/approve each matrix row: required source FK(s), direction, when `cash_impact` is true, and status transitions.

**Options:**
- A. Supply/approve every row of the matrix; specify which conditions are CHECK constraints and which are service invariants.
- B. Replace the matrix with an owner-provided mapping.
- C. Other: ______

**DDL impact:** Yes
**Source:** `financial_transactions`, lines 2309–2350; unmarked status ambiguity at line 2340.

### Q026 — Financial-event type and status values
**Affected table/columns:** `financial_transaction_events.event_type`, `from_status`, `to_status`

**Current ambiguity:** Event type/status allowlists are unspecified. Provider identity semantics are handled separately in provenance and Q042.

**Question:** Provide the exact event-type and status values, or explicitly identify any field intended to be unrestricted.

**Options:**
- A. Supply exact lists per field.
- B. Explicitly state which fields have no database allowlist.
- C. Other: ______

**DDL impact:** Yes
**Source:** `financial_transaction_events`, line 2390.

### Q027 — Payout-adjustment type and status values
**Affected table/columns:** `seller_payout_adjustments.adjustment_type`, `seller_payout_adjustments.status`

**Current ambiguity:** The listed types are candidate values; status allowlist is missing. The direction/recovery/offset decision is Q038.

**Question:** Confirm the exact type/status values independently.

**Options:**
- A. Confirm the current type values and supply status values.
- B. Supply replacement exact lists.
- C. Other: ______

**DDL impact:** Yes
**Source:** `seller_payout_adjustments`, lines 2406, 2425.

## Group 3 — NULL / CHECK / Arithmetic

### Q028 — Publication-year bounds
**Affected table/column:** `book_editions.publication_year`

**Current ambiguity:** `NULL` is allowed, but valid year bounds are not specified.

**Question:** What lower/upper bounds apply, and should future publication years be permitted?

**Options:**
- A. Provide inclusive lower and upper bounds.
- B. Provide a lower bound and no upper bound.
- C. Other: ______

**DDL impact:** Yes
**Source:** `book_editions.publication_year`, line 531.

### Q029 — Violation resolution timestamp rule
**Affected table/columns:** `user_violations.status`, `resolved_at`

**Current ambiguity:** The dictionary does not define whether resolved states require `resolved_at`, or whether non-resolved states may have it.

**Question:** Specify the exact status-to-timestamp invariant, or explicitly assign it to service validation.

**Options:**
- A. Database CHECK: provide the status predicate and timestamp rule.
- B. Service-layer invariant: provide the rule.
- C. Other: ______

**DDL impact:** Yes for CHECK; otherwise service assignment
**Source:** `user_violations`, line 185.

### Q030 — Checkout and order total arithmetic
**Affected tables/columns:** `checkout_groups.subtotal`, `shipping_total`, `discount_total`, `total_amount`; `orders.subtotal`, `shipping_fee`, `discount_amount`, `total_amount`

**Current ambiguity:** Checkout formula is said to depend on pricing policy; order arithmetic is also open.

**Question:** Give the exact arithmetic formula and permitted component signs for each table. State whether this is a CHECK or a transaction/service invariant.

**Options:**
- A. Provide separate formulas and DDL CHECK conditions.
- B. Provide separate formulas and assign cross-column/cross-row enforcement to service.
- C. Other: ______

**DDL impact:** Yes
**Source:** `checkout_groups`, line 1214; `orders`, line 1281.

### Q031 — Sale-item combo allocation checks
**Affected table/columns:** `sale_order_items.combo_order_item_id`, `combo_allocated_amount`, monetary columns

**Current ambiguity:** The document requires nonnegative amounts and says allocation nullability must correspond to combo parent, but the CHECK detail is unresolved.

**Question:** Confirm the exact NULL pairing and amount constraints.

**Options:**
- A. `combo_order_item_id IS NULL` iff `combo_allocated_amount IS NULL`; specify any amount bounds.
- B. Provide a different precise predicate.
- C. Other: ______

**DDL impact:** Yes
**Source:** `sale_order_items`, line 1335.

### Q032 — Refund target shape
**Affected table/columns:** `refunds.sale_order_item_id`, `borrow_order_id`, `return_id`, `order_id`

**Current ambiguity:** It is unresolved whether both optional sale/borrow targets may be NULL for an order-level refund. The table also describes a target XOR and matching relationships.

**Question:** Which target forms are valid, and what exact XOR/NULL rules apply? Specify whether these are CHECK/composite-FK rules or service invariants.

**Options:**
- A. Require exactly one sale-item or borrow target; return target optional only for sale.
- B. Permit order-level refund with both targets NULL.
- C. Define another exact target matrix.
- D. Other: ______

**DDL impact:** Yes
**Source:** `refunds`, lines 1728–1741.

### Q033 — Coupon rate, cap, and currency CHECKs
**Affected table/columns:** `coupons.discount_rate`, `fixed_discount_amount`, `min_order_amount`, `max_discount_amount`, `currency`

**Current ambiguity:** Percent range, cap relationships and nullable currency behavior are unspecified.

**Question:** Define the exact rate bounds, cap/minimum relationships, and when `currency` must be NULL or `VND`.

**Options:**
- A. Provide exact CHECK predicates.
- B. Specify which are service-only and give the invariant.
- C. Other: ______

**DDL impact:** Yes
**Source:** `coupons`, line 1786.

### Q034 — Platform-fee target nullability and scope
**Affected table/columns:** `platform_fees.order_id`, `sale_order_item_id`, `borrow_order_id`, `payment_id`, `fee_type`

**Current ambiguity:** Scope is described as sale item, borrow order, payment, or order-level, but the exact allowed NULL/non-NULL combination and fee-type-to-scope rules are absent.

**Question:** Provide a complete predicate/table mapping: for each `fee_type` and fee case, which target FK is populated, which are NULL, and whether order-level means all three optional scope FKs NULL.

**Options:**
- A. Provide a closed scope matrix and CHECK expression.
- B. Provide the matrix and assign cross-row parts to service validation.
- C. Other: ______

**DDL impact:** Yes
**Source:** `platform_fees`, line 2183; unmarked target-nullability ambiguity.

### Q035 — Payout net-amount arithmetic
**Affected table/columns:** `seller_payouts.gross_amount`, `platform_fee_amount`, `refund_amount`, `net_amount`; adjustments

**Current ambiguity:** The formula is qualified by “subject to adjustments policy,” while PAID payout is immutable and post-payout adjustments are separate records.

**Question:** Define precisely what components calculate `net_amount`, when it becomes immutable, and whether an adjustment can affect it before payout.

**Options:**
- A. Formula is fixed to gross minus fee minus refund; adjustments never mutate payout amounts.
- B. Provide another exact formula/lifecycle.
- C. Other: ______

**DDL impact:** Yes
**Source:** `seller_payouts`, line 2290; unmarked arithmetic ambiguity.

### Q036 — Combo minimum item count
**Affected table:** `sale_combo_items`

**Current ambiguity:** The dictionary asks whether a combo must contain at least one item; this is a cross-row rule, not a single-row CHECK.

**Question:** Must every persisted combo have at least one item? If yes, confirm enforcement as a service transaction invariant (or specify another implementation).

**Options:**
- A. Yes; service-layer invariant.
- B. No; empty combo is permitted.
- C. Other: ______

**DDL impact:** No, if assigned to service
**Source:** `sale_combo_items`, line 860.

## Group 4 — UNIQUE / Generated Columns

### Q037 — Email uniqueness semantics
**Affected table/column:** `users.email`

**Current ambiguity:** Canonical normalization is described, but collation/case comparison is undecided.

**Question:** Define the exact normalization and uniqueness comparison semantics used by the unique index.

**Options:**
- A. Case-insensitive canonical email uniqueness; specify collation/normalization.
- B. Case-sensitive uniqueness; specify collation/normalization.
- C. Other: ______

**DDL impact:** Yes
**Source:** `users.email`, line 85.

### Q038 — Identifier uniqueness and namespaces
**Affected table/columns:** `book_identifiers.identifier_type`, `identifier_value`

**Current ambiguity:** The type/namespace set and global uniqueness behavior for non-ISBN values are unresolved.

**Question:** For each identifier type, specify its namespace and whether uniqueness is global, type-scoped, edition-scoped, or another scope.

**Options:**
- A. Supply a per-type namespace and uniqueness scope.
- B. Supply a different exact scope rule.
- C. Other: ______

**DDL impact:** Yes
**Source:** `book_identifiers`, lines 567, 574.

### Q039 — Request-match deduplication key
**Affected table:** `request_matches`

**Current ambiguity:** No deduplication key is specified.

**Question:** Should duplicate matches be prevented? If so, identify the exact columns/scope (including whether match type/status participates).

**Options:**
- A. Add a unique key; specify its exact columns.
- B. No unique key; duplicates are allowed.
- C. Other: ______

**DDL impact:** Yes
**Source:** `request_matches`, line 1073.

### Q040 — Shipment tracking-code uniqueness
**Affected table/columns:** `shipments.carrier`, `tracking_code`

**Current ambiguity:** The index exists but uniqueness and scope are unresolved.

**Question:** Is a tracking code unique, and within what scope (global, carrier, provider account, or another scope)?

**Options:**
- A. Global unique when non-NULL.
- B. Unique with carrier when non-NULL.
- C. Non-unique; retain ordinary index only.
- D. Other: ______

**DDL impact:** Yes
**Source:** `shipments`, line 1582.

### Q041 — Coupon-code normalization/collation
**Affected table/column:** `coupons.code`

**Current ambiguity:** Unique code is specified but normalization/collation is not.

**Question:** Define normalization and case/collation semantics for uniqueness.

**Options:**
- A. Case-insensitive canonical code; specify normalization/collation.
- B. Case-sensitive code; specify normalization/collation.
- C. Other: ______

**DDL impact:** Yes
**Source:** `coupons.code`, line 1777.

### Q042 — Payout provider-token uniqueness
**Affected table/columns:** `seller_payout_accounts.provider`, `account_token`

**Current ambiguity:** Provider-scoped token uniqueness is suggested but not defined.

**Question:** Is the token unique? If yes, specify scope and behavior for NULL/rotated tokens.

**Options:**
- A. Unique by `(provider, account_token)`.
- B. Unique by another exact scope.
- C. No unique constraint.
- D. Other: ______

**DDL impact:** Yes
**Source:** `seller_payout_accounts`, line 2217.

### Q043 — Financial provider-reference uniqueness
**Affected table/columns:** `financial_transactions.provider`, `transaction_type`, `provider_reference`

**Current ambiguity:** Candidate unique tuple is shown, but scope is explicitly unresolved.

**Question:** Confirm the exact uniqueness scope and NULL behavior for provider references.

**Options:**
- A. Unique `(provider, transaction_type, provider_reference)` when reference is non-NULL.
- B. Unique `(provider, provider_reference)` when non-NULL.
- C. Another exact tuple/predicate.
- D. No unique constraint.

**DDL impact:** Yes
**Source:** `financial_transactions`, line 2329.

### Q044 — Open-return uniqueness predicate
**Affected table/columns:** `returns.status`, generated open-return key, `sale_order_item_id`

**Current ambiguity:** Both the open status set and generated-key expression depend on the unresolved return lifecycle.

**Question:** Should a sale item have at most one active/open return? If yes, name every status counted as open and confirm the intended uniqueness scope.

**Options:**
- A. Yes; provide exact open statuses and key scope.
- B. No active/open unique constraint.
- C. Other: ______

**DDL impact:** Yes
**Source:** `returns`, lines 1664, 1675.

### Q045 — Generated uniqueness-column SQL types
**Affected table/columns:** `default_address_user_key`, `primary_subject_work_key`, `primary_image_book_key`, `active_sale_book_key`, `active_lend_book_key`, `active_cart_user_key`, `sale_seller_key`, `default_active_account_user_key`

**Current ambiguity:** Expressions and STORED mode are documented, but the generated columns have no declared SQL datatype.

**Question:** Confirm the explicit SQL datatype for each generated key, compatible with its source expression, or authorize the DDL implementer to derive the exact type mechanically from the source columns and verify it on MySQL 8.0.16+.

**Options:**
- A. Owner supplies the type for each key.
- B. DDL implementer derives compatible types from source column types; no semantic owner choice.
- C. Other: ______

**DDL impact:** Yes, implementation detail must be closed before DDL
**Source:** generated-key expressions at lines 2469–2480; table definitions at lines 141, 486, 652, 779, 905, 1121, 1284, 2227.

### Q046 — Generated-column inventory documentation
**Affected tables:** `book_work_subjects`, all generated-key tables

**Current ambiguity:** Generated-key summary says all uniqueness keys are STORED, but `primary_subject_work_key` table-local text omits the word `STORED`; generated-key SQL types are not shown in the summary.

**Question:** No business choice is implied. Confirm this is a documentation consistency/DDL transcription item, not an additional generated-key expression decision.

**Options:**
- A. Documentation-only correction; use approved STORED mode and expressions.
- B. There is a further generated-column decision; specify it.
- C. Other: ______

**DDL impact:** No, unless option B
**Source:** `book_work_subjects` generated section line 486; summary lines 2469–2480.

## Group 5 — Currency / Money

### Q047 — Currency columns versus inherited currency
**Affected tables/columns:** All monetary columns; particularly `sale_order_items` monetary fields, `borrow_terms.late_fee_per_day`, and `coupons.currency`

**Current ambiguity:** The convention permits a table to inherit currency but does not enumerate all inherited amounts. `sale_order_items` has money columns but no currency column or explicit inheritance source. `borrow_terms` says inherited from `lend_listings.currency`; coupon currency is nullable with unresolved semantics.

**Question:** For every amount column, confirm either (1) its own `currency` column, or (2) the exact parent column from which currency is inherited. Specifically decide whether `sale_order_items` inherits `orders.currency` or stores its own currency, and define when `coupons.currency` is NULL versus `VND`.

**Options:**
- A. Provide a complete amount-to-currency-column/inheritance map.
- B. Supply a different explicit map.
- C. Other: ______

**DDL impact:** Yes
**Source:** conventions line 47; `borrow_terms` currency note around line 937; `sale_order_items` lines 1300–1335; `coupons` lines 1760–1786.

### Q048 — VND-only and money precision confirmation
**Affected scope:** All monetary tables and rates

**Current ambiguity:** Dictionary convention states VND only, `MONEY=DECIMAL(19,4)`, `RATE=DECIMAL(9,6)`, no FX. These match the owner-provided conventions, but this sheet records confirmation provenance before DDL.

**Question:** Confirm that every monetary value is VND-only at the stated precision, with no FX currency in v1.2.

**Options:**
- A. Confirm VND-only and current precision.
- B. Provide a complete replacement currency/precision policy.
- C. Other: ______

**DDL impact:** Yes
**Source:** conventions lines 14–27; currency-bearing tables throughout.

### Q049 — Combo allocation rounding policy
**Affected tables/columns:** `sale_combo_order_items.rounding_policy_version`, `sale_order_items.combo_allocated_amount`

**Current ambiguity:** Allocation totals must equal the combo net amount “after rounding,” but the rounding algorithm/precision and remainder assignment are not specified.

**Question:** Define the exact rounding algorithm, precision, remainder allocation rule, and version identifier behavior. Do not infer from `DECIMAL(19,4)`.

**Options:**
- A. Provide a deterministic rule/version.
- B. Assign calculation rule to service layer and document its required invariant/versioning.
- C. Other: ______

**DDL impact:** Usually service/documentation; version column default is Q005
**Source:** `sale_combo_order_items`, lines 1362–1373.

## Group 6 — Checkout / Order / Payment

### Q050 — Payment attempts and successful-funding policy
**Affected tables:** `payments`, `payment_allocations`, `checkout_groups`

**Current ambiguity:** The schema can represent multiple attempts, but it is unspecified whether multiple successful payment attempts may jointly fund one checkout group.

**Question:** Define allowed attempt/funding behavior, including whether a checkout can have more than one PAID payment and how duplicate successful captures are reconciled.

**Options:**
- A. At most one PAID payment per checkout group.
- B. Multiple PAID payments may jointly fund it; define allocation/reconciliation rule.
- C. Other: ______

**DDL impact:** May require uniqueness/aggregate enforcement; at minimum lifecycle rule
**Source:** `payments`, line 1508; checklist line 2556.

### Q051 — Payment allocation completion and sum invariant provenance
**Affected table:** `payment_allocations`

**Current ambiguity:** The dictionary says no allocation status; completion derives from payment status; a PAID payment's allocations sum to payment amount. Those rules were explicitly supplied by the owner.

**Question:** No new policy choice is requested. Confirm that the captured owner decision is accurately represented and do not add an allocation status.

**Options:**
- A. Confirm as written.
- B. Correct the transcription with a replacement decision.
- C. Other: ______

**DDL impact:** Yes, but the rule is already owner-confirmed
**Source:** `payment_allocations`, lines 1525–1551 and 2488–2497.

### Q052 — Payment/refund lifecycle and partial refund semantics
**Affected tables/columns:** `payments.status`, `refunds.status`, `refunds.amount`, `financial_transactions`

**Current ambiguity:** Payment states are owner-confirmed, but full transition graph and partial-refund behavior are not. In particular, whether a partially refunded payment remains `PAID` or becomes `REFUNDED` is not defined.

**Question:** Confirm the payment transition graph using only the approved states, define partial versus full refund status semantics, and give refund lifecycle transitions/status values (the exact refund allowlist is also Q019).

**Options:**
- A. Partial refund leaves payment `PAID`; `REFUNDED` means fully refunded.
- B. Provide another exact state-transition rule.
- C. Other: ______

**DDL impact:** Schema status values already fixed for payment; refund CHECK/lifecycle depends on answer
**Source:** `payments` lines 1498–1501; `refunds` lines 1732–1741.

### Q053 — Refund maximum and allocation relationship
**Affected tables:** `refunds`, `payment_allocations`

**Current ambiguity:** Cumulative completed refunds must not exceed refundable allocation, but which refund states count as completed and how allocations are selected/released must align with Q019/Q032/Q052.

**Question:** Confirm the exact amount basis and completion states for the aggregate invariant, and assign enforcement to a locked service transaction or specify a DDL mechanism.

**Options:**
- A. Service-layer locked aggregate invariant; provide the amount basis/statuses.
- B. Specify a DDL-enforceable mechanism.
- C. Other: ______

**DDL impact:** Service invariant if selected; otherwise DDL design
**Source:** `refunds` business rules around line 1737.

## Group 7 — Reservation

### Q054 — Reservation decision provenance
**Affected table/column:** `checkout_groups.reservation_expires_at`; split child orders/inventory

**Current text:** NULL means the group currently holds no reservation; expiry/release is atomic for the entire group; partial expiry is disallowed. Timeout/cancel releases reserved inventory.

**Question:** These rules appear explicitly in the owner-provided decision instructions. Confirm provenance only if the recorded source is disputed; no new design choice is being requested here.

**Options:**
- A. Confirm captured owner decision.
- B. Replace with a corrected owner decision.
- C. Other: ______

**DDL impact:** Yes; decisions are recorded as confirmed
**Source:** `checkout_groups.reservation_expires_at`, line 1192; lifecycle section lines 2501–2510.

## Group 8 — Platform Fees

### Q055 — Fee recipient/charged-to/cash-impact semantics provenance
**Affected table/columns:** `platform_fees.recipient_user_id`, `charged_to`, `cash_impact`

**Current text:** `recipient_user_id` means user whose proceeds are related to the fee base, not the fee beneficiary. `charged_to` is BUYER/SELLER/PLATFORM. Buyer-paid fee is in checkout/payment pricing and not a second buyer cash IN; seller-paid fee is deducted from proceeds; platform-funded fee is not buyer/seller collection. `cash_impact=TRUE` only for actual separate movement.

**Question:** These distinctions were explicitly supplied in owner instructions. Confirm the dictionary captured them correctly; do not reinterpret “recipient” as fee beneficiary.

**Options:**
- A. Confirm as written.
- B. Provide corrected semantics.
- C. Other: ______

**DDL impact:** Yes; provenance is confirmed
**Source:** `platform_fees`, lines 2150, 2166–2198; transaction mapping lines 2522–2531.

## Group 9 — Seller Payout

### Q056 — Payout lifecycle and eligibility
**Affected table:** `seller_payouts`

**Current ambiguity:** One obligation per order and states/retry are owner-confirmed, but exact payout eligibility thresholds (fulfillment, return window, disputes) are not defined in the dictionary.

**Question:** Confirm the eligibility rule/timing or assign it as a service policy with exact required inputs. Also confirm that payout is not eligible immediately on buyer payment absent those conditions.

**Options:**
- A. Define exact eligibility event/window.
- B. Assign exact eligibility calculation to service/business policy; no DDL constraint.
- C. Other: ______

**DDL impact:** Usually service lifecycle; status/timestamp constraints may be affected
**Source:** `seller_payouts` business rules, lines 2297–2302.

### Q057 — Payout obligation/attempt separation and retry provenance
**Affected tables:** `seller_payouts`, `financial_transactions`

**Current text:** One payout obligation/order (`UNIQUE(order_id)`); failure `PROCESSING → FAILED`; retry `FAILED → PROCESSING`; each provider attempt is a separate `financial_transactions` row.

**Question:** These rules are explicitly stated in owner instructions. Confirm transcription; do not create a new obligation per retry.

**Options:**
- A. Confirm as written.
- B. Provide corrected owner decision.
- C. Other: ______

**DDL impact:** Yes; provenance is confirmed
**Source:** `seller_payouts`, lines 2229–2237, 2278–2300; lifecycle summary lines 2511–2516.

### Q058 — Payout-account snapshot provenance
**Affected table/columns:** `seller_payouts.account_reference_snapshot`, destination snapshot columns

**Current text:** Snapshot is encrypted/tokenized provider reference needed for retry, not raw bank credentials/password/PIN; paid payout and destination snapshot are immutable.

**Question:** This was explicitly supplied in owner instructions. Confirm transcription; specify only if retention/access boundaries differ.

**Options:**
- A. Confirm as written.
- B. Provide corrected snapshot/security requirements.
- C. Other: ______

**DDL impact:** Snapshot shape already documented; retention/access is implementation policy
**Source:** `seller_payouts`, lines 2244–2261, 2301–2302, 2516.

## Group 10 — Financial Transactions

The dictionary currently contains a proposed mapping. Do not treat it as approved just because it is present. Complete/approve this matrix. Write `NOT APPLICABLE` only where the owner explicitly decides a field is not used; otherwise supply a value or mark the remaining rule for later decision.

| `transaction_type` | Current source in dictionary | Direction | `cash_impact` | Status / transition | Owner answer |
|---|---|---|---|---|---|
| `BUYER_PAYMENT` | `payment_id` | **PROVENANCE CHECK REQUIRED** — dictionary says IN | **PROVENANCE CHECK REQUIRED** — says TRUE when settled | Not specified by mapping | |
| `PLATFORM_FEE` | `platform_fee_id` | **PROVENANCE CHECK REQUIRED** — attribution IN/OUT depends on who bears fee | Fee cash-impact rule explicitly owner-confirmed; separate real movement only | Not specified by mapping | |
| `SELLER_PAYOUT` | `payout_id` | **PROVENANCE CHECK REQUIRED** — dictionary says OUT | **PROVENANCE CHECK REQUIRED** — TRUE only on successful transfer | Attempt/status links to confirmed payout lifecycle | |
| `REFUND` | `refund_id` | **PROVENANCE CHECK REQUIRED** — dictionary says OUT | **PROVENANCE CHECK REQUIRED** — TRUE when provider completes | Not specified by mapping | |
| `PAYMENT_REVERSAL` | `payment_id` | **PROVENANCE CHECK REQUIRED** — dictionary says OUT | **PROVENANCE CHECK REQUIRED** — settled funds returned only | Void-without-cash treatment not owner-confirmed | |
| `PAYMENT_PROCESSOR_FEE` | `payment_id` | **PROVENANCE CHECK REQUIRED** — dictionary says OUT | **PROVENANCE CHECK REQUIRED** — when provider charges | Not specified by mapping | |
| `SELLER_PAYOUT_ADJUSTMENT` | `payout_adjustment_id` | **PROVENANCE CHECK REQUIRED** — recovery IN, credit/offset OUT | **PROVENANCE CHECK REQUIRED** — cash vs internal netting | Depends on recovery/offset lifecycle | |
| `DEPOSIT_FORFEITURE` | `borrow_order_id` | **PROVENANCE CHECK REQUIRED** — dictionary says OUT attribution | Reclassification creates no new buyer cash IN is owner-confirmed; full transaction cash-impact mapping needs confirmation | Forfeiture follows confirmed deposit-liability rule | |

**Affected table:** `financial_transactions`
**Affected columns:** `transaction_type`, source FKs, `direction`, `cash_impact`, `status`, `completed_at`, `provider_reference`

**Current ambiguity:** Exact per-type source/direction/cash-impact/status mapping is not proven owner-approved. The separate `financial_transactions.status` allowlist is also absent (Q025).

**Question:** For each type, approve or replace the mapping above. State which invariants are CHECK constraints and which are service rules. Confirm whether failed provider attempts are stored as non-cash transaction rows or only events.

**Options:**
- A. Approve the table mapping after completing all provenance-required cells.
- B. Replace it with a new complete matrix.
- C. Other: ______

**DDL impact:** Yes
**Source:** `financial_transactions` mapping, lines 2325–2350 and 2522–2533.

### Q059 — Payment-reversal behavior provenance
**Affected tables:** `payments`, `financial_transactions`, provider-event records

**Current text:** A reversal has `direction=OUT`, with `cash_impact=TRUE` only when settled funds are returned; an authorization void without cash movement is event history.

**Question:** No explicit owner decision for this precise distinction was found in the supplied decision set. Confirm or replace the rule, including whether a no-cash void gets a financial transaction row or only an event.

**Options:**
- A. Confirm current text.
- B. Replace with a different exact rule.
- C. Other: ______

**DDL impact:** Yes for transaction source/type/status mapping
**Source:** transaction mapping row at line 2528.

## Group 11 — Payout Adjustments

### Q060 — Adjustment direction and recovery/offset lifecycle
**Affected tables:** `seller_payout_adjustments`, `seller_payout_adjustment_allocations`, `financial_transactions`

**Current ambiguity:** Type values suggest recovery/credit; cash recovery vs future-payout offset direction/status mapping is unresolved.

**Question:** Define the exact lifecycle for (a) cash recovery from seller, (b) credit to seller, and (c) offset against a future payout. For each, state financial transaction direction/cash impact and which statuses apply.

**Options:**
- A. Supply a three-case mapping.
- B. Limit v1 to a specified subset; identify it.
- C. Other: ______

**DDL impact:** Yes for status/type/mapping; some execution is service layer
**Source:** `seller_payout_adjustments`, line 2432; mapping line 2530.

### Q061 — Adjustment idempotency and allocation behavior
**Affected tables:** `seller_payout_adjustments.idempotency_key`, `seller_payout_adjustment_allocations`

**Current text:** Adjustment has a unique idempotency key; allocation is unique by `(adjustment_id,payout_id)`, immutable, bounded by outstanding adjustment/offsettable payout, and reversal uses a new adjustment/reversal record and allocation.

**Question:** Confirm idempotency-key scope and whether the current unique pair is sufficient. Confirm that no status/idempotency columns are added to allocation rows, and define how reversal records identify the prior allocation.

**Options:**
- A. Confirm global adjustment key; retain current allocation uniqueness and immutable/reversal rules.
- B. Provide exact alternative key scope and allocation identity.
- C. Other: ______

**DDL impact:** Yes for key/unique; reversal linking may be service/documentation
**Source:** `seller_payout_adjustments`, lines 2406–2416; allocation rules lines 2440–2462.

## Group 12 — FK / Delete / Update

### Q062 — Foreign-key action provenance and exceptions
**Affected tables:** All 57 tables

**Current text:** Every listed FK has a target, explicit `ON DELETE` action, and `ON UPDATE CASCADE`; the dictionary says financial/order/payment/payout/refund/audit history is never cascade-deleted.

**Question:** Confirm these are approved policies, not merely draft defaults. If not, provide exceptions by child FK with exact delete and update action. Pay particular attention to nullable actor FKs using `SET NULL` and catalog/junction FKs using `CASCADE`.

**Options:**
- A. Confirm all current per-FK actions.
- B. Provide an exception list by `table.column(s)`.
- C. Other: ______

**DDL impact:** Yes
**Source:** global FK policy lines 28, 40–45 and every table's `### Foreign Keys` section.

### Q063 — Cross-table FK versus service invariant assignments
**Affected tables:** `refunds`, `platform_fees`, `seller_payouts`, `sale_order_items`, `borrow_orders`, `reviews`, `returns`, `financial_transactions`

**Current ambiguity:** Some relationships are described as service-level, composite-FK, or CHECK/service alternatives without choosing one. Examples include refund order/allocation/target matching; fee target/order/recipient relationship; payout recipient matching seller/lender; review/return target membership; transaction source matching its type.

**Question:** For each listed relationship, explicitly assign enforcement to (1) composite FK/CHECK, (2) locked service transaction, or (3) another exact mechanism. Do not ask to re-decide relationships already clearly marked service invariants unless the owner wants them encoded in DDL.

**Options:**
- A. Provide an enforcement assignment for each relationship.
- B. Confirm the relationships already explicitly labeled service invariants; choose DDL enforcement only for the unresolved alternatives.
- C. Other: ______

**DDL impact:** Yes where a composite FK or CHECK is intended
**Source:** table business rules for `refunds` lines 1728–1741, `platform_fees` lines 2181–2198, `seller_payouts` lines 2297–2302, and corresponding listed service/composite notes.

## Group 13 — Idempotency / Immutability

### Q064 — Idempotency-key scopes
**Affected tables/columns:** `checkout_groups`, `payments`, `payment_allocations`, `refunds`, `platform_fees`, `seller_payouts`, `financial_transactions`, `seller_payout_adjustments`

**Current ambiguity:** The dictionary declares unique-key scopes (for example buyer-scoped checkout, provider-scoped payment/refund, global fee/payout/financial/adjustment keys), but not all scopes have explicit owner provenance. Provider event identity is separately confirmed in Q065.

**Question:** Confirm the intended scope and retry semantics for each key, or provide corrections. A “unique” statement alone does not explain whether a retry reuses an entity or creates a new attempt/event.

**Options:**
- A. Confirm each currently declared unique scope.
- B. Provide corrected scope/retry semantics by table.
- C. Other: ______

**DDL impact:** Yes
**Source:** unique constraints at `checkout_groups` line 1205, `payments` lines 1491–1492, `payment_allocations` line 1536, `refunds` lines 1720–1721, `platform_fees` line 2174, `seller_payouts` line 2278, `financial_transactions` line 2328, adjustments line 2416.

### Q065 — Provider/internal financial-event identity provenance
**Affected table:** `financial_transaction_events`

**Current text:** Provider event has both `provider` and `provider_event_id` non-NULL and is unique on the pair. Internal event has both NULL; internal idempotency is service-level or separately approved, not UNIQUE-with-NULL.

**Question:** These semantics were explicitly supplied in owner instructions. Confirm transcription and state whether any internal event class requires a service idempotency key (without adding schema absent approval).

**Options:**
- A. Confirm as written; internal idempotency remains service-level as needed.
- B. Provide corrected owner decision.
- C. Other: ______

**DDL impact:** Yes for provider uniqueness; internal key behavior is service assignment
**Source:** `financial_transaction_events`, lines 2376–2398.

### Q066 — Snapshot and completed-record immutability provenance
**Affected tables:** `payments`, `orders`, `seller_payouts`, `financial_transactions`, `financial_transaction_events`, `seller_payout_adjustment_allocations`

**Current text:** Order snapshots do not change after confirmation; PAID payout and destination snapshot are immutable; completed financial rows are immutable; adjustment allocations are immutable and reversal adds new records.

**Question:** Confirm each rule that came from explicit owner instructions; identify any additional immutable records or allowed corrections. Keep state transitions separate from mutation of completed financial history.

**Options:**
- A. Confirm the listed immutable scopes.
- B. Provide a table-by-table replacement.
- C. Other: ______

**DDL impact:** Some immutability is service/trigger policy; snapshot columns are schema-relevant
**Source:** order snapshot line 1290; payout lines 2301–2302; financial transactions line 2350; adjustment allocations lines 2457–2462.

### Q067 — FK index coverage
**Affected tables:** All 57 tables

**Current ambiguity:** The dictionary requires an index for every FK and lists indexes, but it does not prove every FK column is covered by an index with the correct leftmost-prefix ordering.

**Question:** This is a DDL implementation verification, not a business decision. Assign the DDL implementer to produce an FK-to-index coverage check before handoff.

**Options:**
- A. DDL implementer verifies every FK is indexed or covered by a valid leftmost prefix.
- B. Owner supplies a different index policy.
- C. Other: ______

**DDL impact:** Yes for DDL completeness; no new business choice
**Source:** conventions line 29 and per-table `### Foreign Keys`/`### Indexes`.

## C. Provenance Audit

Status values in this table are restricted to `CONFIRMED`, `NOT CONFIRMED`, and `PROVENANCE CHECK REQUIRED`. “Confirmed” means the owner explicitly supplied that decision in the instructions available in this task context; it is not inferred from agent-authored dictionary prose.

| Decision | Current dictionary text | Explicit owner confirmation found? | Status |
|---|---|---|---|
| Reservation NULL semantics | `reservation_expires_at = NULL` means the checkout group currently holds no reservation | Yes; owner explicitly specified NULL meaning | `CONFIRMED` |
| Atomic reservation release | Expiry/cancel releases the whole checkout group; no partial split-order expiry | Yes; owner explicitly specified atomic group behavior | `CONFIRMED` |
| Deposit forfeiture beneficiary | Lender is default beneficiary; forfeiture does not create a new buyer cash IN if deposit already collected | Yes; owner explicitly specified lender and no new IN | `CONFIRMED` |
| Financial transaction direction | Dictionary gives directions for all eight transaction types | No complete owner-approved per-type mapping identified | `PROVENANCE CHECK REQUIRED` |
| `cash_impact` | Platform-fee and deposit constraints are explicitly owner-confirmed; complete per-type matrix is not | Partial only; full mapping needs owner confirmation | `PROVENANCE CHECK REQUIRED` |
| Payment reversal semantics | OUT only for returned settled funds; authorization void without cash is event-only | No explicit owner confirmation found for this exact rule | `PROVENANCE CHECK REQUIRED` |
| Payout retry transition | One obligation/order; `PROCESSING → FAILED → PROCESSING`; retries are attempts, not new obligations | Yes; owner explicitly specified | `CONFIRMED` |
| Payout account snapshot | Encrypted/tokenized provider reference for retry; no raw bank credentials; PAID snapshot immutable | Yes; owner explicitly specified | `CONFIRMED` |
| Payout-adjustment reversal | Do not mutate historical allocation; create reversal/adjustment record | Yes; owner explicitly specified | `CONFIRMED` |
| Adjustment allocation behavior | Canonical `payout_id`; immutable rows; do not add allocation status/idempotency absent decision | Yes; owner explicitly specified | `CONFIRMED` |

Other owner-confirmed rules to preserve, not re-open as undecided: payment states and no allocation status; buyer/seller/platform fee semantics and no buyer-payment double count; provider-event identity and internal NULL behavior; STORED generated uniqueness mode and active listing predicates; timestamp defaults; VND-only convention and MONEY/RATE precision. Any correction to these must be a new explicit owner decision.

## D. Unmarked Ambiguities

This register carries forward all **12** ambiguities identified in the preceding audit. Items may map to questions above; “not an owner decision” means the issue still must be closed, but can be assigned to DDL/service/documentation.

| # | Unmarked ambiguity | Classification | Decision-sheet coverage |
|---:|---|---|---|
| 1 | Generated uniqueness-column SQL datatype is absent for eight generated keys | DDL implementation detail, but must be resolved before DDL | Q045 |
| 2 | `sale_order_items` monetary columns have no currency column or explicit parent inheritance source | Owner decision | Q047 |
| 3 | `financial_transactions.status` has an allowlist requirement but no allowed values | Owner decision | Q025 |
| 4 | `payments.payment_method` and `payment_purpose` have no exact allowlists/explicit no-CHECK decision | Owner decision | Q017 |
| 5 | `user_violations.violation_type` and `notifications.notification_type` do not say whether values are finite or free-form | Owner decision | Q021 |
| 6 | Generated-column documentation is inconsistent about table-local STORED annotation/type inventory | Documentation only unless an owner changes the expressions/mode | Q046 |
| 7 | `platform_fees` target FK NULL/non-NULL matrix and fee-type scope mapping are not specified | Owner decision | Q034 |
| 8 | `financial_transactions` type-to-source enforcement says CHECK/service without assignment | Owner decision on enforcement assignment | Q025, Q063 |
| 9 | Several cross-table relationships permit composite FK or service enforcement without a final assignment | Owner decision for unresolved alternatives; already-explicit service invariants remain service layer | Q063 |
| 10 | Payout net arithmetic is qualified by an unspecified adjustments policy | Owner decision | Q035 |
| 11 | Partial refund effect on payment status is unspecified | Owner decision/service lifecycle | Q052 |
| 12 | FK index coverage is required but not mechanically proven | DDL implementation detail | Q067 |

## E. Marker Coverage and Inventory

The audit of the current Data Dictionary found **73 literal occurrences** of `[NEEDS CONFIRMATION]`:

- **68** occurrences are attached to table/column/constraint/business-rule content.
- **5** are documentation-only mentions: document status/warning/convention text at lines 3, 7, 31 and final-section heading/conclusion at lines 2564, 2582.
- The 68 substantive occurrences do not equal 68 questions: related columns are grouped above, while each affected column still requires an individual answer where indicated.
- The count and prior audit classification are unchanged: **63 A — DDL blockers, 2 C — service-layer items, 8 D — documentation/implementation items, 0 B — should-decide items**. The 63/2/8 sum to 73 when each marker occurrence is classified by its most direct impact; grouped questions reduce the owner response burden without dropping markers.

Marker-to-question coverage:

| Marker source lines | Covered by |
|---|---|
| 3, 7, 31 | Documentation-only mention; no separate owner decision |
| 68–69, 85, 92 | Q001, Q010, Q037 |
| 146 | Documentation/retention, no schema answer required |
| 162, 183–185 | Q002, Q010, Q029 |
| 220, 257, 294, 331, 372, 405, 448 | Q011 |
| 531 | Q028 |
| 567, 574 | Q038 |
| 611 | Q012 |
| 688, 725, 731 | Q012; line 731 is retention/documentation |
| 817, 860 | Q013, Q036 |
| 925–926, 944 | Q003, Q014 |
| 1001, 1039, 1073, 1083 | Q015, Q039 |
| 1183, 1214, 1216 | Q004, Q016, Q030 |
| 1281 | Q030 |
| 1335 | Q031 |
| 1362, 1373 | Q005, Q049 |
| 1449 | Q014 |
| 1508 | Q050 |
| 1569, 1582, 1589, 1626 | Q006, Q018, Q040 |
| 1664, 1671, 1675 | Q019, Q044 |
| 1732, 1741 | Q019, Q032, Q052 |
| 1777, 1786 | Q041, Q033 |
| 1932, 1944, 2002 | Q007, Q020 |
| 2059 | Q021 |
| 2125 | Q022 |
| 2158, 2183, 2185 | Q008, Q023, Q034 |
| 2208, 2217, 2223 | Q009, Q024, Q042 |
| 2329 | Q043 |
| 2390, 2398 | Q026; line 2398 retention is documentation/implementation |
| 2425, 2432 | Q027, Q060 |
| 2564, 2582 | Documentation-only mention; no separate owner decision |

## F. Final Checklist

- [ ] Q001 — User role/status defaults
- [ ] Q002 — Violation severity default
- [ ] Q003 — Borrow-term defaults
- [ ] Q004 — Checkout status default
- [ ] Q005 — Combo rounding-policy default
- [ ] Q006 — Shipment status default
- [ ] Q007 — Conversation type default
- [ ] Q008 — Platform-fee status default
- [ ] Q009 — Payout-account verification default
- [ ] Q010 — User/moderation allowlists
- [ ] Q011 — Reference-catalog status allowlists
- [ ] Q012 — Book/verification/evidence allowlists
- [ ] Q013 — Sale-combo status allowlist
- [ ] Q014 — Borrow/return-method allowlists
- [ ] Q015 — Request/interest/match allowlists
- [ ] Q016 — Checkout status allowlist
- [ ] Q017 — Payment method/purpose allowlists
- [ ] Q018 — Shipment/tracking status allowlists
- [ ] Q019 — Return/refund status allowlists
- [ ] Q020 — Conversation/message type allowlists
- [ ] Q021 — Notification/delivery/violation type allowlists
- [ ] Q022 — Report status allowlist
- [ ] Q023 — Fee type/status allowlists
- [ ] Q024 — Payout-account status/verification allowlists
- [ ] Q025 — Financial transaction types/status/source matrix
- [ ] Q026 — Financial-event type/status allowlists
- [ ] Q027 — Payout-adjustment type/status allowlists
- [ ] Q028 — Publication-year bounds
- [ ] Q029 — Violation resolved-at predicate
- [ ] Q030 — Checkout/order arithmetic
- [ ] Q031 — Sale-item combo allocation checks
- [ ] Q032 — Refund target NULL/XOR rules
- [ ] Q033 — Coupon rate/cap/currency checks
- [ ] Q034 — Platform-fee scope target matrix
- [ ] Q035 — Payout net arithmetic
- [ ] Q036 — Combo minimum item count/service rule
- [ ] Q037 — Email normalization/collation
- [ ] Q038 — Book identifier uniqueness scope
- [ ] Q039 — Request-match deduplication
- [ ] Q040 — Shipment tracking uniqueness
- [ ] Q041 — Coupon code normalization/collation
- [ ] Q042 — Payout provider-token uniqueness
- [ ] Q043 — Financial provider-reference uniqueness
- [ ] Q044 — Open-return generated predicate
- [ ] Q045 — Generated uniqueness-key SQL datatypes
- [ ] Q046 — Generated-column documentation consistency
- [ ] Q047 — Currency-column/inheritance map
- [ ] Q048 — VND-only and precision confirmation
- [ ] Q049 — Combo allocation rounding algorithm
- [ ] Q050 — Multiple payment attempts/successes
- [ ] Q051 — Payment allocation owner-decision transcription
- [ ] Q052 — Payment/refund lifecycle and partial refunds
- [ ] Q053 — Refund aggregate cap/enforcement
- [ ] Q054 — Reservation decision provenance
- [ ] Q055 — Platform-fee semantics provenance
- [ ] Q056 — Payout eligibility
- [ ] Q057 — Payout retry/attempt provenance
- [ ] Q058 — Payout snapshot provenance
- [ ] Q059 — Payment-reversal semantics provenance
- [ ] Q060 — Adjustment direction/recovery/offset lifecycle
- [ ] Q061 — Adjustment idempotency/allocation behavior
- [ ] Q062 — FK delete/update action provenance
- [ ] Q063 — Cross-table enforcement assignments
- [ ] Q064 — Idempotency-key scopes
- [ ] Q065 — Provider/internal financial-event identity provenance
- [ ] Q066 — Snapshot/completed-record immutability provenance
- [ ] Q067 — FK index coverage assigned and verified

### DDL Readiness Criteria

Do not mark `READY FOR DDL` until all of the following are satisfied:

- [ ] No DDL-blocking `[NEEDS CONFIRMATION]` remains.
- [ ] No DDL-blocking unmarked ambiguity remains.
- [ ] All status/type allowlists are confirmed separately per column.
- [ ] All defaults and `NULL`/`NOT NULL` decisions are confirmed.
- [ ] All UNIQUE scopes and idempotency scopes are confirmed.
- [ ] Generated expressions, STORED mode, and SQL datatypes are complete.
- [ ] Every money amount has an explicit currency column or named inheritance source; VND/precision/rounding are confirmed.
- [ ] All CHECK and arithmetic rules are complete or explicitly assigned to service layer.
- [ ] FK targets, `ON DELETE`, and `ON UPDATE` actions are approved.
- [ ] Payment, refund, reservation, fee, payout, and adjustment lifecycles are confirmed.
- [ ] Financial transaction source/direction/cash-impact/status mapping has owner provenance.
- [ ] Provider and internal idempotency rules are confirmed.
- [ ] Snapshot and completed-history immutability rules are assigned.
- [ ] Cross-table invariants are each assigned to DDL or service layer.
- [ ] DDL implementer has verified all FK indexes and generated-column compatibility against MySQL 8.0.16+.

**Current readiness:** `NOT READY FOR DDL` — owner decisions and provenance checks above remain open.
