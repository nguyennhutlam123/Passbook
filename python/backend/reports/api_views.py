from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from books.pagination import BookPagination
from .models import Report
from .serializers import ReportCreateSerializer, ReportSerializer


class ReportCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        target_name = next(
            name for name in (
                'reported_user', 'book', 'sale_listing', 'lend_listing', 'message',
            ) if data.get(name) is not None
        )
        if target_name == 'book' and data['book'].status == 'UNAVAILABLE':
            raise serializers.ValidationError({
                'book_id': 'Không thể báo cáo sách không còn hiển thị.',
            })
        report = Report.objects.filter(
            reporter=request.user,
            reason=data['reason'],
            description=data.get('description') or None,
            **{target_name: data[target_name]},
        ).first()
        if report is not None:
            return Response(ReportSerializer(report).data, status=status.HTTP_200_OK)

        with transaction.atomic():
            report = Report.objects.create(
                reporter=request.user,
                reason=data['reason'],
                description=data.get('description') or None,
                status='OPEN',
                created_at=timezone.now(),
                **{
                    name: data[name]
                    for name in ('reported_user', 'book', 'sale_listing', 'lend_listing', 'message')
                    if name in data
                },
            )
        return Response(
            ReportSerializer(report).data,
            status=status.HTTP_201_CREATED,
        )


class MyReportListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Report.objects.filter(
            reporter_id=request.user.id,
        ).select_related('book').order_by('-created_at', '-id')
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            ReportSerializer(page, many=True).data,
        )
