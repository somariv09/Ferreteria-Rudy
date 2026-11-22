import time

from django.shortcuts import render, redirect
from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
)
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from functools import wraps
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

from .models import Usuario

from django.contrib import messages
from django.views.decorators.http import require_POST

#request solicitud del navegador
def login(request, modo='normal'):

    # Si se intenta verificar identidad sin haber iniciado sesión,
    # primero debe realizarse el inicio de sesión normal.
    if modo == 'reactivacion' and not request.user.is_authenticated:
        return redirect('login')

    # En el inicio de sesión normal no hace falta mostrar el formulario
    # si ya existe una sesión.
    if modo == 'normal' and request.user.is_authenticated:

        if request.user.rol == Usuario.SUPERADMIN:
            return redirect('catalogoUsuarios')

        return redirect('dashboard')

    error = None

    if request.method == 'POST':

        usuario = request.POST.get('usuario', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(
            request,
            username=usuario,
            password=password
        )

        if modo == 'reactivacion':

            # Comprobar que las credenciales pertenecen al usuario
            # que ya tiene iniciada la sesión.
            if user is not None and user.pk == request.user.pk:

                # Autorizar reactivaciones durante cinco minutos.
                request.session['reactivacion_autorizada_hasta'] = (int(time.time()) + 300)

                return redirect('registrosInactivos')

            error = "LAS CREDENCIALES NO CORRESPONDEN AL USUARIO ACTUAL"

        else:

            if user is not None:
                auth_login(request, user)

                if user.rol == Usuario.SUPERADMIN:
                    return redirect('catalogoUsuarios')

                return redirect('dashboard')

            error = "USUARIO O CONTRASEÑA INCORRECTOS"

    return render(request, 'login.html', {'error': error,'modo': modo })

def tiene_autorizacion_reactivacion(request):

    tiempo_limite = request.session.get('reactivacion_autorizada_hasta')

    if tiempo_limite is None:
        return False

    if int(time.time()) > tiempo_limite:
        request.session.pop('reactivacion_autorizada_hasta', None)
        return False

    return True

#Requiere el envio de una solicitud
@require_POST
def logout(request):
    #Meotod de django que cierra la sesion
    auth_logout(request)
    return redirect('login')

def roles_permitidos(*roles):

    def decorador(vista):

        @wraps(vista)
        def funcion(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect('login')

            if request.user.rol not in roles:
                if request.user.rol == Usuario.SUPERADMIN:
                    return redirect('catalogoUsuarios')

                return redirect('dashboard')

            return vista(request, *args, **kwargs)

        return funcion

    return decorador

@login_required
@roles_permitidos(Usuario.SUPERADMIN)
def catalogoUsuarios(request):

    # Solo el SUPERADMIN puede gestionar usuarios.
    if request.user.rol != Usuario.SUPERADMIN:
        return redirect('dashboard')

    usuarios = Usuario.objects.all().order_by('nombre')

    return render(request, 'catalogoUsuarios.html', {
        'usuarios': usuarios
    })

@login_required
@roles_permitidos(Usuario.SUPERADMIN)
def agregarUsuario(request):

    error = None

    if request.method == 'POST':

        nombre = request.POST.get('nombre', '').strip()
        usuario = request.POST.get('usuario', '').strip()
        password = request.POST.get('password', '')
        confirmar_password = request.POST.get('confirmar_password', '')
        rol = request.POST.get('rol', '')

        # Validar campos obligatorios.
        if not nombre or not usuario or not password or not confirmar_password or not rol:
            error = 'Todos los campos son obligatorios.'

        # Validar que el rol exista.
        elif rol not in dict(Usuario.ROLES):
            error = 'El rol seleccionado no es válido.'

        # Evitar nombres de usuario duplicados.
        elif Usuario.objects.filter(usuario=usuario).exists():
            error = 'Ese nombre de usuario ya está registrado.'

        # Comprobar que ambas contraseñas coincidan.
        elif password != confirmar_password:
            error = 'Las contraseñas no coinciden.'

        else:
            try:
                validate_password(password)

                Usuario.objects.create_user(
                    usuario=usuario,
                    nombre=nombre,
                    password=password,
                    rol=rol,
                    activo=True
                )

                return redirect('catalogoUsuarios')

            except ValidationError as e:
                mensajes = {
                    'password_too_short': 'La contraseña debe tener al menos 8 caracteres.',
                    'password_too_common': 'La contraseña es demasiado común. Elige una más segura.',
                    'password_entirely_numeric': 'La contraseña no puede estar formada únicamente por números.',
                    'password_too_similar': 'La contraseña es demasiado parecida a los datos del usuario.'
                }

                error = ' '.join([
                    mensajes.get(error.code, error.message)
                    for error in e.error_list
                ])

    return render(request, 'agregarUsuario.html', {
        'error': error,
        'roles': Usuario.ROLES,
        'titulo': 'Agregar usuario',
        'accion': 'Registrar'
    })

@login_required
@roles_permitidos(Usuario.SUPERADMIN)
def editarUsuario(request, id_usuario):

    usuario_editar = Usuario.objects.filter(
        id_usuario=id_usuario
    ).first()

    if usuario_editar is None:
        return redirect('catalogoUsuarios')

    # Impedir que el SUPERADMIN edite su propia cuenta.
    if usuario_editar.id_usuario == request.user.id_usuario:
        return redirect('catalogoUsuarios')

    error = None

    if request.method == 'POST':

        nombre = request.POST.get('nombre', '').strip()
        nombre_usuario = request.POST.get('usuario', '').strip()
        rol = request.POST.get('rol', '')
        password = request.POST.get('password', '')

        if not nombre or not nombre_usuario or not rol:
            error = 'Nombre, usuario y rol son obligatorios.'

        elif rol not in dict(Usuario.ROLES):
            error = 'El rol seleccionado no es válido.'

        elif Usuario.objects.filter(
            usuario=nombre_usuario
        ).exclude(id_usuario=id_usuario).exists():
            error = 'Ese nombre de usuario ya está registrado.'

        else:

            if password:
                try:
                    validate_password(password, usuario_editar)
                except ValidationError as e:
                    mensajes = {
                        'password_too_short': 'La contraseña debe tener al menos 8 caracteres.',
                        'password_too_common': 'La contraseña es demasiado común. Elige una más segura.',
                        'password_entirely_numeric': 'La contraseña no puede estar formada únicamente por números.',
                        'password_too_similar': 'La contraseña es demasiado parecida a los datos del usuario.'
                    }

                    error = ' '.join([
                        mensajes.get(error.code, error.message)
                        for error in e.error_list
                    ])

            if error is None:

                usuario_editar.nombre = nombre
                usuario_editar.usuario = nombre_usuario
                usuario_editar.rol = rol

                # Solo cambia la contraseña si se escribió una nueva.
                if password:
                    usuario_editar.set_password(password)

                usuario_editar.save()

                return redirect('catalogoUsuarios')

    return render(request, 'editarUsuario.html', {
        'error': error,
        'roles': Usuario.ROLES,
        'usuario_editar': usuario_editar
    })

@login_required
@roles_permitidos(Usuario.SUPERADMIN)
@require_POST
def activarUsuario(request, id_usuario):

    usuario_activar = Usuario.objects.filter(
        id_usuario=id_usuario
    ).first()

    if usuario_activar is None:
        messages.error(request, 'El usuario no existe.')

    elif usuario_activar.activo:
        messages.warning(request, 'Esta cuenta ya está activa.')

    else:
        usuario_activar.activo = True
        usuario_activar.save(update_fields=['activo'])

    return redirect('catalogoUsuarios')

@login_required
@roles_permitidos(Usuario.SUPERADMIN)
@require_POST
def desactivarUsuario(request, id_usuario):

    usuario_desactivar = Usuario.objects.filter(
        id_usuario=id_usuario
    ).first()

    if usuario_desactivar is None:

        messages.error(request, 'El usuario no existe.')

    elif usuario_desactivar.id_usuario == request.user.id_usuario:

        messages.error(
            request,
            'No puedes desactivar tu propia cuenta.'
        )

    elif not usuario_desactivar.activo:

        messages.warning(
            request,
            'Esta cuenta ya está desactivada.'
        )

    elif usuario_desactivar.rol == Usuario.SUPERADMIN and Usuario.objects.filter(
        rol=Usuario.SUPERADMIN,
        activo=True
    ).count() <= 1:

        messages.error(
            request,
            'No puedes desactivar al último SUPERADMIN activo.'
        )

    else:

        usuario_desactivar.activo = False

        usuario_desactivar.save(
            update_fields=['activo']
        )

    return redirect('catalogoUsuarios')
