from pathlib import Path
from uuid import uuid4

from django.conf import settings


def upload_to_supabase_storage(file_obj, folder='products'):
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError('Install the supabase Python package before uploading images.') from exc

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError('Supabase Storage is not configured.')

    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    extension = Path(file_obj.name).suffix or '.jpg'
    path = f'{folder}/{uuid4().hex}{extension}'
    content = file_obj.read()
    supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
        path,
        content,
        file_options={'content-type': getattr(file_obj, 'content_type', 'application/octet-stream')},
    )
    return supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET).get_public_url(path)
