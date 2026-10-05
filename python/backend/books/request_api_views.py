from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from messaging.models import Message
from messaging.services import get_or_create_private_conversation
from notifications.services import create_notification
from .category_taxonomy import BOOK_CATEGORY_SLUGS
from .models import (
    Book,
    BookRequest,
    BookWork,
    Category,
    LendListing,
    RequestInterest,
    RequestMatch,
    SaleListing,
)
from .pagination import BookPagination


class BookRequestInputSerializer(serializers.Serializer):
    request_type = serializers.ChoiceField(
        choices=('BUY', 'BORROW', 'SELL_INTENT'),
    )
    book_work_id = serializers.PrimaryKeyRelatedField(
        source='book_work',
        queryset=BookWork.objects.all(),
        required=False,
        allow_null=True,
    )
    category_id = serializers.PrimaryKeyRelatedField(
        source='category',
        queryset=Category.objects.filter(
            status='ACTIVE',
            slug__in=BOOK_CATEGORY_SLUGS,
        ),
        required=False,
        allow_null=True,
    )
    title_keyword = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    budget_max = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
        allow_null=True,
    )
    asking_price = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        min_value=0,
        required=False,
        allow_null=True,
    )
    condition_preference = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    planned_at = serializers.DateTimeField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        request_type = attrs.get(
            'request_type',
            getattr(self.instance, 'request_type', None),
        )
        book_work = attrs.get('book_work', getattr(self.instance, 'book_work', None))
        category = attrs.get('category', getattr(self.instance, 'category', None))
        title_keyword = attrs.get(
            'title_keyword',
            getattr(self.instance, 'title_keyword', None),
        )
        if not book_work and not title_keyword and not category:
            raise serializers.ValidationError(
                'Cần chọn đầu sách hoặc nhập từ khóa tiêu đề.',
            )
        if (
            'title_keyword' in attrs
            and 'book_work' not in attrs
            and (
                self.instance is None
                or attrs['title_keyword'] != self.instance.title_keyword
            )
        ):
            attrs['book_work'] = None
        budget_max = attrs.get('budget_max', getattr(self.instance, 'budget_max', None))
        asking_price = attrs.get(
            'asking_price',
            getattr(self.instance, 'asking_price', None),
        )
        if request_type == 'SELL_INTENT':
            if budget_max is not None:
                raise serializers.ValidationError({'budget_max': 'Không áp dụng cho SELL_INTENT.'})
        elif asking_price is not None:
            raise serializers.ValidationError({'asking_price': 'Chỉ áp dụng cho SELL_INTENT.'})
        if (
            'expires_at' in attrs
            and attrs['expires_at'] is not None
            and attrs['expires_at'] <= timezone.now()
        ):
            raise serializers.ValidationError({'expires_at': 'Thời hạn phải ở tương lai.'})
        planned_at_was_submitted = 'planned_at' in attrs
        expires_at_was_submitted = 'expires_at' in attrs
        planned_at = attrs.get(
            'planned_at',
            getattr(self.instance, 'planned_at', None),
        )
        expires_at = attrs.get(
            'expires_at',
            getattr(self.instance, 'expires_at', None),
        )
        now = timezone.now()
        if (
            planned_at_was_submitted
            and planned_at is not None
            and planned_at <= now
        ):
            raise serializers.ValidationError({
                'planned_at': 'Ngày dự định phải ở trong tương lai.',
            })
        if (
            (planned_at_was_submitted or expires_at_was_submitted)
            and planned_at is not None
            and expires_at is not None
            and expires_at <= planned_at
        ):
            raise serializers.ValidationError({
                'expires_at': 'Yêu cầu cần còn hiệu lực sau ngày dự định.',
            })
        return attrs


