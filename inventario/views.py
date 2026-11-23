import os

from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
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

from .models import Categoria, Producto, Movimiento, UnidadMedida
from usuarios.views import (tiene_autorizacion_reactivacion, roles_permitidos)

from usuarios.models import Usuario

TIPOS_UNIDAD = [
    ('Conteo', 'Conteo'),
    ('Presentación', 'Presentación'),
    ('Peso', 'Peso'),
    ('Longitud', 'Longitud'),
    ('Volumen', 'Volumen'),
]


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
                    producto = Producto.objects.select_for_update().get(
                        id_producto=productoID,
                        activo=True
                    )

                    ultimoMovimiento=Movimiento.objects.filter(codigo_movimiento__startswith="MOV-").order_by('-id_movimiento').first()

                    if ultimoMovimiento:
                        #Separar el string en 2 y obtener la parte del numero
                        ultimoNumero=int(ultimoMovimiento.codigo_movimiento.rsplit('-',1)[1])
                    else:
                        ultimoNumero=0

                    codigo=f"MOV-{ultimoNumero+1:04d}"

                    producto.cantidad+=cantidad
                    producto.save(update_fields=['cantidad'])

                    Movimiento.objects.create(
                        codigo_movimiento=codigo,
                        tipo_movimiento=Movimiento.ENTRADA,
                        cantidad=cantidad,
                        fecha=timezone.now(),
                        usuario=request.user,
                        producto=producto,
                        unidad=producto.unidad_base
                    )
                return redirect('dashboard')
            except Producto.DoesNotExist:
                error="El producto no existe"
    return render(request, 'registroEntrada.html', {'error':error, 'productos':productos})


@login_required
@roles_permitidos(Usuario.ADMIN, Usuario.USUARIO)
def registroSalida(request):
    error = None

    productos = Producto.objects.filter(activo=True).order_by("nombre")

    if request.method == "POST":
        productoID = request.POST.get('producto', '')
        cantidad = request.POST.get('cantidad', '')

        try:
            productoID = int(productoID)
            cantidad = int(cantidad)

            if cantidad <= 0:
                error = "El valor debe ser mayor a cero."

        except (ValueError, TypeError):
            error = "Seleccione un producto e ingrese una cantidad válida."

        if not error:
            try:
                with transaction.atomic():
                    producto = Producto.objects.select_for_update().get(
                        id_producto=productoID,
                        activo=True
                    )

                    # Validar existencias disponibles
                    if cantidad > producto.cantidad:
                        error = (
                            f"No hay existencias suficientes. "
                        )
                    else:
                        ultimoMovimiento = (
                            Movimiento.objects
                            .filter(codigo_movimiento__startswith="MOV-")
                            .order_by('-id_movimiento')
                            .first()
                        )

                        if ultimoMovimiento:
                            ultimoNumero = int(
                                ultimoMovimiento.codigo_movimiento.rsplit('-', 1)[1]
                            )
                        else:
                            ultimoNumero = 0

                        codigo = f"MOV-{ultimoNumero + 1:04d}"

                        producto.cantidad -= cantidad
                        producto.save(update_fields=['cantidad'])

                        Movimiento.objects.create(
                            codigo_movimiento=codigo,
                            tipo_movimiento=Movimiento.SALIDA,
                            cantidad=cantidad,
                            fecha=timezone.now(),
                            usuario=request.user,
                            producto=producto,
                            unidad=producto.unidad_base
                        )

                if not error:
                    return redirect('dashboard')

            except Producto.DoesNotExist:
                error = "El producto no existe."

    return render(
        request,
        'registroSalida.html',
        {'error': error, 'productos': productos}
    )


