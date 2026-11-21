from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
def role_required(*roles):
 def check(user): return user.is_authenticated and user.role in roles and not user.is_suspended
 return user_passes_test(check)
