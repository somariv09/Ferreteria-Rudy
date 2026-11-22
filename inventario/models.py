from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone


class Categoria(models.Model):

    id_categoria = models.AutoField(primary_key=True)

    nombre = models.CharField(max_length=100, unique=True)

    descripcion = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='descripción'
    )

    imagen = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'categoria'
        managed = False

    def __str__(self):
        return self.nombre


class UnidadMedida(models.Model):

    id_unidad = models.AutoField(primary_key=True)

    nombre = models.CharField(
        max_length=50,
        unique=True
    )

    abreviatura = models.CharField(
        max_length=15,
        unique=True
    )

    tipo = models.CharField(max_length=20)

    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'unidad_medida'
        managed = False

    def __str__(self):
        return f"{self.nombre} ({self.abreviatura})"


class Producto(models.Model):

    id_producto = models.AutoField(primary_key=True)

    codigo_producto = models.CharField(
        max_length=20,
        unique=True
    )

    nombre = models.CharField(max_length=100)

    descripcion = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    cantidad = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('0')
    )

    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    stock_minimo = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal('0')
    )

    activo = models.BooleanField(default=True)

    imagen = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.DO_NOTHING,
        db_column='id_categoria',
        related_name='productos'
    )

    unidad_base = models.ForeignKey(
        UnidadMedida,
        on_delete=models.DO_NOTHING,
        db_column='id_unidad_base',
        related_name='productos_base'
    )

    class Meta:
        db_table = 'producto'
        managed = False

    def __str__(self):
        return self.nombre


class Movimiento(models.Model):

    ENTRADA = 'ENTRADA'
    SALIDA = 'SALIDA'

    TIPOS_MOVIMIENTO = [
        (ENTRADA, 'Entrada'),
        (SALIDA, 'Salida'),
    ]

    id_movimiento = models.AutoField(primary_key=True)

    codigo_movimiento = models.CharField(
        max_length=20,
        unique=True
    )

    tipo_movimiento = models.CharField(
        max_length=7,
        choices=TIPOS_MOVIMIENTO
    )

    cantidad = models.DecimalField(
        max_digits=18,
        decimal_places=8
    )

    fecha = models.DateTimeField(default=timezone.now)

    usuario = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.DO_NOTHING,
        db_column='id_usuario',
        related_name='movimientos'
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.DO_NOTHING,
        db_column='id_producto',
        related_name='movimientos'
    )

    unidad = models.ForeignKey(
        UnidadMedida,
        on_delete=models.DO_NOTHING,
        db_column='id_unidad',
        related_name='movimientos'
    )

    class Meta:
        db_table = 'movimiento'
        managed = False

    def __str__(self):
        return self.codigo_movimiento