def request_payload(item):
    payload = {
        'id': item.id,
        'user_id': item.user_id,
        'request_type': item.request_type,
        'book_work_id': item.book_work_id,
        'category_id': item.category_id,
        'title_keyword': item.title_keyword,
        'description': item.description,
        'budget_max': str(item.budget_max) if item.budget_max is not None else None,
        'asking_price': str(item.asking_price) if item.asking_price is not None else None,
        'currency': item.currency,
        'condition_preference': item.condition_preference,
        'status': item.status,
        'planned_at': item.planned_at,
        'expires_at': item.expires_at,
        'same_intent_count': getattr(item, 'same_intent_count', 0),
        'created_at': item.created_at,
        'updated_at': item.updated_at,
    }
    if hasattr(item, 'my_interest'):
        payload['my_interest'] = item.my_interest
    return payload


def annotate_same_intent_count(queryset, now=None, user_id=None):
    now = now or timezone.now()
    same_book = (
        Q(book_work_id=OuterRef('book_work_id'), book_work_id__isnull=False)
        | Q(
            book_work__isnull=True,
            title_keyword__isnull=False,
            title_keyword__iexact=OuterRef('title_keyword'),
        )
        | Q(
            book_work__isnull=True,
            title_keyword__isnull=False,
            title_keyword__iexact=OuterRef('book_work__title'),
        )
        | Q(
            book_work_id__isnull=False,
            title_keyword__isnull=False,
            book_work__title__iexact=OuterRef('title_keyword'),
        )
    )
    count_query = (
        BookRequest.objects.filter(
            request_type=OuterRef('request_type'),
            status='OPEN',
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .filter(same_book)
        .values('request_type')
        .annotate(total=Count('user_id', distinct=True))
        .values('total')[:1]
    )
    queryset = queryset.annotate(
        same_intent_count=Coalesce(
            Subquery(count_query, output_field=IntegerField()),
            Value(0),
        ),
    )
    if user_id is not None:
        queryset = queryset.annotate(
            my_interest=Exists(RequestInterest.objects.filter(
                request_id=OuterRef('pk'),
                user_id=user_id,
                status='ACTIVE',
            )),
        )
    return queryset


def intent_summary(book, user=None):
    now = timezone.now()
    requests = BookRequest.objects.filter(
        book_work_id=book.book_edition.book_work_id,
        status='OPEN',
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    )
    buying_count = requests.filter(request_type='BUY').aggregate(
        count=Count('user_id', distinct=True),
    )['count']
    selling_count = requests.filter(request_type='SELL_INTENT').aggregate(
        count=Count('user_id', distinct=True),
    )['count']
    own = {}
    if user is not None and user.is_authenticated:
        own = {
            item.request_type: item.id
            for item in requests.filter(
                user_id=user.id,
                request_type__in=('BUY', 'SELL_INTENT'),
            ).order_by('-created_at', '-id')
        }
    return {
        'buying_count': buying_count,
        'selling_count': selling_count,
        'my_buy_request_id': own.get('BUY'),
        'my_sell_intent_request_id': own.get('SELL_INTENT'),
    }


class BookIntentSummaryView(APIView):
    def get_permissions(self):
        return [AllowAny() if self.request.method == 'GET' else IsAuthenticated()]

    def get(self, request, book_id):
        book = get_object_or_404(
            Book.objects.select_related('book_edition__book_work'),
            pk=book_id,
        )
        return Response(intent_summary(book, request.user))

    def post(self, request, book_id):
        self._validate_request_type(request)
        with transaction.atomic():
            return self._change_intent(request, book_id, cancel=False)

    def delete(self, request, book_id):
        self._validate_request_type(request)
        with transaction.atomic():
            return self._change_intent(request, book_id, cancel=True)

    @staticmethod
    def _validate_request_type(request):
        request_type = request.data.get('request_type')
        if request_type not in ('BUY', 'SELL_INTENT'):
            raise serializers.ValidationError({
                'request_type': 'Chỉ hỗ trợ BUY hoặc SELL_INTENT.',
            })
        return request_type

    @staticmethod
    def _change_intent(request, book_id, *, cancel):
        request_type = BookIntentSummaryView._validate_request_type(request)
        book = get_object_or_404(
            Book.objects.select_related('book_edition__book_work'),
            pk=book_id,
        )
        work = BookWork.objects.select_for_update().get(
            pk=book.book_edition.book_work_id,
        )
        existing = BookRequest.objects.select_for_update().filter(
            user_id=request.user.id,
            book_work_id=work.id,
            request_type=request_type,
        ).order_by('-created_at', '-id').first()
        now = timezone.now()
        if cancel:
            if existing is None or existing.status != 'OPEN':
                raise serializers.ValidationError('Không có dự định đang mở để hủy.')
            existing.status = 'CANCELLED'
            existing.updated_at = now
            existing.save(update_fields=['status', 'updated_at'])
        elif existing is not None:
            if existing.status != 'OPEN' or (
                existing.expires_at is not None and existing.expires_at <= now
            ):
                existing.status = 'OPEN'
                existing.expires_at = None
                existing.updated_at = now
                existing.save(update_fields=['status', 'expires_at', 'updated_at'])
        else:
            BookRequest.objects.create(
                user=request.user,
                request_type=request_type,
                book_work=work,
                title_keyword=work.title,
                status='OPEN',
                created_at=now,
                updated_at=now,
            )
        return Response(intent_summary(book, request.user))


class BookRequestListCreateView(APIView):
    def get_permissions(self):
        is_private_list = (
            self.request.method == 'GET'
            and self.request.query_params.get('scope') == 'mine'
        )
        permission = (
            IsAuthenticated
            if self.request.method == 'POST' or is_private_list
            else AllowAny
        )
        return [permission()]

    def get(self, request):
        now = timezone.now()
        if request.query_params.get('scope') == 'mine':
            queryset = BookRequest.objects.filter(user_id=request.user.id)
        else:
            queryset = BookRequest.objects.filter(status='OPEN').filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now),
            ).filter(
                Q(category__isnull=True)
                | Q(
                    category__status='ACTIVE',
                    category__slug__in=BOOK_CATEGORY_SLUGS,
                ),
            )
            if request.user.is_authenticated:
                queryset = queryset.exclude(user_id=request.user.id)
            request_type = request.query_params.get('request_type')
            if request_type:
                if request_type not in ('BUY', 'BORROW', 'SELL_INTENT'):
                    raise serializers.ValidationError({
                        'request_type': 'Loại yêu cầu không hợp lệ.',
                    })
                queryset = queryset.filter(request_type=request_type)
        queryset = annotate_same_intent_count(
            queryset,
            now,
            request.user.id if request.user.is_authenticated else None,
        ).order_by(
            '-created_at',
            '-id',
        )
        paginator = BookPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([
            request_payload(item) for item in page
        ])

    def post(self, request):
        serializer = BookRequestInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = self._save(serializer, user=request.user)
        return Response(request_payload(item), status=status.HTTP_201_CREATED)

    @staticmethod
    def _save(serializer, *, user, instance=None):
        data = serializer.validated_data
        now = timezone.now()
        request_type = data.get(
            'request_type',
            instance.request_type if instance is not None else None,
        )
        fields = {
            key: data[key]
            for key in (
                'book_work', 'category', 'title_keyword', 'description',
                'budget_max', 'asking_price', 'condition_preference',
                'planned_at', 'expires_at',
            )
            if key in data
        }
        if request_type == 'SELL_INTENT':
            fields['budget_max'] = None
        else:
            fields['asking_price'] = None
        if fields.get('budget_max') is not None or fields.get('asking_price') is not None:
            fields['currency'] = 'VND'
        elif instance is None:
            fields['currency'] = None

        if instance is None:
            return BookRequest.objects.create(
                user=user,
                request_type=request_type,
                status='OPEN',
                created_at=now,
                updated_at=now,
                **fields,
            )
        for key, value in fields.items():
            setattr(instance, key, value)
        instance.request_type = request_type
        instance.updated_at = now
        instance.save()
        return instance


