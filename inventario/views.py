import os

from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash
)
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from django.conf import settings
from django.core.files.storage import default_storage

from django.db import transaction
from django.utils import timezone
import time
from django.db import models

from decimal import Decimal, InvalidOperation
from django.db.models import Q, F
from django.shortcuts import render, redirect, get_object_or_404 

from .models import Categoria, Producto, Movimiento
from usuarios.views import (tiene_autorizacion_reactivacion, roles_permitidos)

from usuarios.models import Usuario


@login_required
@roles_permitidos(Usuario.ADMIN, Usuario.USUARIO)
def dashboard(request):
    # Obtener productos activos
    productos = Producto.objects.filter(activo=True)

    # Contar productos registrados
    total_productos = productos.count()

    # Contar productos con alerta de stock
    alertas_stock = productos.filter(
        cantidad__lte=models.F('stock_minimo')
    ).count()

    # Obtener los últimos 4 movimientos
    movimientos_recientes = Movimiento.objects.order_by(
        '-fecha', '-pk'
    )[:4]

    contexto = {
        'total_productos': total_productos,
        'alertas_stock': alertas_stock,
        'movimientos_recientes': movimientos_recientes,
        'productos_inventario': productos,
    }

    return render(request, 'dashboard.html', contexto)

@login_required
@roles_permitidos(Usuario.ADMIN, Usuario.USUARIO)
def registroEntrada(request):
    error=None

    productos=Producto.objects.filter(activo=True).order_by("nombre")

    if request.method=="POST":
        productoID=request.POST.get('producto', '')
        cantidad=request.POST.get('cantidad', '')

        try:
            productoID= int(productoID)
            cantidad=int(cantidad)

            if cantidad<=0:
                error="El valor debe ser mayor a cero."
        except(ValueError, TypeError):
            error="Seleccione un producto e ingrese la cantidad"

        if not error:
            try:
                with transaction.atomic():
                    productos=Producto.objects.select_for_update().get(id_producto=productoID)

                    ultimoMovimiento=Movimiento.objects.filter(codigo_movimiento__startswith="MOV-").order_by('-id_movimiento').first()

                    if ultimoMovimiento:
                        #Separar el string en 2 y obtener la parte del numero
                        ultimoNumero=int(ultimoMovimiento.codigo_movimiento.rsplit('-',1)[1])
                    else:
                        ultimoNumero=0

                    codigo=f"MOV-{ultimoNumero+1:04d}"

                    productos.cantidad+=cantidad
                    productos.save(update_fields=['cantidad'])

                    Movimiento.objects.create(
                        codigo_movimiento=codigo,
                        tipo_movimiento=Movimiento.ENTRADA,
                        cantidad=cantidad,
                        fecha=timezone.now(),
                        usuario=request.user,
                        producto=productos
                    )
                return redirect('dashboard')
            except Producto.DoesNotExist:
                error="El producto no existe"
    return render(request, 'registroEntrada.html', {'error':error, 'productos':productos})

@login_required
@roles_permitidos(Usuario.ADMIN, Usuario.USUARIO)
def registroSalida(request):
    error=None
    
    productos=Producto.objects.filter(activo=True).order_by("nombre")
    
    if request.method=="POST":
        productoID=request.POST.get('producto', '')
        cantidad=request.POST.get('cantidad', '')

        try:
            productoID= int(productoID)
            cantidad=int(cantidad)

            if cantidad<=0:
                error="El valor debe ser mayor a cero."
        except(ValueError, TypeError):
            error="Seleccione un producto e ingrese la cantidad"

        if not error:
            try:
                with transaction.atomic():
                    productos=Producto.objects.select_for_update().get(id_producto=productoID)

                    ultimoMovimiento=Movimiento.objects.filter(codigo_movimiento__startswith="MOV-").order_by('-id_movimiento').first()

                    if ultimoMovimiento:
                        #Separar el string en 2 y obtener la parte del numero
                        ultimoNumero=int(ultimoMovimiento.codigo_movimiento.rsplit('-',1)[1])
                    else:
                        ultimoNumero=0

                    codigo=f"MOV-{ultimoNumero+1:04d}"

                    productos.cantidad-=cantidad
                    productos.save(update_fields=['cantidad'])

                    Movimiento.objects.create(
                        codigo_movimiento=codigo,
                        tipo_movimiento=Movimiento.SALIDA,
                        cantidad=cantidad,
                        fecha=timezone.now(),
                        usuario=request.user,
                        producto=productos
                    )
                return redirect('dashboard')
            except Producto.DoesNotExist:
                error="El producto no existe"
    return render(request, 'registroSalida.html', {'error':error, 'productos':productos})