@login_required
@roles_permitidos(Usuario.ADMIN, Usuario.USUARIO)
def historial(request):
    movimientos = Movimiento.objects.select_related(
        'producto', 'usuario', 'unidad'
    ).order_by('-fecha', '-id_movimiento')

    buscar = request.GET.get('buscar', '').strip()
    tipo = request.GET.get('tipo', 'todos')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')

    if buscar:
        movimientos = movimientos.filter(
            Q(producto__nombre__icontains=buscar) |
            Q(producto__codigo_producto__icontains=buscar)
        )

    if tipo in ['ENTRADA', 'SALIDA']:
        movimientos = movimientos.filter(
            tipo_movimiento=tipo
        )

    from django.utils.dateparse import parse_date

    fecha_desde = parse_date(desde) if desde else None
    fecha_hasta = parse_date(hasta) if hasta else None

    if fecha_desde:
        movimientos = movimientos.filter(
            fecha__date__gte=fecha_desde
        )

    if fecha_hasta:
        movimientos = movimientos.filter(
            fecha__date__lte=fecha_hasta
        )

    contexto = {
        'movimientos': movimientos,
        'filtros': {
            'buscar': buscar,
            'tipo': tipo,
            'desde': desde,
            'hasta': hasta,
        }
    }

    return render(request, 'historial.html', contexto)


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

    error = None

    categorias = Categoria.objects.filter(
        activo=True
    ).order_by("nombre")

    unidades = UnidadMedida.objects.filter(
        activo=True
    ).order_by("nombre")

    if request.method == "POST":

        imagen = request.FILES.get('imagen')
        codigo = request.POST.get('codigo', '').strip().upper()
        nombre = request.POST.get('nombre', '').strip().upper()
        categoria_id = request.POST.get('categoria', '')
        unidad_base_id = request.POST.get('unidad_base', '')
        descripcion = request.POST.get('descripcion', '').strip()
        cantidad = request.POST.get('cantidad', '')
        precio = request.POST.get('precio', '')
        stockMinimo = request.POST.get('stockMinimo', '')

        ruta_imagen = None

        categoria = None
        unidad_base = None

        if not codigo or not nombre or not categoria_id or not unidad_base_id:
            error = "Debe completar el código, nombre, categoría y unidad base."

        elif not cantidad or not precio or not stockMinimo:
            error = "Ingrese la cantidad, precio y stock mínimo."

        elif Producto.objects.filter(codigo_producto=codigo).exists():
            error = "Ya existe un producto con ese código."

        elif Producto.objects.filter(nombre=nombre).exists():
            error = "El producto ya existe."

        else:
            try:
                cantidad = Decimal(cantidad)
                precio = Decimal(precio)
                stockMinimo = Decimal(stockMinimo)

                if not all(valor.is_finite() for valor in (cantidad, precio, stockMinimo)):
                    error = "Los valores numéricos deben ser válidos."

                elif cantidad != cantidad.to_integral_value():
                    error = "La cantidad debe ser un número entero."

                elif stockMinimo != stockMinimo.to_integral_value():
                    error = "El stock mínimo debe ser un número entero."

                elif cantidad < 0 or precio < 0:
                    error = "La cantidad y el precio no pueden ser menores a cero."

                elif stockMinimo < 3:
                    error = "El stock mínimo debe ser mayor o igual a tres."

            except (ValueError, InvalidOperation):
                error = "La cantidad, precio o stock mínimo tiene un formato no válido."

            # Validar categoría y unidad base.
            if not error:

                try:
                    categoria_id = int(categoria_id)
                    unidad_base_id = int(unidad_base_id)

                    categoria = Categoria.objects.filter(
                        id_categoria=categoria_id,
                        activo=True
                    ).first()

                    unidad_base = UnidadMedida.objects.filter(
                        id_unidad=unidad_base_id,
                        activo=True
                    ).first()

                    if not categoria:
                        error = "La categoría seleccionada no existe o está inactiva."

                    elif not unidad_base:
                        error = "La unidad seleccionada no existe o está inactiva."

                except (ValueError, TypeError):
                    error = "La categoría o unidad seleccionada no es válida."

            # Validar imagen.
            if not error and imagen:

                if os.path.splitext(imagen.name)[1].lower() not in ['.jpg', '.jpeg', '.png']:
                    error = "La imagen debe ser JPG, JPEG o PNG."

                elif imagen.size > 2 * 1024 * 1024:
                    error = "La imagen supera los 2MB."

                else:
                    nombre_archivo = os.path.basename(imagen.name)

                    ruta_imagen = default_storage.save(
                        f'productos/{nombre_archivo}',
                        imagen
                    )

            # Registrar producto y conversión base.
            if not error:

                try:
                    with transaction.atomic():

                        producto = Producto.objects.create(
                            imagen=ruta_imagen,
                            codigo_producto=codigo,
                            nombre=nombre,
                            categoria=categoria,
                            unidad_base=unidad_base,
                            descripcion=descripcion,
                            cantidad=cantidad,
                            precio_unitario=precio,
                            stock_minimo=stockMinimo
                        )

                    return redirect('catalogoProducto')

                except Exception:
                    error = (
                        "No se pudo registrar el producto. "
                        "Verifique los datos e inténtelo nuevamente."
                    )

    return render(request, 'agregarProducto.html', {
        'error': error,
        'categorias': categorias,
        'unidades': unidades
    })


