from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from .models import University, User


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150, allow_blank=False, trim_whitespace=True)
    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(min_length=8, write_only=True, trim_whitespace=False)
    university_id = serializers.PrimaryKeyRelatedField(
        source='university',
        queryset=University.objects.all(),
        write_only=True,
    )
    phone = serializers.CharField(max_length=20, allow_blank=True, required=False)

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
                    role='student',
                    status='active',
                    is_verified=False,
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

    class Meta:
        model = User
        fields = ('id', 'name', 'email', 'university_id', 'role', 'status', 'is_verified', 'avatar', 'phone')


class PublicUniversitySerializer(serializers.ModelSerializer):
    class Meta:
        model = University
        fields = ('id', 'name', 'code')


class PublicSellerSerializer(serializers.ModelSerializer):
    university = PublicUniversitySerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'name', 'avatar', 'university', 'is_verified', 'created_at')


class ProfileSerializer(serializers.ModelSerializer):
    university = PublicUniversitySerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'name', 'email', 'avatar', 'phone', 'university', 'is_verified', 'role', 'status', 'created_at')
        read_only_fields = ('id', 'email', 'university', 'is_verified', 'role', 'status', 'created_at')


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, allow_blank=False, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, min_length=8, allow_blank=False, trim_whitespace=False)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(write_only=True, allow_blank=False, trim_whitespace=False)

    def validate_email(self, value):
        return value.strip().lower()
