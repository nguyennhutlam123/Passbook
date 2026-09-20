from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from books.models import Book
from books.pagination import BookPagination
from .models import Report
from .serializers import ReportCreateSerializer, ReportSerializer


class ReportCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        book_id = serializer.validated_data.pop('book_id', None)
        book = None
        if book_id is not None:
            book = get_object_or_404(Book, pk=book_id)
            if book.status in ('deleted', 'hidden'):
                raise serializers.ValidationError({'book_id': 'Không thể báo cáo sách không còn hiển thị.'})

        report = Report.objects.filter(
            reporter=request.user,
            book=book,
            reason=serializer.validated_data['reason'],
            description=serializer.validated_data['description'],
        ).first()
        if report is not None:
            return Response(ReportSerializer(report).data, status=status.HTTP_200_OK)

        with transaction.atomic():
            report = Report.objects.create(
                reporter=request.user,
                book=book,
                reason=serializer.validated_data['reason'],
                description=serializer.validated_data['description'],
                status='pending',
                created_at=timezone.now(),
            )
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


class MyReportListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Report.objects.filter(reporter_id=request.user.id).select_related('book').order_by('-created_at', '-id')
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(ReportSerializer(page, many=True).data)
