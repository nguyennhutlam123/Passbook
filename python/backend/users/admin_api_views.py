from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from books.pagination import BookPagination
from .models import User, UserViolation
from .permissions import IsAdmin


class AdminUserListSerializer(serializers.ModelSerializer):
    university_name = serializers.CharField(
        source='university.name',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'full_name',
            'phone',
            'role',
            'status',
            'university_name',
            'created_at',
        )
        read_only_fields = fields


class AdminUserListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        users = User.objects.select_related('university').order_by(
            '-created_at', '-id',
        )
        search = request.query_params.get('search', '').strip()
        status_filter = request.query_params.get('status', '').strip()
        role_filter = request.query_params.get('role', '').strip()

        if search:
            users = users.filter(
                Q(email__icontains=search)
                | Q(full_name__icontains=search)
                | Q(phone__icontains=search)
            )
        if status_filter:
            if status_filter not in dict(User.STATUS_CHOICES):
                raise serializers.ValidationError({
                    'status': 'Trạng thái tài khoản không hợp lệ.',
                })
            users = users.filter(status=status_filter)
        if role_filter:
            if role_filter not in dict(User.ROLE_CHOICES):
                raise serializers.ValidationError({
                    'role': 'Vai trò tài khoản không hợp lệ.',
                })
            users = users.filter(role=role_filter)

        paginator = BookPagination()
        page = paginator.paginate_queryset(users, request, view=self)
        return paginator.get_paginated_response(
            AdminUserListSerializer(page, many=True).data,
        )


class UserViolationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserViolation
        fields = (
            'id',
            'user_id',
            'violation_type',
            'reason',
            'description',
            'severity',
            'status',
            'expires_at',
            'created_by_id',
            'created_at',
            'resolved_at',
        )
        read_only_fields = fields


class UserViolationInputSerializer(serializers.Serializer):
    violation_type = serializers.CharField(max_length=50, allow_blank=False)
    reason = serializers.CharField(max_length=255, allow_blank=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    severity = serializers.CharField(max_length=20, allow_blank=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class UserViolationStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=('OPEN', 'RESOLVED'))


class UserAccountStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=User.STATUS_CHOICES)


class MyViolationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        violations = UserViolation.objects.filter(
            user_id=request.user.id,
        ).order_by('-created_at', '-id')
        paginator = BookPagination()
        page = paginator.paginate_queryset(violations, request, view=self)
        return paginator.get_paginated_response(
            UserViolationSerializer(page, many=True).data,
        )


class AdminUserViolationListCreateView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, user_id):
        violations = UserViolation.objects.filter(
            user_id=user_id,
        ).order_by('-created_at', '-id')
        paginator = BookPagination()
        page = paginator.paginate_queryset(violations, request, view=self)
        return paginator.get_paginated_response(
            UserViolationSerializer(page, many=True).data,
        )

    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        serializer = UserViolationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        violation = UserViolation.objects.create(
            user=user,
            created_by=request.user,
            status='OPEN',
            created_at=timezone.now(),
            **serializer.validated_data,
        )
        return Response(
            UserViolationSerializer(violation).data,
            status=status.HTTP_201_CREATED,
        )


class AdminUserViolationDetailView(APIView):
    permission_classes = [IsAdmin]

    @transaction.atomic
    def patch(self, request, violation_id):
        violation = get_object_or_404(
            UserViolation.objects.select_for_update(),
            pk=violation_id,
        )
        serializer = UserViolationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        violation.status = serializer.validated_data['status']
        violation.resolved_at = (
            timezone.now() if violation.status == 'RESOLVED' else None
        )
        violation.save(update_fields=['status', 'resolved_at'])
        return Response(UserViolationSerializer(violation).data)


class AdminUserStatusView(APIView):
    permission_classes = [IsAdmin]

    @transaction.atomic
    def patch(self, request, user_id):
        user = get_object_or_404(
            User.objects.select_for_update(),
            pk=user_id,
        )
        if user.id == request.user.id:
            raise serializers.ValidationError(
                'Quản trị viên không thể tự thay đổi trạng thái tài khoản.',
            )
        serializer = UserAccountStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.status = serializer.validated_data['status']
        user.updated_at = timezone.now()
        user.save(update_fields=['status', 'updated_at'])
        return Response({
            'id': user.id,
            'status': user.status,
        })