@login_required
@roles_permitidos(Usuario.ADMIN, Usuario.USUARIO)
def historial(request):
    return render(request, 'historial.html')

@login_required
@roles_permitidos(Usuario.ADMIN)
def editarMovimiento(request):
    return render(request, 'editarMovimiento.html')

@require_POST
@roles_permitidos(Usuario.ADMIN)
def eliminarMovimiento(request, id_movimiento):
    return render(request, 'historial.html')

@login_required
@roles_permitidos(Usuario.ADMIN, Usuario.USUARIO)
def catalogoProducto(request):
    buscar = request.GET.get('buscar', '').strip()
    disponibilidad = request.GET.get('disponibilidad', 'todos')

    productos = Producto.objects.filter(activo=True).order_by('nombre')

    if buscar:
        productos = productos.filter(
            Q(nombre__icontains=buscar) |
            Q(codigo_producto__icontains=buscar)
        )

    if disponibilidad == 'suficiente':
        productos = productos.filter(cantidad__gt=F('stock_minimo'))

    elif disponibilidad == 'bajo':
        productos = productos.filter(cantidad__lte=F('stock_minimo'))

    for producto in productos:
        producto.imagen_url = (
            default_storage.url(producto.imagen)
            if producto.imagen else None
        )

    return render(request, 'catalogoProducto.html', {
        'productos': productos,
        'filtros': {
            'buscar': buscar,
            'disponibilidad': disponibilidad
        }
    })

@login_required
@roles_permitidos(Usuario.ADMIN)
def agregarProducto(request):
    error= None

    categorias= Categoria.objects.filter(activo=True).order_by("nombre")

    if request.method=="POST":
        imagen=request.FILES.get('imagen')
        codigo=request.POST.get('codigo','').strip().upper()
        nombre=request.POST.get('nombre','').strip().upper()
        #Recibe el valor numerico del id
        categoria=request.POST.get('categoria','')
        descripcion=request.POST.get('descripcion','').strip()
        cantidad=request.POST.get('cantidad','')
        precio=request.POST.get('precio','')
        stockMinimo=request.POST.get('stockMinimo','')

        ruta_imagen=None
    
        if not codigo or not nombre or not categoria:
            error="Debe ingresar los campos de código, nombre y categoria."
    
        elif not cantidad or not precio or not stockMinimo:
            error="Ingrese los campos de cantidad, precio y stock mínimo"
    
        elif Producto.objects.filter(nombre=nombre).exists():
            error="El producto ya existe"
    
        else:
            try:
                cantidad=int(cantidad)
                precio=Decimal(precio)
                stockMinimo=int(stockMinimo)
    
                if cantidad < 0 or precio < 0:
                    error="Cantidad y precio no puede ser menor a 0"
    
                elif stockMinimo < 5:
                    error="El stock minimo debe ser mayor o igual a cinco"

            except(ValueError, InvalidOperation):
                error= "La cantidad, precio o stock minimo no tiene un formato válido"
    
            if not error and imagen:

                if os.path.splitext(imagen.name)[1].lower() not in ['.jpg', '.jpeg', '.png']:
                    error = "La imagen debe ser JPG, JPEG, PNG"

                elif imagen.size > 2*1024*1024:
                    error = "La imagen supera los 2MB"

                else:
                    nombre_archivo = os.path.basename(imagen.name)

                    ruta_imagen = default_storage.save(
                        f'productos/{nombre_archivo}',
                        imagen
                    )
        
        if not error:
            Producto.objects.create(
                imagen=ruta_imagen,
                codigo_producto=codigo,
                nombre=nombre,
                categoria_id=categoria,
                descripcion=descripcion,
                cantidad=cantidad,
                precio_unitario=precio,
                stock_minimo=stockMinimo       
            )
            return redirect('catalogoProducto')
    return render(request, 'agregarProducto.html', {'error':error, "categorias":categorias})

