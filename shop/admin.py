from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import BulkInquiry, CartItem, Category, Feedback, Order, OrderItem, Product, Profile
from .mailers import send_order_status_email

User = get_user_model()

admin.site.site_header = 'RJN Foods Admin'
admin.site.site_title = 'RJN Admin'
admin.site.index_title = 'Store Management'


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    fields = ('full_name', 'phone', 'address', 'role', 'created_at')
    readonly_fields = ('created_at',)


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('id', 'username', 'email', 'profile_full_name', 'profile_phone', 'profile_address', 'profile_role', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'profile__role')
    search_fields = ('username', 'email', 'profile__full_name', 'profile__phone', 'profile__address')

    @admin.display(description='Full name')
    def profile_full_name(self, obj):
        return getattr(getattr(obj, 'profile', None), 'full_name', '')

    @admin.display(description='Phone')
    def profile_phone(self, obj):
        return getattr(getattr(obj, 'profile', None), 'phone', '')

    @admin.display(description='Address')
    def profile_address(self, obj):
        return getattr(getattr(obj, 'profile', None), 'address', '')

    @admin.display(description='Role')
    def profile_role(self, obj):
        return getattr(getattr(obj, 'profile', None), 'role', '')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'product_image', 'quantity', 'unit_price', 'line_total')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('id', 'full_name', 'email', 'phone', 'address_preview', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('full_name', 'email', 'phone', 'address')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Address')
    def address_preview(self, obj):
        return obj.address[:80]

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = Order.objects.filter(pk=obj.pk).values_list('status', flat=True).first()

        super().save_model(request, obj, form, change)

        if change and old_status and old_status != obj.status:
            send_order_status_email(obj)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'full_name', 'phone', 'address_preview', 'role', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__email', 'user__username', 'full_name', 'phone', 'address')
    list_editable = ('phone', 'role')
    readonly_fields = ('created_at',)

    @admin.display(description='Email')
    def user_email(self, obj):
        return obj.user.email or obj.user.username

    @admin.display(description='Address')
    def address_preview(self, obj):
        return obj.address[:100]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'created_at')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'seller_email', 'price', 'stock_status', 'inventory_count', 'is_active', 'created_at')
    list_filter = ('category', 'stock_status', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'seller__email', 'seller__username', 'category__name')
    list_editable = ('price', 'stock_status', 'inventory_count', 'is_active')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Seller')
    def seller_email(self, obj):
        if not obj.seller:
            return ''
        return obj.seller.email or obj.seller.username


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'user_email', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__name', 'user__email', 'comment')

    @admin.display(description='User')
    def user_email(self, obj):
        if not obj.user:
            return ''
        return obj.user.email or obj.user.username


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_email', 'product', 'quantity', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__username', 'product__name')

    @admin.display(description='User')
    def user_email(self, obj):
        return obj.user.email or obj.user.username


@admin.register(BulkInquiry)
class BulkInquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'company', 'email', 'phone', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'company', 'email', 'phone', 'message')
    list_editable = ('status',)
