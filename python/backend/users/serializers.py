from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from .models import University, User, UserAddress


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, allow_blank=False, trim_whitespace=True)
    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(min_length=8, write_only=True, trim_whitespace=False)
    university_id = serializers.PrimaryKeyRelatedField(
        source='university',
        queryset=University.objects.all(),
        write_only=True,
    )
    phone = serializers.CharField(max_length=30, allow_blank=True, required=False)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError('Email đã được đăng ký.')
        return email

    def create(self, validated_data):
        password = validated_data.pop('password')
        now = timezone.now()
        try:
            with transaction.atomic():
                return User.objects.create(
                    password_hash=make_password(password),
                    full_name=validated_data.pop('name'),
                    role='STUDENT',
                    status='PENDING_VERIFICATION',
                    created_at=now,
                    updated_at=now,
                    **validated_data,
                )
        except IntegrityError as exc:
            if User.objects.filter(email=validated_data.get('email')).exists():
                raise serializers.ValidationError({'email': 'Email đã được đăng ký.'}) from exc
            raise


class RegisteredUserSerializer(serializers.ModelSerializer):
    university_id = serializers.IntegerField(source='university.id', read_only=True)
    name = serializers.CharField(source='full_name', read_only=True)
    avatar = serializers.CharField(source='avatar_url', read_only=True, allow_null=True)
    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'name', 'email', 'university_id', 'role', 'status',
            'is_verified', 'avatar', 'phone',
        )

    def get_role(self, user):
        return user.role.lower()

    def get_status(self, user):
        return user.status.lower()


class PublicUniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = ('id', 'name', 'code')


class PublicSellerSerializer(serializers.ModelSerializer):
    university = PublicUniversitySerializer(read_only=True)
    name = serializers.CharField(source='full_name', read_only=True)
    avatar = serializers.CharField(source='avatar_url', read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = ('id', 'name', 'avatar', 'university', 'is_verified', 'created_at')


class ProfileSerializer(serializers.ModelSerializer):
    university = PublicUniversitySerializer(read_only=True)
    name = serializers.CharField(source='full_name', required=False)
    avatar = serializers.CharField(source='avatar_url', allow_null=True, required=False)
    role = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'name', 'email', 'avatar', 'phone', 'university',
            'is_verified', 'role', 'status', 'created_at',
        )
        read_only_fields = (
            'id', 'email', 'phone', 'university', 'is_verified', 'role', 'status',
            'created_at',
        )

    def get_role(self, user):
        return user.role.lower()

    def get_status(self, user):
        return user.status.lower()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, allow_blank=False, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, min_length=8, allow_blank=False, trim_whitespace=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255, required=False)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=False)
    password = serializers.CharField(write_only=True, allow_blank=False, trim_whitespace=False)
    otp_channel = serializers.ChoiceField(
        choices=('EMAIL', 'PHONE'),
        required=False,
    )

    def validate_email(self, value):
        return value.strip().lower()

    def validate_phone(self, value):
        return value.strip()

    def validate(self, attrs):
        if bool(attrs.get('email')) == bool(attrs.get('phone')):
            raise serializers.ValidationError(
                'Cung cấp chính xác một trong email hoặc phone.',
            )
        return attrs


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAddress
        fields = (
            'id', 'recipient_name', 'phone', 'address_line', 'ward',
            'district', 'city', 'postal_code', 'is_default',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