class BookRequestDetailView(APIView):
    def get_permissions(self):
        permission = IsAuthenticated if self.request.method in ('PATCH', 'DELETE') else AllowAny
        return [permission()]

    def get(self, request, request_id):
        item = get_object_or_404(BookRequest, pk=request_id)
        if item.status != 'OPEN' and (
            not request.user.is_authenticated or item.user_id != request.user.id
        ):
            raise PermissionDenied('Yêu cầu này không khả dụng.')
        if (
            item.category_id
            and (
                item.category.status != 'ACTIVE'
                or item.category.slug not in BOOK_CATEGORY_SLUGS
            )
            and (
                not request.user.is_authenticated
                or item.user_id != request.user.id
            )
        ):
            raise PermissionDenied('Danh mục yêu cầu không còn được hỗ trợ.')
        return Response(request_payload(item))

    def patch(self, request, request_id):
        item = get_object_or_404(BookRequest, pk=request_id)
        if item.user_id != request.user.id:
            raise PermissionDenied('Bạn không có quyền sửa yêu cầu này.')
        if item.status != 'OPEN':
            raise serializers.ValidationError('Chỉ có thể sửa yêu cầu đang mở.')
        serializer = BookRequestInputSerializer(
            item,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        item = BookRequestListCreateView._save(
            serializer,
            user=request.user,
            instance=item,
        )
        return Response(request_payload(item))

    def delete(self, request, request_id):
        item = get_object_or_404(BookRequest, pk=request_id)
        if item.user_id != request.user.id:
            raise PermissionDenied('Bạn không có quyền hủy yêu cầu này.')
        if item.status != 'OPEN':
            raise serializers.ValidationError('Yêu cầu không còn ở trạng thái mở.')
        item.status = 'CANCELLED'
        item.updated_at = timezone.now()
        item.save(update_fields=['status', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookRequestInterestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id):
        book_request = get_object_or_404(BookRequest, pk=request_id)
        if book_request.user_id != request.user.id:
            raise PermissionDenied('Bạn không có quyền xem các lượt quan tâm.')
        interests = RequestInterest.objects.filter(
            request=book_request,
            status='ACTIVE',
        ).select_related('user').order_by('-created_at', '-id')
        paginator = BookPagination()
        page = paginator.paginate_queryset(interests, request, view=self)
        return paginator.get_paginated_response([
            {
                'id': item.id,
                'user_id': item.user_id,
                'note': item.note,
                'created_at': item.created_at,
            }
            for item in page
        ])

    @transaction.atomic
    def post(self, request, request_id):
        book_request = get_object_or_404(
            BookRequest.objects.select_for_update(),
            pk=request_id,
            status='OPEN',
        )
        now = timezone.now()
        if book_request.expires_at is not None and book_request.expires_at <= now:
            raise serializers.ValidationError('Yêu cầu này đã hết hạn.')
        if book_request.user_id == request.user.id:
            raise serializers.ValidationError('Không thể quan tâm yêu cầu của chính bạn.')
        note = serializers.CharField(
            required=False,
            allow_blank=True,
            allow_null=True,
            max_length=1500,
        ).run_validation(request.data.get('note'))
        interest, created = RequestInterest.objects.get_or_create(
            request=book_request,
            user=request.user,
            defaults={
                'note': note,
                'status': 'ACTIVE',
                'created_at': now,
            },
        )
        was_active = not created and interest.status == 'ACTIVE'
        if not created and not was_active:
            interest.note = note
            interest.status = 'ACTIVE'
            interest.save(update_fields=['note', 'status'])
        elif not created and interest.note != note:
            interest.note = note
            interest.save(update_fields=['note'])

        conversation, conversation_created = get_or_create_private_conversation(
            request.user.id,
            book_request.user_id,
        )
        should_send_contact = created or not was_active or conversation_created
        if should_send_contact:
            title = (
                book_request.book_work.title
                if book_request.book_work_id
                else book_request.title_keyword
                or 'yêu cầu sách'
            )
            intent = {
                'BUY': 'có thông tin sách phù hợp',
                'BORROW': 'có thể cho mượn sách phù hợp',
                'SELL_INTENT': 'quan tâm muốn mua sách bạn đăng',
            }[book_request.request_type]
            intro = f'Mình {intent} với yêu cầu “{title}”.'
            content = f'{intro}\n{note.strip()}' if note and note.strip() else intro
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                message_type='TEXT',
                content=content,
                sent_at=now,
            )
            conversation.updated_at = now
            conversation.save(update_fields=['updated_at'])
            create_notification(
                book_request.user_id,
                notification_type='BOOK_REQUEST',
                title='Có người phản hồi yêu cầu sách',
                content=f'{request.user.full_name} {intent}. Mở tin nhắn để trao đổi.',
                entity_type='CONVERSATION',
                entity_id=conversation.id,
                created_at=now,
            )
        return Response(
            {
                'id': interest.id,
                'request_id': book_request.id,
                'status': interest.status,
                'conversation_id': conversation.id,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, request_id):
        interest = get_object_or_404(
            RequestInterest,
            request_id=request_id,
            user=request.user,
        )
        interest.status = 'WITHDRAWN'
        interest.save(update_fields=['status'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookRequestMatchListView(APIView):
    permission_classes = [IsAuthenticated]
    MAX_MATCHES = 50

    @transaction.atomic
    def get(self, request, request_id):
        book_request = get_object_or_404(
            BookRequest.objects.select_for_update(),
            pk=request_id,
        )
        if book_request.user_id != request.user.id:
            raise PermissionDenied('Bạn không có quyền xem kết quả này.')

        matches = []
        now = timezone.now()
        if book_request.status != 'OPEN' or (
            book_request.expires_at and book_request.expires_at <= now
        ):
            return Response(matches)

        if book_request.request_type in ('BUY', 'BORROW'):
            for listing in self._candidates(book_request):
                if len(matches) >= self.MAX_MATCHES:
                    break
                if book_request.request_type == 'BUY':
                    lookup = {
                        'request': book_request,
                        'sale_listing': listing,
                        'lend_listing': None,
                        'matched_request': None,
                    }
                    title = listing.title
                    price = listing.price
                    match_type = 'SALE'
                    listing_id = listing.id
                else:
                    lookup = {
                        'request': book_request,
                        'sale_listing': None,
                        'lend_listing': listing,
                        'matched_request': None,
                    }
                    title = listing.title
                    price = listing.rental_fee
                    match_type = 'BORROW'
                    listing_id = listing.id

                score = self._score(book_request, listing)
                match, _ = RequestMatch.objects.get_or_create(
                    **lookup,
                    defaults={
                        'match_type': match_type,
                        'score': score,
                        'status': 'SUGGESTED',
                        'created_at': now,
                    },
                )
                if match.status == 'SUGGESTED' and match.score != score:
                    match.score = score
                    match.save(update_fields=['score'])
                matches.append({
                    'id': match.id,
                    'match_type': match_type,
                    'listing_id': listing_id,
                    'title': title,
                    'price': str(price),
                    'score': str(score),
                    'status': match.status,
                })

        if book_request.request_type in ('BUY', 'SELL_INTENT'):
            counterpart_requests = self._request_candidates(book_request)
            for counterpart in counterpart_requests:
                if len(matches) >= self.MAX_MATCHES:
                    break
                score = self._request_score(book_request, counterpart)
                match, _ = RequestMatch.objects.get_or_create(
                    request=book_request,
                    matched_request=counterpart,
                    sale_listing=None,
                    lend_listing=None,
                    defaults={
                        'match_type': 'BUY_SELL',
                        'score': score,
                        'status': 'SUGGESTED',
                        'created_at': now,
                    },
                )
                if match.status == 'SUGGESTED' and match.score != score:
                    match.score = score
                    match.save(update_fields=['score'])
                title = (
                    counterpart.book_work.title
                    if counterpart.book_work_id
                    else counterpart.title_keyword
                    or (counterpart.category.name if counterpart.category_id else '')
                )
                counterpart_price = (
                    counterpart.asking_price
                    if counterpart.request_type == 'SELL_INTENT'
                    else counterpart.budget_max
                )
                matches.append({
                    'id': match.id,
                    'match_type': 'BUY_SELL',
                    'matched_request_id': counterpart.id,
                    'title': title,
                    'price': (
                        str(counterpart_price)
                        if counterpart_price is not None
                        else None
                    ),
                    'score': str(score),
                    'status': match.status,
                })
        return Response(matches)

    @staticmethod
    def _candidates(book_request):
        if book_request.request_type == 'BUY':
            queryset = SaleListing.objects.filter(
                status='ACTIVE',
                book__status='AVAILABLE',
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
            ).select_related('book__book_edition__book_work')
            price_field = 'price'
        elif book_request.request_type == 'BORROW':
            queryset = LendListing.objects.filter(
                status='ACTIVE',
                book__status='AVAILABLE',
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
            ).select_related('book__book_edition__book_work')
            price_field = 'rental_fee'
        else:
            return []

        if book_request.budget_max is not None:
            queryset = queryset.filter(**{f'{price_field}__lte': book_request.budget_max})
        if book_request.condition_preference:
            queryset = queryset.filter(
                book__condition_label__iexact=book_request.condition_preference,
            )
        if book_request.book_work_id:
            queryset = queryset.filter(
                book__book_edition__book_work_id=book_request.book_work_id,
            )
        else:
            filters = Q()
            if book_request.title_keyword:
                filters |= Q(title__icontains=book_request.title_keyword)
                filters |= Q(
                    book__book_edition__book_work__title__icontains=book_request.title_keyword,
                )
            if book_request.category_id:
                filters |= Q(
                    book__book_edition__book_work__category_id=book_request.category_id,
                )
            queryset = queryset.filter(filters)
        return list(queryset.order_by('-created_at', '-id')[:BookRequestMatchListView.MAX_MATCHES])

    @staticmethod
    def _request_candidates(book_request):
        opposite_type = (
            'SELL_INTENT'
            if book_request.request_type == 'BUY'
            else 'BUY'
        )
        now = timezone.now()
        queryset = BookRequest.objects.filter(
            request_type=opposite_type,
            status='OPEN',
        ).exclude(user_id=book_request.user_id).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now),
        )
        if book_request.request_type == 'BUY':
            if book_request.budget_max is not None:
                queryset = queryset.filter(
                    Q(asking_price__isnull=True)
                    | Q(asking_price__lte=book_request.budget_max),
                )
        elif book_request.asking_price is not None:
            queryset = queryset.filter(
                Q(budget_max__isnull=True)
                | Q(budget_max__gte=book_request.asking_price),
            )

        if book_request.condition_preference:
            queryset = queryset.filter(
                Q(condition_preference__isnull=True)
                | Q(condition_preference__iexact=book_request.condition_preference),
            )
        if book_request.book_work_id:
            queryset = queryset.filter(
                Q(book_work_id=book_request.book_work_id)
                | Q(
                    book_work__isnull=True,
                    title_keyword__icontains=book_request.book_work.title,
                ),
            )
        elif book_request.category_id:
            queryset = queryset.filter(
                Q(category_id=book_request.category_id)
                | Q(book_work__category_id=book_request.category_id),
            )
        elif book_request.title_keyword:
            queryset = queryset.filter(
                Q(title_keyword__icontains=book_request.title_keyword)
                | Q(book_work__title__icontains=book_request.title_keyword)
                | Q(category__name__icontains=book_request.title_keyword),
            )
        return list(
            queryset.select_related('book_work', 'category')
            .order_by('-created_at', '-id')[:BookRequestMatchListView.MAX_MATCHES],
        )

    @staticmethod
    def _request_score(source, counterpart):
        if source.book_work_id and source.book_work_id == counterpart.book_work_id:
            return Decimal('1.00000')
        source_category_id = (
            source.category_id
            or (source.book_work.category_id if source.book_work_id else None)
        )
        counterpart_category_id = (
            counterpart.category_id
            or (
                counterpart.book_work.category_id
                if counterpart.book_work_id
                else None
            )
        )
        if source_category_id and source_category_id == counterpart_category_id:
            return Decimal('0.80000')
        return Decimal('0.60000')

    @staticmethod
    def _score(book_request, listing):
        if (
            book_request.book_work_id
            and listing.book.book_edition.book_work_id == book_request.book_work_id
        ):
            return Decimal('1.00000')
        if (
            book_request.category_id
            and listing.book.book_edition.book_work.category_id == book_request.category_id
        ):
            return Decimal('0.80000')
        return Decimal('0.60000')
