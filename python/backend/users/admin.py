from django.contrib import admin

from .models import (
    Faculty,
    Language,
    Major,
    OtpVerification,
    Subject,
    University,
    User,
    UserAddress,
    UserViolation,
)


@admin.register(OtpVerification)
class OtpVerificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'target', 'channel', 'purpose', 'status', 'expires_at')
    list_filter = ('channel', 'purpose', 'status')
    search_fields = ('target',)
    readonly_fields = (
        'id', 'user', 'channel', 'purpose', 'target', 'expires_at',
        'verified_at', 'attempt_count', 'resend_count', 'status',
        'created_at', 'updated_at',
    )
    fields = readonly_fields

    def get_queryset(self, request):
        return super().get_queryset(request).defer('otp_hash')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(User)
class PassbookUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'full_name', 'role', 'status', 'created_at')
    list_filter = ('role', 'status', 'university')
    search_fields = ('email', 'full_name', 'phone')
    readonly_fields = ('id', 'created_at')
    exclude = ('password_hash',)

    def has_add_permission(self, request):
        return False


admin.site.register((
    University,
    Faculty,
    Major,
    Language,
    Subject,
    UserAddress,
    UserViolation,
))
