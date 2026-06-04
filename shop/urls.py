from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    BulkInquiryView,
    CartViewSet,
    CategoryViewSet,
    FeedbackView,
    OrderViewSet,
    ProductViewSet,
    RegisterView,
    admin_summary,
    confirm_password_reset,
    me,
    request_password_reset,
    verify_email,
    update_profile,
)

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('products', ProductViewSet, basename='product')
router.register('cart', CartViewSet, basename='cart')
router.register('orders', OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', me, name='me'),
    path('auth/profile/', update_profile, name='update_profile'),
    path('auth/verify-email/', verify_email, name='verify_email'),
    path('auth/password-reset/', request_password_reset, name='request_password_reset'),
    path('auth/password-reset/confirm/', confirm_password_reset, name='confirm_password_reset'),
    path('feedback/', FeedbackView.as_view(), name='feedback'),
    path('inquiries/', BulkInquiryView.as_view(), name='inquiries'),
    path('admin/summary/', admin_summary, name='admin_summary'),
]
