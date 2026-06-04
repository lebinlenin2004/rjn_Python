from django.contrib.auth import get_user_model
from django.core import signing
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import BulkInquiry, CartItem, Category, Feedback, Order, Product, Profile
from .mailers import (
    read_email_verification_token,
    read_password_reset_token,
    send_order_confirmation_email,
    send_order_status_email,
    send_password_reset_email,
    send_verification_email,
)
from .permissions import IsAdminRole, IsVerifiedUser, user_role
from .serializers import (
    BulkInquirySerializer,
    CartItemSerializer,
    CategorySerializer,
    CheckoutSerializer,
    FeedbackSerializer,
    OrderSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProductSerializer,
    ProfileSerializer,
    RegisterSerializer,
)
from .storage import upload_to_supabase_storage

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        send_verification_email(self.request, user)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        response.data = {'detail': 'Account created. Please check your email to verify your account.'}
        return response


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def verify_email(request):
    token = request.query_params.get('token')
    if not token:
        return Response({'detail': 'Verification token is required.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        payload = read_email_verification_token(token)
    except signing.SignatureExpired:
        return Response({'detail': 'Verification link expired. Please register again or contact support.'}, status=status.HTTP_400_BAD_REQUEST)
    except signing.BadSignature:
        return Response({'detail': 'Invalid verification link.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(id=payload.get('user_id'), email=payload.get('email')).first()
    if not user:
        return Response({'detail': 'Verification user not found.'}, status=status.HTTP_404_NOT_FOUND)
    user.is_active = True
    user.save(update_fields=['is_active'])
    Profile.objects.get_or_create(
        user=user,
        defaults={'full_name': user.get_full_name() or user.email or user.username},
    )
    return Response({'detail': 'Email verified. You can login now.'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    profile, _created = Profile.objects.get_or_create(
        user=request.user,
        defaults={'full_name': request.user.get_full_name() or request.user.email or request.user.username},
    )
    return Response(ProfileSerializer(profile).data)


@api_view(['PATCH'])
@permission_classes([permissions.IsAuthenticated])
def update_profile(request):
    profile, _created = Profile.objects.get_or_create(
        user=request.user,
        defaults={'full_name': request.user.get_full_name() or request.user.email or request.user.username},
    )
    serializer = ProfileSerializer(profile, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def request_password_reset(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email'].lower().strip()
    user = User.objects.filter(email=email).first() or User.objects.filter(username=email).first()
    if user and user.is_active:
        send_password_reset_email(user)
    return Response({'detail': 'If an active account exists for this email, a password reset link has been sent.'})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def confirm_password_reset(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        payload = read_password_reset_token(serializer.validated_data['token'])
    except signing.SignatureExpired:
        return Response({'detail': 'Password reset link expired. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)
    except signing.BadSignature:
        return Response({'detail': 'Invalid password reset link.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(id=payload.get('user_id'), email=payload.get('email'), is_active=True).first()
    if not user:
        return Response({'detail': 'Password reset user not found.'}, status=status.HTTP_404_NOT_FOUND)
    user.set_password(serializer.validated_data['password'])
    user.save(update_fields=['password'])
    return Response({'detail': 'Password reset successfully. You can login now.'})


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.AllowAny()]
        return [IsAdminRole()]


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.select_related('category', 'seller', 'seller__profile').prefetch_related('feedback')
        if self.action in ('list', 'retrieve'):
            queryset = queryset.filter(is_active=True)

        category = self.request.query_params.get('category')
        search = self.request.query_params.get('q') or self.request.query_params.get('search')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        sort = self.request.query_params.get('sort', 'newest')
        mine = self.request.query_params.get('mine')

        if mine and self.request.user.is_authenticated:
            queryset = queryset.filter(seller=self.request.user)
        if category:
            category_filter = Q(category__slug=category)
            if str(category).isdigit():
                category_filter |= Q(category_id=category)
            queryset = queryset.filter(category_filter)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        sort_map = {
            'newest': '-created_at',
            'price_low': 'price',
            'price_high': '-price',
            'name': 'name',
        }
        return queryset.order_by(sort_map.get(sort, '-created_at'))

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.AllowAny()]
        return [IsVerifiedUser()]

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    def perform_update(self, serializer):
        product = self.get_object()
        if not (self.request.user.is_staff or user_role(self.request.user) == 'admin' or product.seller_id == self.request.user.id):
            self.permission_denied(self.request)
        serializer.save()

    def perform_destroy(self, instance):
        if not (self.request.user.is_staff or user_role(self.request.user) == 'admin' or instance.seller_id == self.request.user.id):
            self.permission_denied(self.request)
        instance.delete()

    @action(detail=False, methods=['post'], permission_classes=[IsVerifiedUser])
    def upload_image(self, request):
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'Image file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            public_url = upload_to_supabase_storage(image, folder=f'products/{request.user.id}')
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'url': public_url})


class FeedbackView(generics.CreateAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.select_related('product', 'product__category', 'product__seller').filter(user=self.request.user)

    def perform_create(self, serializer):
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']
        item, created = CartItem.objects.get_or_create(user=self.request.user, product=product, defaults={'quantity': quantity})
        if not created:
            item.quantity += quantity
            item.save(update_fields=['quantity', 'updated_at'])
        serializer.instance = item


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Order.objects.prefetch_related('items')
        if self.request.user.is_staff or user_role(self.request.user) == 'admin':
            return queryset
        return queryset.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        send_order_confirmation_email(order)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminRole])
    def set_status(self, request, pk=None):
        order = self.get_object()
        next_status = request.data.get('status')
        valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}
        if next_status not in valid_statuses:
            return Response({'detail': 'Invalid order status.'}, status=status.HTTP_400_BAD_REQUEST)
        order.status = next_status
        order.save(update_fields=['status', 'updated_at'])
        send_order_status_email(order)
        return Response(OrderSerializer(order).data)


class BulkInquiryView(generics.CreateAPIView):
    queryset = BulkInquiry.objects.all()
    serializer_class = BulkInquirySerializer
    permission_classes = [permissions.AllowAny]


@api_view(['GET'])
@permission_classes([IsAdminRole])
def admin_summary(request):
    return Response({
        'products': Product.objects.count(),
        'active_products': Product.objects.filter(is_active=True).count(),
        'orders': Order.objects.count(),
        'pending_orders': Order.objects.filter(status='pending').count(),
        'total_sales': Order.objects.exclude(status='cancelled').aggregate(total=Sum('total_amount'))['total'] or 0,
        'customers': User.objects.count(),
        'inquiries': BulkInquiry.objects.count(),
        'recent_orders': OrderSerializer(Order.objects.prefetch_related('items')[:8], many=True).data,
    })
