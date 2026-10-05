-- Apply once to an existing Passbook v1.2 Lite database.
-- This adds moderation states without adding or removing tables or columns.
ALTER TABLE `sale_listings`
  DROP CONSTRAINT `ck_sale_listings_3`,
  ADD CONSTRAINT `ck_sale_listings_3`
    CHECK (`status` IN (
      'DRAFT',
      'PENDING',
      'ACTIVE',
      'REJECTED',
      'RESERVED',
      'SOLD',
      'CLOSED',
      'EXPIRED'
    ));
