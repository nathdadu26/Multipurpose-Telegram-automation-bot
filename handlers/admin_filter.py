from functools import wraps
from config.settings import settings


def admin_only(func):
    """Silently ignore any update from someone who is not an admin."""

    @wraps(func)
    async def wrapper(update, context, *a, **kw):
        user = update.effective_user
        if user is None or user.id not in settings.admin_ids:
            return
        return await func(update, context, *a, **kw)

    return wrapper
