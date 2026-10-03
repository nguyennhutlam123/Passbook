from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from books.pagination import BookPagination
from users.permissions import IsAdmin
from .models import Report


class AdminReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = (
            'id',
            'reporter_id',
            'reported_user_id',
            'book_id',
            'sale_listing_id',
            'lend_listing_id',
            'message_id',
            'reason',
            'description',
            'status',
            'handled_by_id',
            'resolution_note',
            'created_at',
            'resolved_at',
        )
        read_only_fields = fields


class AdminReportUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=('OPEN', 'IN_REVIEW', 'RESOLVED', 'REJECTED'),
    )
    resolution_note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class AdminReportListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        reports = Report.objects.select_related(
            'reporter',
            'reported_user',
            'book',
            'sale_listing',
            'lend_listing',
            'message',
            'handled_by',
        ).order_by('-created_at', '-id')
        report_status = request.query_params.get('status')
        if report_status:
            valid_statuses = {
                value for value, _label in AdminReportUpdateSerializer().fields[
                    'status'
                ].choices
            }
            if report_status not in valid_statuses:
                raise serializers.ValidationError({
                    'status': 'Trạng thái báo cáo không hợp lệ.',
                })
            reports = reports.filter(status=report_status)

        paginator = BookPagination()
        page = paginator.paginate_queryset(reports, request, view=self)
        return paginator.get_paginated_response(
            AdminReportSerializer(page, many=True).data,
        )


class AdminReportDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @transaction.atomic
    def patch(self, request, report_id):
        report = get_object_or_404(
            Report.objects.select_for_update(),
            pk=report_id,
        )
        serializer = AdminReportUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report.status = serializer.validated_data['status']
        report.handled_by = request.user
        report.resolution_note = serializer.validated_data.get(
            'resolution_note',
            report.resolution_note,
        )
        report.resolved_at = (
            timezone.now()
            if report.status in ('RESOLVED', 'REJECTED')
            else None
        )
        report.save(update_fields=[
            'status',
            'handled_by',
            'resolution_note',
            'resolved_at',
        ])
        return Response(AdminReportSerializer(report).data)
