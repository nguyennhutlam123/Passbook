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


REPORT_STATUSES = ('OPEN', 'IN_REVIEW', 'RESOLVED', 'REJECTED')


class AdminReportSerializer(serializers.ModelSerializer):
    reporter_name = serializers.CharField(source='reporter.full_name', read_only=True)
    reported_user_name = serializers.CharField(
        source='reported_user.full_name',
        read_only=True,
        allow_null=True,
    )
    book_title = serializers.CharField(
        source='book.book_edition.book_work.title',
        read_only=True,
        allow_null=True,
    )
    sale_listing_title = serializers.CharField(
        source='sale_listing.title',
        read_only=True,
        allow_null=True,
    )
    lend_listing_title = serializers.CharField(
        source='lend_listing.title',
        read_only=True,
        allow_null=True,
    )
    message_content = serializers.CharField(
        source='message.content',
        read_only=True,
        allow_null=True,
    )
    message_sender_id = serializers.IntegerField(
        source='message.sender_id',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Report
        fields = (
            'id',
            'reporter_id',
            'reporter_name',
            'reported_user_id',
            'reported_user_name',
            'book_id',
            'book_title',
            'sale_listing_id',
            'sale_listing_title',
            'lend_listing_id',
            'lend_listing_title',
            'message_id',
            'message_content',
            'message_sender_id',
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
        choices=REPORT_STATUSES,
    )
    resolution_note = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate(self, attrs):
        if attrs['status'] in ('RESOLVED', 'REJECTED') and not (
            attrs.get('resolution_note') or ''
        ).strip():
            raise serializers.ValidationError({
                'resolution_note': 'Nhập ghi chú khi đóng báo cáo.',
            })
        return attrs


class AdminReportListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        reports = Report.objects.select_related(
            'reporter',
            'reported_user',
            'book',
            'book__book_edition__book_work',
            'sale_listing',
            'lend_listing',
            'message',
            'message__sender',
            'handled_by',
        ).order_by('-created_at', '-id')
        report_status = request.query_params.get('status')
        if report_status:
            if report_status not in REPORT_STATUSES:
                raise serializers.ValidationError({
                    'status': 'Trạng thái báo cáo không hợp lệ.',
                })
            reports = reports.filter(status=report_status)
        reason = request.query_params.get('reason')
        if reason:
            if reason not in (
                'INAPPROPRIATE_CONTENT',
                'INCORRECT_BOOK_INFO',
                'SPAM',
                'SCAM',
                'POLICY_VIOLATION',
                'OTHER',
            ):
                raise serializers.ValidationError({
                    'reason': 'Lý do báo cáo không hợp lệ.',
                })
            reports = reports.filter(reason=reason)

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
        previous_status = report.status
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
        if report.status != previous_status:
            from notifications.services import create_notification

            status_labels = {
                'OPEN': 'được đưa lại vào hàng chờ xử lý',
                'IN_REVIEW': 'đang được Admin xem xét',
                'RESOLVED': 'đã được xử lý',
                'REJECTED': 'đã được xem xét và từ chối',
            }
            create_notification(
                report.reporter_id,
                notification_type='REPORT',
                title=f'Cập nhật báo cáo #{report.id}',
                content=f'Báo cáo của bạn {status_labels[report.status]}.',
                entity_type='REPORT',
                entity_id=report.id,
            )
        return Response(AdminReportSerializer(report).data)
