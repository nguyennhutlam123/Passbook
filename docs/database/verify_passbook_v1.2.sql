-- Read-only metadata checks; select the target schema before running.
-- These checks do not connect to a database or modify schema/data.
SELECT DATABASE() AS selected_schema;

SELECT 'base_table_count' AS check_name, 57 AS expected_count,
       COUNT(*) AS actual_count,
       IF(COUNT(*) = 57, 'PASS', 'FAIL') AS result
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE';

WITH expected_tables AS (
    SELECT 'users' AS `table_name`
    UNION ALL
    SELECT 'user_addresses' AS `table_name`
    UNION ALL
    SELECT 'user_violations' AS `table_name`
    UNION ALL
    SELECT 'universities' AS `table_name`
    UNION ALL
    SELECT 'faculties' AS `table_name`
    UNION ALL
    SELECT 'majors' AS `table_name`
    UNION ALL
    SELECT 'subjects' AS `table_name`
    UNION ALL
    SELECT 'categories' AS `table_name`
    UNION ALL
    SELECT 'languages' AS `table_name`
    UNION ALL
    SELECT 'book_works' AS `table_name`
    UNION ALL
    SELECT 'book_work_subjects' AS `table_name`
    UNION ALL
    SELECT 'book_editions' AS `table_name`
    UNION ALL
    SELECT 'book_identifiers' AS `table_name`
    UNION ALL
    SELECT 'books' AS `table_name`
    UNION ALL
    SELECT 'book_images' AS `table_name`
    UNION ALL
    SELECT 'book_verifications' AS `table_name`
    UNION ALL
    SELECT 'verification_evidences' AS `table_name`
    UNION ALL
    SELECT 'sale_listings' AS `table_name`
    UNION ALL
    SELECT 'sale_combos' AS `table_name`
    UNION ALL
    SELECT 'sale_combo_items' AS `table_name`
    UNION ALL
    SELECT 'lend_listings' AS `table_name`
    UNION ALL
    SELECT 'borrow_terms' AS `table_name`
    UNION ALL
    SELECT 'book_requests' AS `table_name`
    UNION ALL
    SELECT 'request_interests' AS `table_name`
    UNION ALL
    SELECT 'request_matches' AS `table_name`
    UNION ALL
    SELECT 'carts' AS `table_name`
    UNION ALL
    SELECT 'cart_items' AS `table_name`
    UNION ALL
    SELECT 'checkout_groups' AS `table_name`
    UNION ALL
    SELECT 'orders' AS `table_name`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`
    UNION ALL
    SELECT 'sale_combo_order_items' AS `table_name`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`
    UNION ALL
    SELECT 'payments' AS `table_name`
    UNION ALL
    SELECT 'payment_allocations' AS `table_name`
    UNION ALL
    SELECT 'shipments' AS `table_name`
    UNION ALL
    SELECT 'shipment_tracking' AS `table_name`
    UNION ALL
    SELECT 'returns' AS `table_name`
    UNION ALL
    SELECT 'refunds' AS `table_name`
    UNION ALL
    SELECT 'coupons' AS `table_name`
    UNION ALL
    SELECT 'coupon_listings' AS `table_name`
    UNION ALL
    SELECT 'coupon_categories' AS `table_name`
    UNION ALL
    SELECT 'coupon_usages' AS `table_name`
    UNION ALL
    SELECT 'favorites' AS `table_name`
    UNION ALL
    SELECT 'conversations' AS `table_name`
    UNION ALL
    SELECT 'conversation_members' AS `table_name`
    UNION ALL
    SELECT 'messages' AS `table_name`
    UNION ALL
    SELECT 'notifications' AS `table_name`
    UNION ALL
    SELECT 'notification_deliveries' AS `table_name`
    UNION ALL
    SELECT 'reviews' AS `table_name`
    UNION ALL
    SELECT 'reports' AS `table_name`
    UNION ALL
    SELECT 'platform_fees' AS `table_name`
    UNION ALL
    SELECT 'seller_payout_accounts' AS `table_name`
    UNION ALL
    SELECT 'seller_payouts' AS `table_name`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`
    UNION ALL
    SELECT 'financial_transaction_events' AS `table_name`
    UNION ALL
    SELECT 'seller_payout_adjustments' AS `table_name`
    UNION ALL
    SELECT 'seller_payout_adjustment_allocations' AS `table_name`
)
SELECT 'expected_table_names' AS check_name,
       (SELECT COUNT(*) FROM expected_tables) AS expected_count,
       (SELECT COUNT(*) FROM expected_tables e
        JOIN information_schema.TABLES t
          ON t.TABLE_SCHEMA = DATABASE() AND t.TABLE_NAME = e.table_name
         AND t.TABLE_TYPE = 'BASE TABLE') AS actual_count,
       IF((SELECT COUNT(*) FROM expected_tables e
           JOIN information_schema.TABLES t
             ON t.TABLE_SCHEMA = DATABASE() AND t.TABLE_NAME = e.table_name
            AND t.TABLE_TYPE = 'BASE TABLE') = 57, 'PASS', 'FAIL') AS result;

WITH expected_tables AS (
    SELECT 'users' AS `table_name`
    UNION ALL
    SELECT 'user_addresses' AS `table_name`
    UNION ALL
    SELECT 'user_violations' AS `table_name`
    UNION ALL
    SELECT 'universities' AS `table_name`
    UNION ALL
    SELECT 'faculties' AS `table_name`
    UNION ALL
    SELECT 'majors' AS `table_name`
    UNION ALL
    SELECT 'subjects' AS `table_name`
    UNION ALL
    SELECT 'categories' AS `table_name`
    UNION ALL
    SELECT 'languages' AS `table_name`
    UNION ALL
    SELECT 'book_works' AS `table_name`
    UNION ALL
    SELECT 'book_work_subjects' AS `table_name`
    UNION ALL
    SELECT 'book_editions' AS `table_name`
    UNION ALL
    SELECT 'book_identifiers' AS `table_name`
    UNION ALL
    SELECT 'books' AS `table_name`
    UNION ALL
    SELECT 'book_images' AS `table_name`
    UNION ALL
    SELECT 'book_verifications' AS `table_name`
    UNION ALL
    SELECT 'verification_evidences' AS `table_name`
    UNION ALL
    SELECT 'sale_listings' AS `table_name`
    UNION ALL
    SELECT 'sale_combos' AS `table_name`
    UNION ALL
    SELECT 'sale_combo_items' AS `table_name`
    UNION ALL
    SELECT 'lend_listings' AS `table_name`
    UNION ALL
    SELECT 'borrow_terms' AS `table_name`
    UNION ALL
    SELECT 'book_requests' AS `table_name`
    UNION ALL
    SELECT 'request_interests' AS `table_name`
    UNION ALL
    SELECT 'request_matches' AS `table_name`
    UNION ALL
    SELECT 'carts' AS `table_name`
    UNION ALL
    SELECT 'cart_items' AS `table_name`
    UNION ALL
    SELECT 'checkout_groups' AS `table_name`
    UNION ALL
    SELECT 'orders' AS `table_name`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`
    UNION ALL
    SELECT 'sale_combo_order_items' AS `table_name`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`
    UNION ALL
    SELECT 'payments' AS `table_name`
    UNION ALL
    SELECT 'payment_allocations' AS `table_name`
    UNION ALL
    SELECT 'shipments' AS `table_name`
    UNION ALL
    SELECT 'shipment_tracking' AS `table_name`
    UNION ALL
    SELECT 'returns' AS `table_name`
    UNION ALL
    SELECT 'refunds' AS `table_name`
    UNION ALL
    SELECT 'coupons' AS `table_name`
    UNION ALL
    SELECT 'coupon_listings' AS `table_name`
    UNION ALL
    SELECT 'coupon_categories' AS `table_name`
    UNION ALL
    SELECT 'coupon_usages' AS `table_name`
    UNION ALL
    SELECT 'favorites' AS `table_name`
    UNION ALL
    SELECT 'conversations' AS `table_name`
    UNION ALL
    SELECT 'conversation_members' AS `table_name`
    UNION ALL
    SELECT 'messages' AS `table_name`
    UNION ALL
    SELECT 'notifications' AS `table_name`
    UNION ALL
    SELECT 'notification_deliveries' AS `table_name`
    UNION ALL
    SELECT 'reviews' AS `table_name`
    UNION ALL
    SELECT 'reports' AS `table_name`
    UNION ALL
    SELECT 'platform_fees' AS `table_name`
    UNION ALL
    SELECT 'seller_payout_accounts' AS `table_name`
    UNION ALL
    SELECT 'seller_payouts' AS `table_name`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`
    UNION ALL
    SELECT 'financial_transaction_events' AS `table_name`
    UNION ALL
    SELECT 'seller_payout_adjustments' AS `table_name`
    UNION ALL
    SELECT 'seller_payout_adjustment_allocations' AS `table_name`
)
SELECT 'unexpected_base_tables' AS check_name,
       COUNT(*) AS actual_count, IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM information_schema.TABLES t
