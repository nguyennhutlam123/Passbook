from django.contrib import admin
from django import forms
from django.utils import timezone

from .models import Report
from users.models import User as PassbookUser


class ReportAdminForm(forms.ModelForm):
    status = forms.ChoiceField(choices=(
        ('OPEN', 'Pending'),
        ('IN_REVIEW', 'In review'),
        ('RESOLVED', 'Resolved'),
        ('REJECTED', 'Rejected'),
    ))

    class Meta:
        model = Report
        fields = '__all__'


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    form = ReportAdminForm
    list_display = (
        'id',
        'reason',
        'status',
        'reporter',
        'reported_user',
        'book',
        'sale_listing',
        'lend_listing',
        'message',
        'created_at',
        'handled_by',
        'resolved_at',
    )
    list_filter = ('status', 'reason', 'created_at')
    list_editable = ('status',)
    search_fields = ('reporter__email', 'reported_user__email', 'reason', 'description')
    readonly_fields = ('reporter', 'created_at')

    def save_model(self, request, obj, form, change):
        obj.handled_by = PassbookUser.objects.filter(
            pk=request.user.pk,
            role='ADMIN',
        ).first()
        obj.resolved_at = (
            timezone.now()
            if obj.status in ('RESOLVED', 'REJECTED')
            else None
        )
        super().save_model(request, obj, form, change)
