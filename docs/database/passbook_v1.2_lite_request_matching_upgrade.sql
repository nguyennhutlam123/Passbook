-- Apply once to an existing Passbook v1.2 Lite database after backing up data.
-- Enables persistent SELL_INTENT <-> BUY request matches without adding a table.
ALTER TABLE `request_matches`
  ADD COLUMN `matched_request_id` BIGINT UNSIGNED NULL DEFAULT NULL
    AFTER `request_id`,
  ADD KEY `ix_request_matches_4` (`matched_request_id`, `status`),
  ADD CONSTRAINT `fk_request_matches_4`
    FOREIGN KEY (`matched_request_id`) REFERENCES `book_requests` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE;
