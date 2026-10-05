-- Apply once to an existing Passbook v1.2 Lite database after backing up data.
-- Stores an optional planned transaction date separately from the request expiry.
ALTER TABLE `book_requests`
  ADD COLUMN `planned_at` DATETIME(3) NULL DEFAULT NULL
    AFTER `status`;