@login_required
@roles_permitidos(Usuario.ADMIN)
def editarProducto(request, id_producto):

    producto = get_object_or_404(Producto, id_producto=id_producto)
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    error = None

    if request.method == "POST":

        imagen = request.FILES.get('imagen')
        codigo = request.POST.get('codigo', '').strip().upper()
        nombre = request.POST.get('nombre', '').strip().upper()
        categoria_id = request.POST.get('categoria', '')
        descripcion = request.POST.get('descripcion', '').strip()
        precio = request.POST.get('precio', '')
        stockMinimo = request.POST.get('stockMinimo', '')

        if not codigo or not nombre or not categoria_id:
            error = "Debe ingresar los campos de código, nombre y categoria."

        elif not precio or not stockMinimo:
            error = "Ingrese los campos de cantidad, precio y stock mínimo"

        elif Producto.objects.filter(
            nombre=nombre
        ).exclude(id_producto=id_producto).exists():
            error = "Esta categoria ya existe."

        elif imagen and os.path.splitext(imagen.name)[1].lower() not in ['.jpg', '.jpeg', '.png']:
            error = "La imagen debe ser JPG, JPEG, PNG"

        elif imagen and imagen.size > 2*1024*1024:
            error = "La imagen supera los 2MB"

        else:
            categoria = get_object_or_404(
                Categoria,
                id_categoria=categoria_id
            )

            producto.codigo_producto = codigo
            producto.nombre = nombre
            producto.categoria = categoria
            producto.descripcion = descripcion
            producto.precio_unitario = precio
            producto.stock_minimo = stockMinimo

            if imagen:
                nombre_archivo = os.path.basename(imagen.name)

                ruta_imagen = default_storage.save(
                    f'productos/{nombre_archivo}',
                    imagen
                )

                producto.imagen = ruta_imagen

            producto.save()
            return redirect('catalogoProducto')

    producto.imagen_url = (
        default_storage.url(producto.imagen)
        if producto.imagen else None
    )

    return render(request, 'editarProducto.html', {
        'producto': producto,
        'error': error,
        'categorias': categorias
    })

@login_required
@require_POST
@roles_permitidos(Usuario.ADMIN)
def eliminarProducto(request, id_producto):
    producto = get_object_or_404(Producto, id_producto=id_producto)

    producto.activo = False
    producto.save(update_fields=['activo'])

    return redirect("catalogoProducto")

@login_required
@roles_permitidos(Usuario.ADMIN, Usuario.USUARIO)
def catalogoCategoria(request):
    buscar = request.GET.get('buscar', '').strip()

    categorias = Categoria.objects.filter(activo=True).order_by('nombre')

    if buscar:
        categorias = categorias.filter(nombre__icontains=buscar)

    for categoria in categorias:
        categoria.imagen_url = (
            default_storage.url(categoria.imagen)
            if categoria.imagen else None
        )

    return render(request, 'catalogoCategoria.html', {
        'categorias': categorias,
        'filtros': {'buscar': buscar}
    })

