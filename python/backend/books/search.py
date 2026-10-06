from django.db import connection
from django.db.models import F, FloatField, Func, Q


def _ngram_boolean_phrase(value):
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def supports_ngram_search(value):
    return any(
        left.isalnum() and right.isalnum()
        for left, right in zip(value, value[1:])
    )


class NgramMatch(Func):
    output_field = FloatField()

    def __init__(self, fields, value):
        self.search_phrase = _ngram_boolean_phrase(value)
        super().__init__(
            *(F(field) for field in fields),
            output_field=self.output_field,
        )

    def as_sql(self, compiler, connection, **extra_context):
        match_sql, params = super().as_sql(
            compiler,
            connection,
            function='MATCH',
            template='MATCH(%(expressions)s)',
            **extra_context,
        )
        return (
            f'{match_sql} AGAINST (%s IN BOOLEAN MODE)',
            (*params, self.search_phrase),
        )


def indexed_icontains(queryset, fields, value, exact_fields=None):
    exact_fields = exact_fields or fields
    exact_match = Q()
    for field in exact_fields:
        exact_match |= Q(**{f'{field}__icontains': value})

    if (
        connection.vendor != 'mysql'
        or connection.mysql_is_mariadb
        or not supports_ngram_search(value)
    ):
        return queryset.filter(exact_match)

    return queryset.annotate(
        _ngram_match=NgramMatch(fields, value),
    ).filter(
        _ngram_match__gt=0,
    ).filter(
        exact_match,
    )
