#@author:  Tomas Jonatan Lopez Cruz
#@email:   20461973hola@gmail.com
#@date:    2026-10-13
#@version: 0.0.1
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from ..models import Usuario, Rol
from .gestion_administrativa import registrar_auditoria  # 🆕 Importamos la función de auditoría


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        usuario = authenticate(request, username=username, password=password)
        
        if usuario is not None:
            auth_login(request, usuario)
            
            # 🆕 REGISTRAR AUDITORÍA
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
    # 🆕 REGISTRAR AUDITORÍA ANTES DE CERRAR SESIÓN
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


@login_required # 🆕 Agregué login_required para seguridad
def lista_usuarios(request):
    usuarios = Usuario.objects.select_related('id_rol').all().order_by('nombre')
    return render(request, 'gestion_vehicular/admin/gestion_basica/usuarios_lista.html', {'usuarios': usuarios})


@login_required # 🆕 Agregué login_required para seguridad
def crear_usuario(request):
    if request.method == 'POST':
        from django.contrib.auth.hashers import make_password
        
        rol_id = request.POST.get('rol_id')
        usuario_login = request.POST.get('usuario_login')
        
        usuario = Usuario.objects.create(
            id_rol_id=rol_id,
            nombre=request.POST.get('nombre'),
            apellido=request.POST.get('apellido', ''),
            usuario_login=usuario_login,
            contrasena_hash=make_password(request.POST.get('password')),
            telefono=request.POST.get('telefono', ''),
            activo=True,
        )
        
        # 🆕 REGISTRAR AUDITORÍA
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


@login_required # 🆕 Agregué login_required para seguridad
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    
    if request.method == 'POST':
        usuario.nombre = request.POST.get('nombre')
        usuario.apellido = request.POST.get('apellido', '')
        usuario.id_rol_id = request.POST.get('rol_id')
        usuario.telefono = request.POST.get('telefono', '')
        usuario.activo = request.POST.get('activo') == 'on'
        
        nueva_password = request.POST.get('password')
        if nueva_password:
            from django.contrib.auth.hashers import make_password
            usuario.contrasena_hash = make_password(nueva_password)
        
        usuario.save()
        
        # 🆕 REGISTRAR AUDITORÍA
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