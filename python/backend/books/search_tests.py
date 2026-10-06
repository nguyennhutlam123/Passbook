from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .models import BookWork
from .search import indexed_icontains


class IndexedIcontainsTests(SimpleTestCase):
    def test_search_uses_ngram_match_and_keeps_exact_substring_check(self):
        with patch(
            'books.search.connection',
            SimpleNamespace(vendor='mysql', mysql_is_mariadb=False),
        ):
            queryset = indexed_icontains(
                BookWork.objects.all(),
                ('title', 'author_name'),
                'triết',
            )

        sql, params = queryset.query.sql_with_params()

        self.assertIn('MATCH(', sql)
        self.assertIn('AGAINST (%s IN BOOLEAN MODE)', sql)
        self.assertIn('> %s', sql)
        self.assertIn('LIKE', sql)
        self.assertIn('"triết"', params)
        self.assertIn(0.0, params)
        self.assertIn('%triết%', params)

    def test_short_search_uses_icontains_without_ngram(self):
        with patch(
            'books.search.connection',
            SimpleNamespace(vendor='mysql', mysql_is_mariadb=False),
        ):
            queryset = indexed_icontains(
                BookWork.objects.all(),
                ('title', 'author_name'),
                'a',
            )

        sql, params = queryset.query.sql_with_params()

        self.assertNotIn('MATCH(', sql)
        self.assertIn('LIKE', sql)
        self.assertIn('%a%', params)

    def test_search_is_escaped_as_a_boolean_phrase(self):
        with patch(
            'books.search.connection',
            SimpleNamespace(vendor='mysql', mysql_is_mariadb=False),
        ):
            queryset = indexed_icontains(
                BookWork.objects.all(),
                ('title',),
                'MATH-101 "A"',
            )

        _sql, params = queryset.query.sql_with_params()

        self.assertIn('"MATH-101 \\"A\\""', params)
