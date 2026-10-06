-- Apply once to an existing PassBook v1.2 Lite database running MySQL 8.0+.
-- These ngram FULLTEXT indexes accelerate catalog searches while the API keeps
-- an exact LIKE check to preserve the existing substring-search behavior.
-- Run before deploying code that uses books.search.indexed_icontains.

ALTER TABLE `sale_listings`
  ADD FULLTEXT INDEX `ft_sale_listings_search` (`title`, `description`)
    WITH PARSER ngram;

ALTER TABLE `lend_listings`
  ADD FULLTEXT INDEX `ft_lend_listings_search` (`title`, `description`)
    WITH PARSER ngram;

ALTER TABLE `book_works`
  ADD FULLTEXT INDEX `ft_book_works_search`
    (`title`, `description`, `author_name`)
    WITH PARSER ngram;

ALTER TABLE `book_editions`
  ADD FULLTEXT INDEX `ft_book_editions_search`
    (`edition_name`, `publisher_name`, `description`)
    WITH PARSER ngram;

ALTER TABLE `subjects`
  ADD FULLTEXT INDEX `ft_subjects_search` (`name`, `code`)
    WITH PARSER ngram;

ALTER TABLE `book_identifiers`
  ADD FULLTEXT INDEX `ft_book_identifiers_search` (`identifier_value`)
    WITH PARSER ngram;

ALTER TABLE `categories`
  ADD FULLTEXT INDEX `ft_categories_search` (`name`)
    WITH PARSER ngram;

ALTER TABLE `universities`
  ADD FULLTEXT INDEX `ft_universities_search` (`name`)
    WITH PARSER ngram;

ALTER TABLE `faculties`
  ADD FULLTEXT INDEX `ft_faculties_search` (`name`)
    WITH PARSER ngram;

ALTER TABLE `majors`
  ADD FULLTEXT INDEX `ft_majors_search` (`name`)
    WITH PARSER ngram;