LEFT JOIN expected_tables e ON e.table_name = t.TABLE_NAME
WHERE t.TABLE_SCHEMA = DATABASE() AND t.TABLE_TYPE = 'BASE TABLE'
  AND e.table_name IS NULL;

SELECT 'primary_key_table_count' AS check_name, 57 AS expected_count,
       COUNT(DISTINCT TABLE_NAME) AS actual_count,
       IF(COUNT(DISTINCT TABLE_NAME) = 57, 'PASS', 'FAIL') AS result
FROM information_schema.TABLE_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_TYPE = 'PRIMARY KEY';

SELECT 'primary_key_column_count' AS check_name, 62 AS expected_count,
       COUNT(*) AS actual_count,
       IF(COUNT(*) = 62, 'PASS', 'FAIL') AS result
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE() AND INDEX_NAME = 'PRIMARY';

WITH expected_pk_columns AS (
    SELECT 'users' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'user_addresses' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'user_violations' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'universities' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'faculties' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'majors' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'subjects' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'categories' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'languages' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'book_works' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'book_work_subjects' AS `table_name`, 1 AS `ordinal_position`, 'book_work_id' AS `column_name`
    UNION ALL
    SELECT 'book_work_subjects' AS `table_name`, 2 AS `ordinal_position`, 'subject_id' AS `column_name`
    UNION ALL
    SELECT 'book_editions' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'book_identifiers' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'books' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'book_images' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'book_verifications' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'verification_evidences' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'sale_listings' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'sale_combos' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'sale_combo_items' AS `table_name`, 1 AS `ordinal_position`, 'combo_id' AS `column_name`
    UNION ALL
    SELECT 'sale_combo_items' AS `table_name`, 2 AS `ordinal_position`, 'sale_listing_id' AS `column_name`
    UNION ALL
    SELECT 'lend_listings' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'borrow_terms' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'book_requests' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'request_interests' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'request_matches' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'carts' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'checkout_groups' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'orders' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'sale_combo_order_items' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'payments' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'payment_allocations' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'shipments' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'shipment_tracking' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'returns' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'coupons' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'coupon_listings' AS `table_name`, 1 AS `ordinal_position`, 'coupon_id' AS `column_name`
    UNION ALL
    SELECT 'coupon_listings' AS `table_name`, 2 AS `ordinal_position`, 'sale_listing_id' AS `column_name`
    UNION ALL
    SELECT 'coupon_categories' AS `table_name`, 1 AS `ordinal_position`, 'coupon_id' AS `column_name`
    UNION ALL
    SELECT 'coupon_categories' AS `table_name`, 2 AS `ordinal_position`, 'category_id' AS `column_name`
    UNION ALL
    SELECT 'coupon_usages' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'conversations' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'conversation_members' AS `table_name`, 1 AS `ordinal_position`, 'conversation_id' AS `column_name`
    UNION ALL
    SELECT 'conversation_members' AS `table_name`, 2 AS `ordinal_position`, 'user_id' AS `column_name`
    UNION ALL
    SELECT 'messages' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'notifications' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'notification_deliveries' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'reviews' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'reports' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'platform_fees' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'seller_payout_accounts' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'seller_payouts' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'financial_transaction_events' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'seller_payout_adjustments' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'seller_payout_adjustment_allocations' AS `table_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
)
SELECT e.table_name, e.ordinal_position, e.column_name
FROM expected_pk_columns e
LEFT JOIN information_schema.STATISTICS s
  ON s.TABLE_SCHEMA = DATABASE() AND s.TABLE_NAME = e.table_name
 AND s.INDEX_NAME = 'PRIMARY' AND s.SEQ_IN_INDEX = e.ordinal_position
WHERE s.COLUMN_NAME IS NULL OR s.COLUMN_NAME <> e.column_name;

SELECT 'foreign_key_count' AS check_name, 134 AS expected_count,
       COUNT(*) AS actual_count,
       IF(COUNT(*) = 134, 'PASS', 'FAIL') AS result
FROM information_schema.TABLE_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_TYPE = 'FOREIGN KEY';

WITH fk_columns AS (
    SELECT TABLE_NAME, CONSTRAINT_NAME,
           COUNT(*) AS column_count,
           GROUP_CONCAT(COLUMN_NAME ORDER BY ORDINAL_POSITION) AS fk_columns
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE CONSTRAINT_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
    GROUP BY TABLE_NAME, CONSTRAINT_NAME
), index_columns AS (
    SELECT TABLE_NAME, INDEX_NAME, COUNT(*) AS column_count,
           GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS index_columns
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
    GROUP BY TABLE_NAME, INDEX_NAME
)
SELECT f.TABLE_NAME, f.CONSTRAINT_NAME
FROM fk_columns f
WHERE NOT EXISTS (
    SELECT 1 FROM index_columns i
    WHERE i.TABLE_NAME = f.TABLE_NAME
      AND i.column_count >= f.column_count
      AND SUBSTRING_INDEX(i.index_columns, ',', f.column_count) = f.fk_columns
);

WITH expected_fk_columns AS (
    SELECT 'users' AS `table_name`, 'fk_users_1' AS `constraint_name`, 1 AS `ordinal_position`, 'university_id' AS `column_name`, 'universities' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'users' AS `table_name`, 'fk_users_2' AS `constraint_name`, 1 AS `ordinal_position`, 'faculty_id' AS `column_name`, 'faculties' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'users' AS `table_name`, 'fk_users_2' AS `constraint_name`, 2 AS `ordinal_position`, 'university_id' AS `column_name`, 'faculties' AS `referenced_table_name`, 'university_id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'users' AS `table_name`, 'fk_users_3' AS `constraint_name`, 1 AS `ordinal_position`, 'major_id' AS `column_name`, 'majors' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'users' AS `table_name`, 'fk_users_3' AS `constraint_name`, 2 AS `ordinal_position`, 'faculty_id' AS `column_name`, 'majors' AS `referenced_table_name`, 'faculty_id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'user_addresses' AS `table_name`, 'fk_user_addresses_1' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'user_violations' AS `table_name`, 'fk_user_violations_1' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'user_violations' AS `table_name`, 'fk_user_violations_2' AS `constraint_name`, 1 AS `ordinal_position`, 'created_by' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'SET NULL' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'faculties' AS `table_name`, 'fk_faculties_1' AS `constraint_name`, 1 AS `ordinal_position`, 'university_id' AS `column_name`, 'universities' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'majors' AS `table_name`, 'fk_majors_1' AS `constraint_name`, 1 AS `ordinal_position`, 'faculty_id' AS `column_name`, 'faculties' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'categories' AS `table_name`, 'fk_categories_1' AS `constraint_name`, 1 AS `ordinal_position`, 'parent_id' AS `column_name`, 'categories' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_works' AS `table_name`, 'fk_book_works_1' AS `constraint_name`, 1 AS `ordinal_position`, 'category_id' AS `column_name`, 'categories' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_works' AS `table_name`, 'fk_book_works_2' AS `constraint_name`, 1 AS `ordinal_position`, 'created_by' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_work_subjects' AS `table_name`, 'fk_book_work_subjects_1' AS `constraint_name`, 1 AS `ordinal_position`, 'book_work_id' AS `column_name`, 'book_works' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_work_subjects' AS `table_name`, 'fk_book_work_subjects_2' AS `constraint_name`, 1 AS `ordinal_position`, 'subject_id' AS `column_name`, 'subjects' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_editions' AS `table_name`, 'fk_book_editions_1' AS `constraint_name`, 1 AS `ordinal_position`, 'book_work_id' AS `column_name`, 'book_works' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_editions' AS `table_name`, 'fk_book_editions_2' AS `constraint_name`, 1 AS `ordinal_position`, 'language_id' AS `column_name`, 'languages' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_identifiers' AS `table_name`, 'fk_book_identifiers_1' AS `constraint_name`, 1 AS `ordinal_position`, 'book_edition_id' AS `column_name`, 'book_editions' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'books' AS `table_name`, 'fk_books_1' AS `constraint_name`, 1 AS `ordinal_position`, 'book_edition_id' AS `column_name`, 'book_editions' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'books' AS `table_name`, 'fk_books_2' AS `constraint_name`, 1 AS `ordinal_position`, 'owner_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_images' AS `table_name`, 'fk_book_images_1' AS `constraint_name`, 1 AS `ordinal_position`, 'book_id' AS `column_name`, 'books' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_verifications' AS `table_name`, 'fk_book_verifications_1' AS `constraint_name`, 1 AS `ordinal_position`, 'book_id' AS `column_name`, 'books' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_verifications' AS `table_name`, 'fk_book_verifications_2' AS `constraint_name`, 1 AS `ordinal_position`, 'verifier_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'SET NULL' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'verification_evidences' AS `table_name`, 'fk_verification_evidences_1' AS `constraint_name`, 1 AS `ordinal_position`, 'verification_id' AS `column_name`, 'book_verifications' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_listings' AS `table_name`, 'fk_sale_listings_1' AS `constraint_name`, 1 AS `ordinal_position`, 'book_id' AS `column_name`, 'books' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_listings' AS `table_name`, 'fk_sale_listings_2' AS `constraint_name`, 1 AS `ordinal_position`, 'seller_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_combos' AS `table_name`, 'fk_sale_combos_1' AS `constraint_name`, 1 AS `ordinal_position`, 'seller_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_combo_items' AS `table_name`, 'fk_sale_combo_items_1' AS `constraint_name`, 1 AS `ordinal_position`, 'combo_id' AS `column_name`, 'sale_combos' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_combo_items' AS `table_name`, 'fk_sale_combo_items_1' AS `constraint_name`, 2 AS `ordinal_position`, 'seller_id' AS `column_name`, 'sale_combos' AS `referenced_table_name`, 'seller_id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_combo_items' AS `table_name`, 'fk_sale_combo_items_2' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_listing_id' AS `column_name`, 'sale_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_combo_items' AS `table_name`, 'fk_sale_combo_items_2' AS `constraint_name`, 2 AS `ordinal_position`, 'seller_id' AS `column_name`, 'sale_listings' AS `referenced_table_name`, 'seller_id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_combo_items' AS `table_name`, 'fk_sale_combo_items_3' AS `constraint_name`, 1 AS `ordinal_position`, 'seller_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'lend_listings' AS `table_name`, 'fk_lend_listings_1' AS `constraint_name`, 1 AS `ordinal_position`, 'book_id' AS `column_name`, 'books' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'lend_listings' AS `table_name`, 'fk_lend_listings_2' AS `constraint_name`, 1 AS `ordinal_position`, 'lender_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'borrow_terms' AS `table_name`, 'fk_borrow_terms_1' AS `constraint_name`, 1 AS `ordinal_position`, 'lend_listing_id' AS `column_name`, 'lend_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_requests' AS `table_name`, 'fk_book_requests_1' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_requests' AS `table_name`, 'fk_book_requests_2' AS `constraint_name`, 1 AS `ordinal_position`, 'book_work_id' AS `column_name`, 'book_works' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'book_requests' AS `table_name`, 'fk_book_requests_3' AS `constraint_name`, 1 AS `ordinal_position`, 'category_id' AS `column_name`, 'categories' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'request_interests' AS `table_name`, 'fk_request_interests_1' AS `constraint_name`, 1 AS `ordinal_position`, 'request_id' AS `column_name`, 'book_requests' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'request_interests' AS `table_name`, 'fk_request_interests_2' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'request_matches' AS `table_name`, 'fk_request_matches_1' AS `constraint_name`, 1 AS `ordinal_position`, 'request_id' AS `column_name`, 'book_requests' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'request_matches' AS `table_name`, 'fk_request_matches_2' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_listing_id' AS `column_name`, 'sale_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'request_matches' AS `table_name`, 'fk_request_matches_3' AS `constraint_name`, 1 AS `ordinal_position`, 'lend_listing_id' AS `column_name`, 'lend_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'carts' AS `table_name`, 'fk_carts_1' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'fk_cart_items_1' AS `constraint_name`, 1 AS `ordinal_position`, 'cart_id' AS `column_name`, 'carts' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'fk_cart_items_2' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_listing_id' AS `column_name`, 'sale_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'fk_cart_items_3' AS `constraint_name`, 1 AS `ordinal_position`, 'lend_listing_id' AS `column_name`, 'lend_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'fk_cart_items_4' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_combo_id' AS `column_name`, 'sale_combos' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'checkout_groups' AS `table_name`, 'fk_checkout_groups_1' AS `constraint_name`, 1 AS `ordinal_position`, 'cart_id' AS `column_name`, 'carts' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'checkout_groups' AS `table_name`, 'fk_checkout_groups_2' AS `constraint_name`, 1 AS `ordinal_position`, 'buyer_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'orders' AS `table_name`, 'fk_orders_1' AS `constraint_name`, 1 AS `ordinal_position`, 'checkout_group_id' AS `column_name`, 'checkout_groups' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'orders' AS `table_name`, 'fk_orders_2' AS `constraint_name`, 1 AS `ordinal_position`, 'buyer_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'orders' AS `table_name`, 'fk_orders_3' AS `constraint_name`, 1 AS `ordinal_position`, 'seller_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`, 'fk_sale_order_items_1' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`, 'fk_sale_order_items_2' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_listing_id' AS `column_name`, 'sale_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`, 'fk_sale_order_items_3' AS `constraint_name`, 1 AS `ordinal_position`, 'book_id' AS `column_name`, 'books' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`, 'fk_sale_order_items_4' AS `constraint_name`, 1 AS `ordinal_position`, 'seller_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`, 'fk_sale_order_items_5' AS `constraint_name`, 1 AS `ordinal_position`, 'combo_order_item_id' AS `column_name`, 'sale_combo_order_items' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_combo_order_items' AS `table_name`, 'fk_sale_combo_order_items_1' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_combo_order_items' AS `table_name`, 'fk_sale_combo_order_items_2' AS `constraint_name`, 1 AS `ordinal_position`, 'combo_id' AS `column_name`, 'sale_combos' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'sale_combo_order_items' AS `table_name`, 'fk_sale_combo_order_items_3' AS `constraint_name`, 1 AS `ordinal_position`, 'seller_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'fk_borrow_orders_1' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'fk_borrow_orders_2' AS `constraint_name`, 1 AS `ordinal_position`, 'checkout_group_id' AS `column_name`, 'checkout_groups' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'fk_borrow_orders_3' AS `constraint_name`, 1 AS `ordinal_position`, 'lend_listing_id' AS `column_name`, 'lend_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'fk_borrow_orders_4' AS `constraint_name`, 1 AS `ordinal_position`, 'lender_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'fk_borrow_orders_5' AS `constraint_name`, 1 AS `ordinal_position`, 'borrower_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'fk_borrow_orders_6' AS `constraint_name`, 1 AS `ordinal_position`, 'return_requested_by' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'SET NULL' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'payments' AS `table_name`, 'fk_payments_1' AS `constraint_name`, 1 AS `ordinal_position`, 'checkout_group_id' AS `column_name`, 'checkout_groups' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'payments' AS `table_name`, 'fk_payments_2' AS `constraint_name`, 1 AS `ordinal_position`, 'payer_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'payment_allocations' AS `table_name`, 'fk_payment_allocations_1' AS `constraint_name`, 1 AS `ordinal_position`, 'payment_id' AS `column_name`, 'payments' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'payment_allocations' AS `table_name`, 'fk_payment_allocations_2' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'shipments' AS `table_name`, 'fk_shipments_1' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'shipment_tracking' AS `table_name`, 'fk_shipment_tracking_1' AS `constraint_name`, 1 AS `ordinal_position`, 'shipment_id' AS `column_name`, 'shipments' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'returns' AS `table_name`, 'fk_returns_1' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'returns' AS `table_name`, 'fk_returns_2' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_order_item_id' AS `column_name`, 'sale_order_items' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'returns' AS `table_name`, 'fk_returns_3' AS `constraint_name`, 1 AS `ordinal_position`, 'requested_by' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'fk_refunds_1' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'fk_refunds_2' AS `constraint_name`, 1 AS `ordinal_position`, 'payment_allocation_id' AS `column_name`, 'payment_allocations' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'fk_refunds_3' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_order_item_id' AS `column_name`, 'sale_order_items' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'fk_refunds_4' AS `constraint_name`, 1 AS `ordinal_position`, 'borrow_order_id' AS `column_name`, 'borrow_orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'fk_refunds_5' AS `constraint_name`, 1 AS `ordinal_position`, 'return_id' AS `column_name`, 'returns' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'fk_refunds_6' AS `constraint_name`, 1 AS `ordinal_position`, 'requested_by' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'SET NULL' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'coupons' AS `table_name`, 'fk_coupons_1' AS `constraint_name`, 1 AS `ordinal_position`, 'seller_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'coupon_listings' AS `table_name`, 'fk_coupon_listings_1' AS `constraint_name`, 1 AS `ordinal_position`, 'coupon_id' AS `column_name`, 'coupons' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'coupon_listings' AS `table_name`, 'fk_coupon_listings_2' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_listing_id' AS `column_name`, 'sale_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'coupon_categories' AS `table_name`, 'fk_coupon_categories_1' AS `constraint_name`, 1 AS `ordinal_position`, 'coupon_id' AS `column_name`, 'coupons' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'CASCADE' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'coupon_categories' AS `table_name`, 'fk_coupon_categories_2' AS `constraint_name`, 1 AS `ordinal_position`, 'category_id' AS `column_name`, 'categories' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'coupon_usages' AS `table_name`, 'fk_coupon_usages_1' AS `constraint_name`, 1 AS `ordinal_position`, 'coupon_id' AS `column_name`, 'coupons' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'coupon_usages' AS `table_name`, 'fk_coupon_usages_2' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'coupon_usages' AS `table_name`, 'fk_coupon_usages_3' AS `constraint_name`, 1 AS `ordinal_position`, 'checkout_group_id' AS `column_name`, 'checkout_groups' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'fk_favorites_1' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'fk_favorites_2' AS `constraint_name`, 1 AS `ordinal_position`, 'book_id' AS `column_name`, 'books' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'fk_favorites_3' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_listing_id' AS `column_name`, 'sale_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'fk_favorites_4' AS `constraint_name`, 1 AS `ordinal_position`, 'lend_listing_id' AS `column_name`, 'lend_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'conversation_members' AS `table_name`, 'fk_conversation_members_1' AS `constraint_name`, 1 AS `ordinal_position`, 'conversation_id' AS `column_name`, 'conversations' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'conversation_members' AS `table_name`, 'fk_conversation_members_2' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'messages' AS `table_name`, 'fk_messages_1' AS `constraint_name`, 1 AS `ordinal_position`, 'conversation_id' AS `column_name`, 'conversations' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'messages' AS `table_name`, 'fk_messages_2' AS `constraint_name`, 1 AS `ordinal_position`, 'sender_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'notifications' AS `table_name`, 'fk_notifications_1' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'notification_deliveries' AS `table_name`, 'fk_notification_deliveries_1' AS `constraint_name`, 1 AS `ordinal_position`, 'notification_id' AS `column_name`, 'notifications' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reviews' AS `table_name`, 'fk_reviews_1' AS `constraint_name`, 1 AS `ordinal_position`, 'reviewer_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reviews' AS `table_name`, 'fk_reviews_2' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reviews' AS `table_name`, 'fk_reviews_3' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_listing_id' AS `column_name`, 'sale_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reviews' AS `table_name`, 'fk_reviews_4' AS `constraint_name`, 1 AS `ordinal_position`, 'lend_listing_id' AS `column_name`, 'lend_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reports' AS `table_name`, 'fk_reports_1' AS `constraint_name`, 1 AS `ordinal_position`, 'reporter_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reports' AS `table_name`, 'fk_reports_2' AS `constraint_name`, 1 AS `ordinal_position`, 'reported_user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reports' AS `table_name`, 'fk_reports_3' AS `constraint_name`, 1 AS `ordinal_position`, 'book_id' AS `column_name`, 'books' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reports' AS `table_name`, 'fk_reports_4' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_listing_id' AS `column_name`, 'sale_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reports' AS `table_name`, 'fk_reports_5' AS `constraint_name`, 1 AS `ordinal_position`, 'lend_listing_id' AS `column_name`, 'lend_listings' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reports' AS `table_name`, 'fk_reports_6' AS `constraint_name`, 1 AS `ordinal_position`, 'message_id' AS `column_name`, 'messages' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'reports' AS `table_name`, 'fk_reports_7' AS `constraint_name`, 1 AS `ordinal_position`, 'handled_by' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'SET NULL' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'platform_fees' AS `table_name`, 'fk_platform_fees_1' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'platform_fees' AS `table_name`, 'fk_platform_fees_2' AS `constraint_name`, 1 AS `ordinal_position`, 'sale_order_item_id' AS `column_name`, 'sale_order_items' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'platform_fees' AS `table_name`, 'fk_platform_fees_3' AS `constraint_name`, 1 AS `ordinal_position`, 'borrow_order_id' AS `column_name`, 'borrow_orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'platform_fees' AS `table_name`, 'fk_platform_fees_4' AS `constraint_name`, 1 AS `ordinal_position`, 'payment_id' AS `column_name`, 'payments' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'platform_fees' AS `table_name`, 'fk_platform_fees_5' AS `constraint_name`, 1 AS `ordinal_position`, 'recipient_user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'seller_payout_accounts' AS `table_name`, 'fk_seller_payout_accounts_1' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'seller_payouts' AS `table_name`, 'fk_seller_payouts_1' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'seller_payouts' AS `table_name`, 'fk_seller_payouts_2' AS `constraint_name`, 1 AS `ordinal_position`, 'recipient_user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'seller_payouts' AS `table_name`, 'fk_seller_payouts_3' AS `constraint_name`, 1 AS `ordinal_position`, 'payout_account_id' AS `column_name`, 'seller_payout_accounts' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_1' AS `constraint_name`, 1 AS `ordinal_position`, 'checkout_group_id' AS `column_name`, 'checkout_groups' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_2' AS `constraint_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`, 'orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_3' AS `constraint_name`, 1 AS `ordinal_position`, 'payment_id' AS `column_name`, 'payments' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_4' AS `constraint_name`, 1 AS `ordinal_position`, 'payment_allocation_id' AS `column_name`, 'payment_allocations' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_5' AS `constraint_name`, 1 AS `ordinal_position`, 'payout_id' AS `column_name`, 'seller_payouts' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_6' AS `constraint_name`, 1 AS `ordinal_position`, 'platform_fee_id' AS `column_name`, 'platform_fees' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_7' AS `constraint_name`, 1 AS `ordinal_position`, 'refund_id' AS `column_name`, 'refunds' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_8' AS `constraint_name`, 1 AS `ordinal_position`, 'payout_adjustment_id' AS `column_name`, 'seller_payout_adjustments' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_9' AS `constraint_name`, 1 AS `ordinal_position`, 'borrow_order_id' AS `column_name`, 'borrow_orders' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_10' AS `constraint_name`, 1 AS `ordinal_position`, 'recipient_user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'fk_financial_transactions_11' AS `constraint_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transaction_events' AS `table_name`, 'fk_financial_transaction_events_1' AS `constraint_name`, 1 AS `ordinal_position`, 'financial_transaction_id' AS `column_name`, 'financial_transactions' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'financial_transaction_events' AS `table_name`, 'fk_financial_transaction_events_2' AS `constraint_name`, 1 AS `ordinal_position`, 'actor_user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'SET NULL' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'seller_payout_adjustments' AS `table_name`, 'fk_seller_payout_adjustments_1' AS `constraint_name`, 1 AS `ordinal_position`, 'recipient_user_id' AS `column_name`, 'users' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'seller_payout_adjustments' AS `table_name`, 'fk_seller_payout_adjustments_2' AS `constraint_name`, 1 AS `ordinal_position`, 'original_payout_id' AS `column_name`, 'seller_payouts' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'seller_payout_adjustments' AS `table_name`, 'fk_seller_payout_adjustments_3' AS `constraint_name`, 1 AS `ordinal_position`, 'refund_id' AS `column_name`, 'refunds' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'seller_payout_adjustment_allocations' AS `table_name`, 'fk_seller_payout_adjustment_allocations_1' AS `constraint_name`, 1 AS `ordinal_position`, 'adjustment_id' AS `column_name`, 'seller_payout_adjustments' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
    UNION ALL
    SELECT 'seller_payout_adjustment_allocations' AS `table_name`, 'fk_seller_payout_adjustment_allocations_2' AS `constraint_name`, 1 AS `ordinal_position`, 'payout_id' AS `column_name`, 'seller_payouts' AS `referenced_table_name`, 'id' AS `referenced_column_name`, 'RESTRICT' AS `delete_rule`, 'CASCADE' AS `update_rule`
)
SELECT e.table_name, e.constraint_name, e.ordinal_position, e.column_name,
       e.referenced_table_name, e.referenced_column_name,
       e.delete_rule AS expected_delete_rule, e.update_rule AS expected_update_rule,
       kcu.REFERENCED_TABLE_NAME AS actual_referenced_table,
       kcu.REFERENCED_COLUMN_NAME AS actual_referenced_column,
       rc.DELETE_RULE AS actual_delete_rule, rc.UPDATE_RULE AS actual_update_rule
FROM expected_fk_columns e
LEFT JOIN information_schema.KEY_COLUMN_USAGE kcu
  ON kcu.CONSTRAINT_SCHEMA = DATABASE() AND kcu.TABLE_NAME = e.table_name
 AND kcu.CONSTRAINT_NAME = e.constraint_name
 AND kcu.ORDINAL_POSITION = e.ordinal_position
LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
  ON rc.CONSTRAINT_SCHEMA = DATABASE() AND rc.TABLE_NAME = e.table_name
 AND rc.CONSTRAINT_NAME = e.constraint_name
WHERE kcu.COLUMN_NAME IS NULL OR kcu.COLUMN_NAME <> e.column_name
   OR kcu.REFERENCED_TABLE_NAME <> e.referenced_table_name
   OR kcu.REFERENCED_COLUMN_NAME <> e.referenced_column_name
   OR rc.DELETE_RULE <> e.delete_rule OR rc.UPDATE_RULE <> e.update_rule;

SELECT 'unique_index_count' AS check_name, 54 AS expected_count,
       COUNT(DISTINCT TABLE_NAME, INDEX_NAME) AS actual_count,
       IF(COUNT(DISTINCT TABLE_NAME, INDEX_NAME) = 54, 'PASS', 'FAIL') AS result
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE() AND NON_UNIQUE = 0 AND INDEX_NAME <> 'PRIMARY';

WITH expected_unique_columns AS (
    SELECT 'users' AS `table_name`, 'uq_users_1' AS `index_name`, 1 AS `ordinal_position`, 'email' AS `column_name`
    UNION ALL
    SELECT 'user_addresses' AS `table_name`, 'uq_user_addresses_1' AS `index_name`, 1 AS `ordinal_position`, 'default_address_user_key' AS `column_name`
    UNION ALL
    SELECT 'universities' AS `table_name`, 'uq_universities_1' AS `index_name`, 1 AS `ordinal_position`, 'code' AS `column_name`
    UNION ALL
    SELECT 'faculties' AS `table_name`, 'uq_faculties_1' AS `index_name`, 1 AS `ordinal_position`, 'university_id' AS `column_name`
    UNION ALL
    SELECT 'faculties' AS `table_name`, 'uq_faculties_1' AS `index_name`, 2 AS `ordinal_position`, 'code' AS `column_name`
    UNION ALL
    SELECT 'faculties' AS `table_name`, 'uq_faculties_2' AS `index_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'faculties' AS `table_name`, 'uq_faculties_2' AS `index_name`, 2 AS `ordinal_position`, 'university_id' AS `column_name`
    UNION ALL
    SELECT 'majors' AS `table_name`, 'uq_majors_1' AS `index_name`, 1 AS `ordinal_position`, 'faculty_id' AS `column_name`
    UNION ALL
    SELECT 'majors' AS `table_name`, 'uq_majors_1' AS `index_name`, 2 AS `ordinal_position`, 'code' AS `column_name`
    UNION ALL
    SELECT 'majors' AS `table_name`, 'uq_majors_2' AS `index_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'majors' AS `table_name`, 'uq_majors_2' AS `index_name`, 2 AS `ordinal_position`, 'faculty_id' AS `column_name`
    UNION ALL
    SELECT 'subjects' AS `table_name`, 'uq_subjects_1' AS `index_name`, 1 AS `ordinal_position`, 'code' AS `column_name`
    UNION ALL
    SELECT 'categories' AS `table_name`, 'uq_categories_1' AS `index_name`, 1 AS `ordinal_position`, 'slug' AS `column_name`
    UNION ALL
    SELECT 'languages' AS `table_name`, 'uq_languages_1' AS `index_name`, 1 AS `ordinal_position`, 'code' AS `column_name`
    UNION ALL
    SELECT 'book_work_subjects' AS `table_name`, 'uq_book_work_subjects_1' AS `index_name`, 1 AS `ordinal_position`, 'primary_subject_work_key' AS `column_name`
    UNION ALL
    SELECT 'book_identifiers' AS `table_name`, 'uq_book_identifiers_1' AS `index_name`, 1 AS `ordinal_position`, 'identifier_type' AS `column_name`
    UNION ALL
    SELECT 'book_identifiers' AS `table_name`, 'uq_book_identifiers_1' AS `index_name`, 2 AS `ordinal_position`, 'identifier_value' AS `column_name`
    UNION ALL
    SELECT 'book_images' AS `table_name`, 'uq_book_images_1' AS `index_name`, 1 AS `ordinal_position`, 'primary_image_book_key' AS `column_name`
    UNION ALL
    SELECT 'sale_listings' AS `table_name`, 'uq_sale_listings_1' AS `index_name`, 1 AS `ordinal_position`, 'active_sale_book_key' AS `column_name`
    UNION ALL
    SELECT 'sale_listings' AS `table_name`, 'uq_sale_listings_2' AS `index_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'sale_listings' AS `table_name`, 'uq_sale_listings_2' AS `index_name`, 2 AS `ordinal_position`, 'seller_id' AS `column_name`
    UNION ALL
    SELECT 'sale_combos' AS `table_name`, 'uq_sale_combos_1' AS `index_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'sale_combos' AS `table_name`, 'uq_sale_combos_1' AS `index_name`, 2 AS `ordinal_position`, 'seller_id' AS `column_name`
    UNION ALL
    SELECT 'lend_listings' AS `table_name`, 'uq_lend_listings_1' AS `index_name`, 1 AS `ordinal_position`, 'active_lend_book_key' AS `column_name`
    UNION ALL
    SELECT 'borrow_terms' AS `table_name`, 'uq_borrow_terms_1' AS `index_name`, 1 AS `ordinal_position`, 'lend_listing_id' AS `column_name`
    UNION ALL
    SELECT 'request_interests' AS `table_name`, 'uq_request_interests_1' AS `index_name`, 1 AS `ordinal_position`, 'request_id' AS `column_name`
    UNION ALL
    SELECT 'request_interests' AS `table_name`, 'uq_request_interests_1' AS `index_name`, 2 AS `ordinal_position`, 'user_id' AS `column_name`
    UNION ALL
    SELECT 'carts' AS `table_name`, 'uq_carts_1' AS `index_name`, 1 AS `ordinal_position`, 'active_cart_user_key' AS `column_name`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'uq_cart_items_1' AS `index_name`, 1 AS `ordinal_position`, 'cart_id' AS `column_name`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'uq_cart_items_1' AS `index_name`, 2 AS `ordinal_position`, 'sale_listing_id' AS `column_name`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'uq_cart_items_2' AS `index_name`, 1 AS `ordinal_position`, 'cart_id' AS `column_name`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'uq_cart_items_2' AS `index_name`, 2 AS `ordinal_position`, 'lend_listing_id' AS `column_name`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'uq_cart_items_3' AS `index_name`, 1 AS `ordinal_position`, 'cart_id' AS `column_name`
    UNION ALL
    SELECT 'cart_items' AS `table_name`, 'uq_cart_items_3' AS `index_name`, 2 AS `ordinal_position`, 'sale_combo_id' AS `column_name`
    UNION ALL
    SELECT 'checkout_groups' AS `table_name`, 'uq_checkout_groups_1' AS `index_name`, 1 AS `ordinal_position`, 'checkout_code' AS `column_name`
    UNION ALL
    SELECT 'checkout_groups' AS `table_name`, 'uq_checkout_groups_2' AS `index_name`, 1 AS `ordinal_position`, 'buyer_id' AS `column_name`
    UNION ALL
    SELECT 'checkout_groups' AS `table_name`, 'uq_checkout_groups_2' AS `index_name`, 2 AS `ordinal_position`, 'idempotency_key' AS `column_name`
    UNION ALL
    SELECT 'orders' AS `table_name`, 'uq_orders_1' AS `index_name`, 1 AS `ordinal_position`, 'order_code' AS `column_name`
    UNION ALL
    SELECT 'orders' AS `table_name`, 'uq_orders_2' AS `index_name`, 1 AS `ordinal_position`, 'checkout_group_id' AS `column_name`
    UNION ALL
    SELECT 'orders' AS `table_name`, 'uq_orders_2' AS `index_name`, 2 AS `ordinal_position`, 'sale_seller_key' AS `column_name`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`, 'uq_sale_order_items_1' AS `index_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`
    UNION ALL
    SELECT 'sale_order_items' AS `table_name`, 'uq_sale_order_items_1' AS `index_name`, 2 AS `ordinal_position`, 'sale_listing_id' AS `column_name`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'uq_borrow_orders_1' AS `index_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'uq_borrow_orders_2' AS `index_name`, 1 AS `ordinal_position`, 'checkout_group_id' AS `column_name`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'uq_borrow_orders_2' AS `index_name`, 2 AS `ordinal_position`, 'lend_listing_id' AS `column_name`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'uq_borrow_orders_3' AS `index_name`, 1 AS `ordinal_position`, 'id' AS `column_name`
    UNION ALL
    SELECT 'borrow_orders' AS `table_name`, 'uq_borrow_orders_3' AS `index_name`, 2 AS `ordinal_position`, 'order_id' AS `column_name`
    UNION ALL
    SELECT 'payments' AS `table_name`, 'uq_payments_1' AS `index_name`, 1 AS `ordinal_position`, 'provider' AS `column_name`
    UNION ALL
    SELECT 'payments' AS `table_name`, 'uq_payments_1' AS `index_name`, 2 AS `ordinal_position`, 'provider_transaction_code' AS `column_name`
    UNION ALL
    SELECT 'payments' AS `table_name`, 'uq_payments_2' AS `index_name`, 1 AS `ordinal_position`, 'provider' AS `column_name`
    UNION ALL
    SELECT 'payments' AS `table_name`, 'uq_payments_2' AS `index_name`, 2 AS `ordinal_position`, 'idempotency_key' AS `column_name`
    UNION ALL
    SELECT 'payment_allocations' AS `table_name`, 'uq_payment_allocations_1' AS `index_name`, 1 AS `ordinal_position`, 'payment_id' AS `column_name`
    UNION ALL
    SELECT 'payment_allocations' AS `table_name`, 'uq_payment_allocations_1' AS `index_name`, 2 AS `ordinal_position`, 'order_id' AS `column_name`
    UNION ALL
    SELECT 'payment_allocations' AS `table_name`, 'uq_payment_allocations_1' AS `index_name`, 3 AS `ordinal_position`, 'allocation_type' AS `column_name`
    UNION ALL
    SELECT 'payment_allocations' AS `table_name`, 'uq_payment_allocations_2' AS `index_name`, 1 AS `ordinal_position`, 'idempotency_key' AS `column_name`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'uq_refunds_1' AS `index_name`, 1 AS `ordinal_position`, 'provider' AS `column_name`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'uq_refunds_1' AS `index_name`, 2 AS `ordinal_position`, 'provider_refund_reference' AS `column_name`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'uq_refunds_2' AS `index_name`, 1 AS `ordinal_position`, 'provider' AS `column_name`
    UNION ALL
    SELECT 'refunds' AS `table_name`, 'uq_refunds_2' AS `index_name`, 2 AS `ordinal_position`, 'idempotency_key' AS `column_name`
    UNION ALL
    SELECT 'coupons' AS `table_name`, 'uq_coupons_1' AS `index_name`, 1 AS `ordinal_position`, 'code' AS `column_name`
    UNION ALL
    SELECT 'coupon_usages' AS `table_name`, 'uq_coupon_usages_1' AS `index_name`, 1 AS `ordinal_position`, 'coupon_id' AS `column_name`
    UNION ALL
    SELECT 'coupon_usages' AS `table_name`, 'uq_coupon_usages_1' AS `index_name`, 2 AS `ordinal_position`, 'user_id' AS `column_name`
    UNION ALL
    SELECT 'coupon_usages' AS `table_name`, 'uq_coupon_usages_1' AS `index_name`, 3 AS `ordinal_position`, 'checkout_group_id' AS `column_name`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'uq_favorites_1' AS `index_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'uq_favorites_1' AS `index_name`, 2 AS `ordinal_position`, 'book_id' AS `column_name`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'uq_favorites_2' AS `index_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'uq_favorites_2' AS `index_name`, 2 AS `ordinal_position`, 'sale_listing_id' AS `column_name`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'uq_favorites_3' AS `index_name`, 1 AS `ordinal_position`, 'user_id' AS `column_name`
    UNION ALL
    SELECT 'favorites' AS `table_name`, 'uq_favorites_3' AS `index_name`, 2 AS `ordinal_position`, 'lend_listing_id' AS `column_name`
    UNION ALL
    SELECT 'notification_deliveries' AS `table_name`, 'uq_notification_deliveries_1' AS `index_name`, 1 AS `ordinal_position`, 'notification_id' AS `column_name`
    UNION ALL
    SELECT 'notification_deliveries' AS `table_name`, 'uq_notification_deliveries_1' AS `index_name`, 2 AS `ordinal_position`, 'channel' AS `column_name`
    UNION ALL
    SELECT 'reviews' AS `table_name`, 'uq_reviews_1' AS `index_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`
    UNION ALL
    SELECT 'reviews' AS `table_name`, 'uq_reviews_1' AS `index_name`, 2 AS `ordinal_position`, 'reviewer_id' AS `column_name`
    UNION ALL
    SELECT 'platform_fees' AS `table_name`, 'uq_platform_fees_1' AS `index_name`, 1 AS `ordinal_position`, 'idempotency_key' AS `column_name`
    UNION ALL
    SELECT 'seller_payout_accounts' AS `table_name`, 'uq_seller_payout_accounts_1' AS `index_name`, 1 AS `ordinal_position`, 'default_active_account_user_key' AS `column_name`
    UNION ALL
    SELECT 'seller_payouts' AS `table_name`, 'uq_seller_payouts_1' AS `index_name`, 1 AS `ordinal_position`, 'order_id' AS `column_name`
    UNION ALL
    SELECT 'seller_payouts' AS `table_name`, 'uq_seller_payouts_2' AS `index_name`, 1 AS `ordinal_position`, 'idempotency_key' AS `column_name`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'uq_financial_transactions_1' AS `index_name`, 1 AS `ordinal_position`, 'transaction_code' AS `column_name`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'uq_financial_transactions_2' AS `index_name`, 1 AS `ordinal_position`, 'idempotency_key' AS `column_name`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'uq_financial_transactions_3' AS `index_name`, 1 AS `ordinal_position`, 'provider' AS `column_name`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'uq_financial_transactions_3' AS `index_name`, 2 AS `ordinal_position`, 'transaction_type' AS `column_name`
    UNION ALL
    SELECT 'financial_transactions' AS `table_name`, 'uq_financial_transactions_3' AS `index_name`, 3 AS `ordinal_position`, 'provider_reference' AS `column_name`
    UNION ALL
    SELECT 'financial_transaction_events' AS `table_name`, 'uq_financial_transaction_events_1' AS `index_name`, 1 AS `ordinal_position`, 'provider' AS `column_name`
    UNION ALL
    SELECT 'financial_transaction_events' AS `table_name`, 'uq_financial_transaction_events_1' AS `index_name`, 2 AS `ordinal_position`, 'provider_event_id' AS `column_name`
    UNION ALL
    SELECT 'seller_payout_adjustments' AS `table_name`, 'uq_seller_payout_adjustments_1' AS `index_name`, 1 AS `ordinal_position`, 'idempotency_key' AS `column_name`
    UNION ALL
    SELECT 'seller_payout_adjustment_allocations' AS `table_name`, 'uq_seller_payout_adjustment_allocations_1' AS `index_name`, 1 AS `ordinal_position`, 'adjustment_id' AS `column_name`
    UNION ALL
    SELECT 'seller_payout_adjustment_allocations' AS `table_name`, 'uq_seller_payout_adjustment_allocations_1' AS `index_name`, 2 AS `ordinal_position`, 'payout_id' AS `column_name`
)
SELECT e.table_name, e.index_name, e.ordinal_position, e.column_name
FROM expected_unique_columns e
LEFT JOIN information_schema.STATISTICS s
  ON s.TABLE_SCHEMA = DATABASE() AND s.TABLE_NAME = e.table_name
 AND s.INDEX_NAME = e.index_name AND s.NON_UNIQUE = 0
 AND s.SEQ_IN_INDEX = e.ordinal_position
WHERE s.COLUMN_NAME IS NULL OR s.COLUMN_NAME <> e.column_name;

WITH expected_generated AS (
    SELECT 'user_addresses' AS `table_name`, 'default_address_user_key' AS `column_name`, 'BIGINT UNSIGNED' AS `column_type`
    UNION ALL
    SELECT 'book_images' AS `table_name`, 'primary_image_book_key' AS `column_name`, 'BIGINT UNSIGNED' AS `column_type`
    UNION ALL
    SELECT 'book_work_subjects' AS `table_name`, 'primary_subject_work_key' AS `column_name`, 'BIGINT UNSIGNED' AS `column_type`
    UNION ALL
    SELECT 'carts' AS `table_name`, 'active_cart_user_key' AS `column_name`, 'BIGINT UNSIGNED' AS `column_type`
    UNION ALL
    SELECT 'sale_listings' AS `table_name`, 'active_sale_book_key' AS `column_name`, 'BIGINT UNSIGNED' AS `column_type`
    UNION ALL
    SELECT 'lend_listings' AS `table_name`, 'active_lend_book_key' AS `column_name`, 'BIGINT UNSIGNED' AS `column_type`
    UNION ALL
    SELECT 'seller_payout_accounts' AS `table_name`, 'default_active_account_user_key' AS `column_name`, 'BIGINT UNSIGNED' AS `column_type`
    UNION ALL
    SELECT 'orders' AS `table_name`, 'sale_seller_key' AS `column_name`, 'BIGINT UNSIGNED' AS `column_type`
)
SELECT e.table_name, e.column_name, e.column_type
FROM expected_generated e
LEFT JOIN information_schema.COLUMNS c
  ON c.TABLE_SCHEMA = DATABASE() AND c.TABLE_NAME = e.table_name
 AND c.COLUMN_NAME = e.column_name
WHERE c.COLUMN_NAME IS NULL OR LOWER(c.COLUMN_TYPE) <> LOWER(e.column_type)
   OR c.EXTRA NOT LIKE '%STORED GENERATED%';

SELECT 'stored_generated_column_count' AS check_name, 8 AS expected_count,
       COUNT(*) AS actual_count,
       IF(COUNT(*) = 8, 'PASS', 'FAIL') AS result
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() AND EXTRA LIKE '%STORED GENERATED%';

SELECT 'check_constraint_count' AS check_name, 104 AS expected_count,
       COUNT(*) AS actual_count,
       IF(COUNT(*) = 104, 'PASS', 'FAIL') AS result
FROM information_schema.TABLE_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_TYPE = 'CHECK';

SELECT 'innodb_and_utf8mb4_table_count' AS check_name, 57 AS expected_count,
       COUNT(*) AS actual_count,
       IF(COUNT(*) = 57, 'PASS', 'FAIL') AS result
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
  AND ENGINE = 'InnoDB' AND TABLE_COLLATION = 'utf8mb4_0900_ai_ci';

SELECT 'non_utf8mb4_character_columns' AS check_name,
       COUNT(*) AS actual_count, IF(COUNT(*) = 0, 'PASS', 'FAIL') AS result
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() AND CHARACTER_SET_NAME IS NOT NULL
  AND CHARACTER_SET_NAME <> 'utf8mb4';

SELECT 'money_decimal_19_4_columns' AS check_name, 45 AS expected_count,
       COUNT(*) AS actual_count,
       IF(COUNT(*) = 45, 'PASS', 'FAIL') AS result
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() AND DATA_TYPE = 'decimal'
  AND NUMERIC_PRECISION = 19 AND NUMERIC_SCALE = 4;

SELECT 'rate_decimal_9_6_columns' AS check_name, 2 AS expected_count,
       COUNT(*) AS actual_count,
       IF(COUNT(*) = 2, 'PASS', 'FAIL') AS result
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE() AND DATA_TYPE = 'decimal'
  AND NUMERIC_PRECISION = 9 AND NUMERIC_SCALE = 6;
