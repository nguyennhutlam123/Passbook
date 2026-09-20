from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination


class BookPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_page_size(self, request):
        raw_page_size = request.query_params.get(self.page_size_query_param)
        if raw_page_size is not None:
            try:
                page_size = int(raw_page_size)
            except ValueError as exc:
                raise serializers.ValidationError({'page_size': 'page_size phải là số nguyên.'}) from exc
            if page_size < 1 or page_size > self.max_page_size:
                raise serializers.ValidationError({
                    'page_size': f'page_size phải nằm trong khoảng 1 đến {self.max_page_size}.',
                })
        return super().get_page_size(request)
