from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
import logging


logger = logging.getLogger(__name__)


EMAIL_VERIFICATION_SALT = 'rjn.email.verification'
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24
PASSWORD_RESET_SALT = 'rjn.password.reset'
PASSWORD_RESET_MAX_AGE = 60 * 60


def safe_send_mail(subject, message, recipient):
    try:
        return send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send email to %s', recipient)
        return 0


def make_email_verification_token(user):
    return signing.dumps({'user_id': user.id, 'email': user.email}, salt=EMAIL_VERIFICATION_SALT)


def read_email_verification_token(token):
    return signing.loads(token, salt=EMAIL_VERIFICATION_SALT, max_age=EMAIL_VERIFICATION_MAX_AGE)


def make_password_reset_token(user):
    return signing.dumps({'user_id': user.id, 'email': user.email}, salt=PASSWORD_RESET_SALT)


def read_password_reset_token(token):
    return signing.loads(token, salt=PASSWORD_RESET_SALT, max_age=PASSWORD_RESET_MAX_AGE)


def send_verification_email(request, user):
    token = make_email_verification_token(user)
    verify_url = f'{settings.FRONTEND_URL.rstrip()}/verify-email?token={token}'
    subject = 'Verify your RJN Foods account'
    message = (
        f'Hi {user.email},\n\n'
        'Welcome to RJN Foods. Please verify your email address to activate your account.\n\n'
        f'Verify email: {verify_url}\n\n'
        'This link expires in 24 hours.\n\n'
        'RJN Foods'
    )
    return safe_send_mail(subject, message, user.email)


def send_password_reset_email(user):
    token = make_password_reset_token(user)
    reset_url = f'{settings.FRONTEND_URL.rstrip()}/reset-password?token={token}'
    subject = 'Reset your RJN Foods password'
    message = (
        f'Hi {user.email},\n\n'
        'We received a request to reset your RJN Foods password.\n\n'
        f'Reset password: {reset_url}\n\n'
        'This link expires in 1 hour. If you did not request this, you can ignore this email.\n\n'
        'RJN Foods'
    )
    return safe_send_mail(subject, message, user.email)


def send_order_confirmation_email(order):
    item_lines = [
        f'- {item.product_name} x {item.quantity}: AED {item.line_total}'
        for item in order.items.all()
    ]
    subject = f'RJN Foods order #{order.id} confirmed'
    message = (
        f'Hi {order.full_name},\n\n'
        'Thank you for your order. We have received it and our team will process it soon.\n\n'
        f'Order ID: #{order.id}\n'
        f'Status: {order.status}\n'
        f'Total: AED {order.total_amount}\n\n'
        'Items:\n'
        f'{chr(10).join(item_lines)}\n\n'
        f'Delivery address:\n{order.address}\n\n'
        'RJN Foods'
    )
    return safe_send_mail(subject, message, order.email)


def send_order_status_email(order):
    subject = f'RJN Foods order #{order.id} status update'
    message = (
        f'Hi {order.full_name},\n\n'
        f'Your order #{order.id} status is now: {order.status.upper()}.\n\n'
        f'Total: AED {order.total_amount}\n\n'
        'Thank you for shopping with RJN Foods.'
    )
    return safe_send_mail(subject, message, order.email)