@login_required
@roles_permitidos(Usuario.ADMIN)
def editarProducto(request, id_producto):

    producto = get_object_or_404(Producto, id_producto=id_producto)

    categorias = Categoria.objects.filter(
        activo=True
    ).order_by('nombre')

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
            error = "Debe ingresar el código, nombre y categoría."

        elif not precio or not stockMinimo:
            error = "Ingrese el precio y el stock mínimo."

        elif Producto.objects.filter(
            codigo_producto=codigo
        ).exclude(id_producto=id_producto).exists():
            error = "Ya existe un producto con ese código."

        elif Producto.objects.filter(
            nombre=nombre
        ).exclude(id_producto=id_producto).exists():
            error = "Ya existe un producto con ese nombre."

        else:

            try:
                precio = Decimal(precio)
                stockMinimo = Decimal(stockMinimo)

                if not precio.is_finite() or not stockMinimo.is_finite():
                    error = "Los valores numéricos deben ser válidos."

                elif precio < 0:
                    error = "El precio no puede ser menor a cero."

                elif stockMinimo < 3:
                    error = "El stock mínimo debe ser mayor o igual a tres."

            except (ValueError, InvalidOperation):
                error = "El precio o stock mínimo tiene un formato no válido."

            # Validar categoría.
            if not error:

                categoria = Categoria.objects.filter(
                    id_categoria=categoria_id,
                    activo=True
                ).first()

                if not categoria:
                    error = "La categoría seleccionada no existe o está inactiva."

            # Validar imagen.
            if not error and imagen:

                if os.path.splitext(imagen.name)[1].lower() not in [
                    '.jpg', '.jpeg', '.png'
                ]:
                    error = "La imagen debe ser JPG, JPEG o PNG."

                elif imagen.size > 2 * 1024 * 1024:
                    error = "La imagen supera los 2MB."

            # Actualizar producto.
            if not error:

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

@login_required
@roles_permitidos(Usuario.ADMIN)
def catalogoUnidades(request):

    unidades = UnidadMedida.objects.filter(
        activo=True
    ).order_by('nombre')

    return render(request, 'catalogoUnidades.html', {
        'unidades': unidades,
    })


@login_required
@roles_permitidos(Usuario.ADMIN)
def agregarUnidad(request):

    error = None

    if request.method == 'POST':

        nombre = request.POST.get('nombre', '').strip().upper()
        abreviatura = request.POST.get('abreviatura', '').strip().upper()
        tipo = request.POST.get('tipo', '').strip().upper()

        if not nombre or not abreviatura or not tipo:
            error = "Debe completar todos los campos."

        elif UnidadMedida.objects.filter(nombre__iexact=nombre).exists():
            error = "Ya existe una unidad con ese nombre."

        elif UnidadMedida.objects.filter(abreviatura__iexact=abreviatura).exists():
            error = "Ya existe una unidad con esa abreviatura."

        else:
            UnidadMedida.objects.create(
                nombre=nombre,
                abreviatura=abreviatura,
                tipo=tipo
            )

            return redirect('catalogoUnidades')

    return render(request, 'agregarUnidad.html', {
        'error': error,
        'tipos_unidad': TIPOS_UNIDAD
    })

@login_required
@roles_permitidos(Usuario.ADMIN)
def editarUnidad(request, id_unidad):

    unidad = get_object_or_404(
        UnidadMedida,
        id_unidad=id_unidad
    )

    error = None

    # Comprobar si la unidad está relacionada.
    unidad_en_uso = (
        unidad.productos_base.exists() or
        unidad.movimientos.exists()
    )

    if request.method == 'POST':

        nombre = request.POST.get(
            'nombre', ''
        ).strip().upper()

        abreviatura = request.POST.get(
            'abreviatura', ''
        ).strip().upper()

        if not nombre or not abreviatura:
            error = "Debe completar el nombre y la abreviatura."

        elif UnidadMedida.objects.filter(
            nombre__iexact=nombre
        ).exclude(id_unidad=id_unidad).exists():
            error = "Ya existe una unidad con ese nombre."

        elif UnidadMedida.objects.filter(
            abreviatura__iexact=abreviatura
        ).exclude(id_unidad=id_unidad).exists():
            error = "Ya existe una unidad con esa abreviatura."

        else:

            # El tipo solamente se puede modificar si
            # la unidad no tiene relaciones.
            if not unidad_en_uso:

                tipo = request.POST.get(
                    'tipo', ''
                ).strip().upper()

                tipos_validos = dict(TIPOS_UNIDAD)

                if tipo not in tipos_validos:
                    error = "El tipo de unidad seleccionado no es válido."

                else:
                    unidad.tipo = tipo

            if not error:

                unidad.nombre = nombre
                unidad.abreviatura = abreviatura

                unidad.save()

                return redirect('catalogoUnidades')

    return render(request, 'editarUnidad.html', {
        'unidad': unidad,
        'error': error,
        'tipos_unidad': TIPOS_UNIDAD,
        'unidad_en_uso': unidad_en_uso
    })
