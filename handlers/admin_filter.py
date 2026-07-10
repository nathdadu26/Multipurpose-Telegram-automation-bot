from functools import wraps
from config.settings import settings


def admin_only(func):
    """Silently ignore any update from someone other than the single admin."""

    @wraps(func)
    async def wrapper(update, context, *a, **kw):
        user = update.effective_user
        if user is None or user.id != settings.admin_id:
            return
        return await func(update, context, *a, **kw)

    return wrapper
