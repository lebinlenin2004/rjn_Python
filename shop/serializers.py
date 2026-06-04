from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import BulkInquiry, CartItem, Category, Feedback, Order, OrderItem, Product, Profile

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = ('id', 'email', 'full_name', 'phone', 'address', 'role', 'created_at')
        read_only_fields = ('id', 'email', 'role', 'created_at')


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, validators=[validate_password])


class RegisterSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'full_name')

    def validate_email(self, value):
        email = value.lower().strip()
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise serializers.ValidationError('An account with this email already exists. Please login or use another email.')
        return email

    def create(self, validated_data):
        full_name = validated_data.pop('full_name', '')
        email = validated_data['email']
        user = User.objects.create_user(username=email, email=email, password=validated_data['password'], is_active=False)
        Profile.objects.get_or_create(user=user, defaults={'full_name': full_name})
        return user


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'image_url', 'created_at')


class FeedbackSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = ('id', 'product', 'user_name', 'rating', 'comment', 'created_at')
        read_only_fields = ('id', 'user_name', 'created_at')

    def get_user_name(self, obj):
        profile = getattr(obj.user, 'profile', None)
        return getattr(profile, 'full_name', '') or getattr(obj.user, 'email', '') or 'Buyer'

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    feedback = FeedbackSerializer(many=True, read_only=True)
    rating = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'seller', 'category', 'category_id', 'name', 'description', 'price',
            'min_order_quantity', 'image_url', 'image_urls', 'stock_status', 'inventory_count',
            'is_active', 'show_price', 'show_seller', 'rating', 'feedback', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'seller', 'rating', 'feedback', 'created_at', 'updated_at')

    def get_rating(self, obj):
        ratings = [item.rating for item in obj.feedback.all()]
        return sum(ratings) / len(ratings) if ratings else None

    def get_seller(self, obj):
        if not obj.seller:
            return None
        profile = getattr(obj.seller, 'profile', None)
        return {
            'id': obj.seller_id,
            'email': obj.seller.email,
            'full_name': getattr(profile, 'full_name', '') or obj.seller.email,
        }


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True), source='product', write_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'product_id', 'quantity', 'line_total', 'created_at', 'updated_at')
        read_only_fields = ('id', 'product', 'line_total', 'created_at', 'updated_at')

    def get_line_total(self, obj):
        if obj.product.price is None:
            return None
        return obj.product.price * obj.quantity

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError('Quantity must be at least 1.')
        return value


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'product_image', 'quantity', 'unit_price', 'line_total')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'full_name', 'email', 'phone', 'address', 'notes',
            'status', 'total_amount', 'items', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'status', 'total_amount', 'items', 'created_at', 'updated_at')


class CheckoutSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=180)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=40)
    address = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        cart_items = list(CartItem.objects.select_related('product').filter(user=user))
        if not cart_items:
            raise serializers.ValidationError('Cart is empty.')

        total = Decimal('0')
        order = Order.objects.create(user=user, total_amount=0, **validated_data)
        for cart_item in cart_items:
            product = cart_item.product
            unit_price = product.price
            line_total = (unit_price or Decimal('0')) * cart_item.quantity
            total += line_total
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                product_image=product.image_url,
                quantity=cart_item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        order.total_amount = total
        order.save(update_fields=['total_amount'])
        CartItem.objects.filter(user=user).delete()
        return order


class BulkInquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkInquiry
        fields = ('id', 'name', 'company', 'email', 'phone', 'message', 'status', 'created_at')
        read_only_fields = ('id', 'status', 'created_at')
