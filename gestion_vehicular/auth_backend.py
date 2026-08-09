from django.contrib.auth.backends import BaseBackend
from .models import Usuario

class UsuarioBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        try:
            usuario = Usuario.objects.get(usuario_login=username)
            if not usuario.activo:
                return None
            if usuario.check_password(password):
                return usuario
            return None
        except Usuario.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return None