#@author:  Tomas Jonatan Lopez Cruz
#@email:   20461973hola@gmail.com
#@date:    2026-10-13
#@version: 0.0.1
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from ..models import Usuario, Rol  # 👈 IMPORTANTE: Solo importamos, no definimos los modelos aquí
from .gestion_administrativa import registrar_auditoria

from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import PasswordResetView 
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.views import PasswordResetConfirmView
from django.contrib.auth.forms import SetPasswordForm

from django.db import connection
from django.contrib.auth.hashers import make_password

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        usuario = authenticate(request, username=username, password=password)
        
        if usuario is not None:
            auth_login(request, usuario)
            
            registrar_auditoria(
                request, 
                'LOGIN', 
                'SEGURIDAD', 
                f'El usuario "{usuario.usuario_login}" inició sesión en el sistema.'
            )
            
            messages.success(request, f'Bienvenido, {usuario.nombre}')
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuario o contrasena incorrectos')
    
    return render(request, 'gestion_vehicular/auth/login.html')


def logout_view(request):
    if request.user.is_authenticated:
        registrar_auditoria(
            request, 
            'LOGOUT', 
            'SEGURIDAD', 
            f'El usuario "{request.user.usuario_login}" cerró sesión.'
        )
    
    auth_logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    if request.user.id_rol_id == 1:
        return redirect('dashboard_admin')
    elif request.user.id_rol_id == 2:
        return redirect('dashboard_jefe')
    elif request.user.id_rol_id == 3:
        return redirect('dashboard_ayudante')
    return redirect('dashboard_admin')


@login_required
def lista_usuarios(request):
    usuarios = Usuario.objects.select_related('id_rol').all().order_by('nombre')
    return render(request, 'gestion_vehicular/admin/gestion_basica/usuarios_lista.html', {'usuarios': usuarios})


@login_required
def crear_usuario(request):
    if request.method == 'POST':
        rol_id = request.POST.get('rol_id')
        usuario_login = request.POST.get('usuario_login')
        password_texto_plano = request.POST.get('password')
        
        # 1. Creamos el usuario SIN la contraseña todavía
        usuario = Usuario.objects.create(
            id_rol_id=rol_id,
            nombre=request.POST.get('nombre'),
            apellido=request.POST.get('apellido', ''),
            ci=request.POST.get('ci', '') or None,
            usuario_login=usuario_login,
            telefono=request.POST.get('telefono', ''),
            activo=True,
        )
        
        # 2. Usamos el método set_password del modelo
        usuario.set_password(password_texto_plano)
        usuario.save()
        
        rol_nombre = usuario.id_rol.nombre if usuario.id_rol else 'Desconocido'
        registrar_auditoria(
            request, 
            'CREAR', 
            'USUARIOS', 
            f'Creó al usuario "{usuario_login}" con el rol de {rol_nombre}.'
        )
        
        messages.success(request, 'Usuario creado exitosamente')
        return redirect('lista_usuarios')
    
    roles = Rol.objects.all()
    return render(request, 'gestion_vehicular/admin/gestion_basica/usuarios_crear.html', {'roles': roles})


@login_required
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    
    if request.method == 'POST':
        usuario.nombre = request.POST.get('nombre')
        usuario.apellido = request.POST.get('apellido', '')
        usuario.ci = request.POST.get('ci', '') or None
        usuario.id_rol_id = request.POST.get('rol_id')
        usuario.telefono = request.POST.get('telefono', '')
        usuario.activo = request.POST.get('activo') == 'on'
        
        nueva_password = request.POST.get('password')
        if nueva_password:
            usuario.set_password(nueva_password) # Usamos el método de tu modelo
        
        usuario.save()
        
        detalle = f'Editó al usuario "{usuario.usuario_login}".'
        if nueva_password:
            detalle += ' (Se cambió la contraseña).'
            
        registrar_auditoria(
            request, 
            'EDITAR', 
            'USUARIOS', 
            detalle
        )
        
        messages.success(request, 'Usuario actualizado')
        return redirect('lista_usuarios')
    
    roles = Rol.objects.all()
    return render(request, 'gestion_vehicular/admin/gestion_basica/usuarios_editar.html', {'usuario': usuario, 'roles': roles})


#gmail
def enviar_enlace_usuario(request, usuario_id):
    """Genera un token y envía un correo con el enlace para restablecer contraseña"""
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    try:
        # 1. Generar token seguro
        token = default_token_generator.make_token(usuario)
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))

        # 2. Construir el enlace absoluto
        link = request.build_absolute_uri(
            reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        )

        # 3. Preparar mensaje
        asunto = "Recuperación de Contraseña - AUTODO"
        mensaje = (
            f"Hola {usuario.nombre_completo},\n\n"
            f"Recibimos una solicitud para restablecer tu contraseña en AUTODO.\n\n"
            f"Por favor, haz clic en el siguiente enlace para crear una nueva contraseña:\n\n"
            f"{link}\n\n"
            f"Si no solicitaste este cambio, puedes ignorar este correo.\n\n"
            f"Atentamente,\n"
            f"El equipo de DIAXO LT."
        )

        # 4. Enviar correo
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=None, # Usa el DEFAULT_FROM_EMAIL de settings
            recipient_list=[usuario.email],
            fail_silently=False,
        )
        
        messages.success(request, f'Enlace de recuperación enviado a {usuario.email}')
        
    except Exception as e:
        messages.error(request, f'Error al enviar el correo: {str(e)}')
        
    return redirect('lista_usuarios')


class CustomPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        """Sobrescribimos para buscar por 'activo' en lugar de 'is_active'"""
        active_users = Usuario.objects.filter(
            usuario_login__iexact=email,
            activo=True
        )
        return (u for u in active_users if u.has_usable_password())

    # 👇 AÑADE ESTE MÉTODO PARA FORZAR EL DOMINIO
    def save(self, domain_override=None, **kwargs):
        if not domain_override:
            domain_override = '127.0.0.1:8000'
        super().save(domain_override=domain_override, **kwargs)
        

class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = 'auth/password_reset.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'auth/password_reset_confirm.html'
    form_class = SetPasswordForm

    def form_valid(self, form):
        uidb64 = self.kwargs.get('uidb64')
        
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = Usuario.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, Usuario.DoesNotExist):
            user = None

        if user is not None:
            nueva_password = form.cleaned_data.get('new_password1')
            hash_nuevo = make_password(nueva_password)
            
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE usuario SET contrasena_hash = %s WHERE id = %s",
                    [hash_nuevo, user.id]
                )
                filas_afectadas = cursor.rowcount
            
            if filas_afectadas > 0:
                messages.success(self.request, ' ¡Contraseña cambiada exitosamente! ')
                return redirect('login')
            else:
                messages.error(self.request, 'No se pudo actualizar la contraseña.')
                return redirect('password_reset')
        else:
            messages.error(self.request, 'El enlace es inválido o ha expirado.')
            return redirect('password_reset')