@login_required
@roles_permitidos(Usuario.ADMIN)
def agregarCategoria(request):
    error=None

    if request.method == "POST":
        nombre=request.POST.get('nombre', '').strip().upper()
        descripcion=request.POST.get('descripcion', '').strip()
        imagen=request.FILES.get('imagen')

        if not nombre:
            error="Ingrese el nombre de la categoria"

        elif Categoria.objects.filter(nombre=nombre).exists():
            error="Esta categoria ya existe."

        elif imagen and os.path.splitext(imagen.name)[1].lower() not in ['.jpg', '.jpeg', '.png']:
            error = "La imagen debe ser JPG, JPEG, PNG"

        elif imagen and imagen.size >2*1024*1024:
            error="La imagen supera los 2MB"
    
        else:
            ruta_imagen= None

            if imagen:
                nombre_archivo = os.path.basename(imagen.name)
                ruta_imagen = default_storage.save(
                    f'categorias/{nombre_archivo}',
                    imagen
                )

        if not error:
            Categoria.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                imagen=ruta_imagen
            )
            return redirect('catalogoCategoria')

    return render(request, 'agregarCategoria.html', {'error':error})

@login_required
@roles_permitidos(Usuario.ADMIN)
def editarCategoria(request, id_categoria):

    categoria = get_object_or_404(Categoria, id_categoria=id_categoria)
    error = None

    if request.method == "POST":

        nombre = request.POST.get('nombre', '').strip().upper()
        descripcion = request.POST.get('descripcion', '').strip()
        imagen = request.FILES.get('imagen')

        if not nombre:
            error = "Ingrese el nombre de la categoria"

        elif Categoria.objects.filter(
            nombre=nombre
        ).exclude(id_categoria=id_categoria).exists():
            error = "Esta categoria ya existe."

        elif imagen and os.path.splitext(imagen.name)[1].lower() not in ['.jpg', '.jpeg', '.png']:
            error = "La imagen debe ser JPG, JPEG, PNG"

        elif imagen and imagen.size > 2*1024*1024:
            error = "La imagen supera los 2MB"

        else:
            categoria.nombre = nombre
            categoria.descripcion = descripcion

            if imagen:
                nombre_archivo = os.path.basename(imagen.name)

                ruta_imagen = default_storage.save(
                    f'categorias/{nombre_archivo}',
                    imagen
                )

                categoria.imagen = ruta_imagen

            categoria.save()
            return redirect('catalogoCategoria')

    categoria.imagen_url = (
        default_storage.url(categoria.imagen)
        if categoria.imagen else None
    )

    return render(request, 'editarCategoria.html', {
        'categoria': categoria,
        'error': error
    })

@login_required
@require_POST
@roles_permitidos(Usuario.ADMIN)
def eliminarCategoria(request, id_categoria):
    categoria = get_object_or_404(Categoria, id_categoria=id_categoria)
    categoria.activo = False
    categoria.save(update_fields=['activo'])

    return redirect('catalogoCategoria')

@login_required
@roles_permitidos(Usuario.ADMIN)
def registrosInactivos(request):

    if not tiene_autorizacion_reactivacion(request):
        return redirect('verificarReactivacion')

    productos = Producto.objects.filter(activo=False).select_related('categoria').order_by('nombre')

    categorias = Categoria.objects.filter(activo=False).order_by('nombre')

    return render(request, 'registrosInactivos.html', {
        'productos': productos,
        'categorias': categorias
    })

@login_required
@require_POST
@roles_permitidos(Usuario.ADMIN)
def reactivarProducto(request, id_producto):

    if not tiene_autorizacion_reactivacion(request):
        return redirect('verificarReactivacion')

    producto = get_object_or_404(Producto, id_producto=id_producto,activo=False)

    producto.activo = True
    producto.save(update_fields=['activo'])

    return redirect('registrosInactivos')

@login_required
@require_POST
@roles_permitidos(Usuario.ADMIN)
def reactivarCategoria(request, id_categoria):

    if not tiene_autorizacion_reactivacion(request):
        return redirect('verificarReactivacion')

    categoria = get_object_or_404(Categoria,id_categoria=id_categoria,activo=False)

    categoria.activo = True
    categoria.save(update_fields=['activo'])

    return redirect('registrosInactivos')

