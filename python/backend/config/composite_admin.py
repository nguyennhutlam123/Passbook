from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import path, reverse
from django import forms
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.middleware.csrf import get_token


class CompositeKeyModelForm(forms.ModelForm):
    def validate_unique(self):
        model = self.instance.__class__
        for key_fields in model._meta.unique_together:
            values = {
                name: self.cleaned_data.get(name)
                for name in key_fields
            }
            if any(value is None for value in values.values()):
                continue
            matches = model._default_manager.filter(**values)
            if not self.instance._state.adding:
                original_key = {
                    name: self.initial.get(name)
                    for name in key_fields
                }
                matches = matches.exclude(**original_key)
            if matches.exists():
                self.add_error(
                    key_fields[0],
                    _('A row with this composite key already exists.'),
                )

        if (
            self.cleaned_data.get('is_primary')
            and 'book_work' in self.cleaned_data
        ):
            primary_rows = model._default_manager.filter(
                book_work=self.cleaned_data['book_work'],
                is_primary=True,
            )
            if not self.instance._state.adding:
                primary_rows = primary_rows.exclude(**{
                    name: self.initial.get(name)
                    for name in model._meta.unique_together[0]
                })
            if primary_rows.exists():
                self.add_error(
                    'is_primary',
                    _('This work already has a primary subject.'),
                )


class CompositeKeyAdmin(admin.ModelAdmin):
    composite_key_fields = ()
    form = CompositeKeyModelForm
    actions = None

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/composite-delete/',
                self.admin_site.admin_view(self.composite_delete_view),
                name=(
                    f'{self.model._meta.app_label}_'
                    f'{self.model._meta.model_name}_composite_delete'
                ),
            ),
        ]
        return custom_urls + super().get_urls()

    def get_object(self, request, object_id, from_field=None):
        parts = self._parse_key(object_id)
        if parts is None:
            return None
        lookup = dict(zip(self.composite_key_fields, parts))
        try:
            return self.get_queryset(request).get(**lookup)
        except self.model.DoesNotExist:
            return None

    def save_model(self, request, obj, form, change):
        fields = [
            field for field in obj._meta.local_concrete_fields
            if not getattr(field, 'generated', False)
        ]
        columns = [field.column for field in fields]
        values = [getattr(obj, field.attname) for field in fields]
        table_name = connection.ops.quote_name(obj._meta.db_table)
        quoted_columns = [connection.ops.quote_name(column) for column in columns]
        if change:
            object_id = request.resolver_match.kwargs['object_id']
            old_key = self._parse_key(object_id)
            if old_key is None:
                raise Http404
            update_sql = ', '.join(f'{column}=%s' for column in quoted_columns)
            where_sql = ' AND '.join(
                f'{connection.ops.quote_name(self.model._meta.get_field(name).column)}=%s'
                for name in self.composite_key_fields
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    f'UPDATE {table_name} SET {update_sql} WHERE {where_sql}',
                    [*values, *old_key],
                )
        else:
            placeholders = ', '.join(['%s'] * len(values))
            with connection.cursor() as cursor:
                cursor.execute(
                    f'INSERT INTO {table_name} '
                    f'({", ".join(quoted_columns)}) VALUES ({placeholders})',
                    values,
                )
        obj._state.adding = False

    def delete_model(self, request, obj):
        where_sql = ' AND '.join(
            f'{connection.ops.quote_name(self.model._meta.get_field(name).column)}=%s'
            for name in self.composite_key_fields
        )
        values = [getattr(obj, self.model._meta.get_field(name).attname)
                  for name in self.composite_key_fields]
        with connection.cursor() as cursor:
            cursor.execute(
                f'DELETE FROM {connection.ops.quote_name(obj._meta.db_table)} '
                f'WHERE {where_sql}',
                values,
            )

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)

    def composite_key_link(self, obj):
        object_id = ':'.join(
            str(getattr(obj, self.model._meta.get_field(name).attname))
            for name in self.composite_key_fields
        )
        url = reverse(
            f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change',
            args=(object_id,),
        )
        return format_html('<a href="{}">{}</a>', url, object_id)

    composite_key_link.short_description = _('Composite key')
    composite_key_link.admin_order_field = None

    def composite_delete_link(self, obj):
        object_id = ':'.join(
            str(getattr(obj, self.model._meta.get_field(name).attname))
            for name in self.composite_key_fields
        )
        url = reverse(
            f'admin:{self.model._meta.app_label}_'
            f'{self.model._meta.model_name}_composite_delete',
            args=(object_id,),
        )
        return format_html('<a href="{}">{}</a>', url, _('Delete'))

    composite_delete_link.short_description = _('Delete')

    def change_view(
        self,
        request,
        object_id,
        form_url='',
        extra_context=None,
    ):
        context = {'show_delete': False}
        context.update(extra_context or {})
        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=context,
        )

    def composite_delete_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if obj is None:
            raise Http404
        if not self.has_delete_permission(request, obj):
            raise PermissionDenied
        if request.method == 'POST':
            if request.POST.get('confirm') != 'yes':
                raise Http404
            self.delete_model(request, obj)
            self.log_deletion(request, obj, str(obj))
            return redirect(
                f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist',
            )
        return HttpResponse(format_html(
            '<!doctype html><title>{}</title><h1>{}</h1>'
            '<p>{}</p><form method="post">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
            '<button type="submit" name="confirm" value="yes">{}</button>'
            '</form>',
            _('Confirm deletion'),
            _('Delete this relationship?'),
            obj,
            get_token(request),
            _('Confirm delete'),
        ))

    def _parse_key(self, object_id):
        try:
            parts = tuple(int(part) for part in object_id.split(':'))
        except (AttributeError, TypeError, ValueError):
            return None
        if len(parts) != len(self.composite_key_fields):
            return None
        return parts
