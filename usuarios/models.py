from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager


class UsuarioManager(BaseUserManager):

    def create_user(self, usuario, nombre, password=None, **extra_fields):

        if not usuario:
            raise ValueError('El usuario es obligatorio')

        user = self.model(
            usuario=usuario,
            nombre=nombre,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, usuario, nombre, password=None, **extra_fields):

        extra_fields.setdefault('rol', 'SUPERADMIN')
        extra_fields.setdefault('activo', True)

        if extra_fields.get('rol') != 'SUPERADMIN':
            raise ValueError('El superusuario debe tener rol SUPERADMIN')

        return self.create_user(
            usuario,
            nombre,
            password,
            **extra_fields
        )


class Usuario(AbstractBaseUser):

    SUPERADMIN = 'SUPERADMIN'
    ADMIN = 'ADMIN'
    USUARIO = 'USUARIO'

    ROLES = [
        (SUPERADMIN, 'Superadministrador'),
        (ADMIN, 'Administrador'),
        (USUARIO, 'Usuario'),
    ]

    id_usuario = models.AutoField(
        primary_key=True,
        db_column='id_usuario'
    )

    nombre = models.CharField(max_length=100)

    usuario = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True
    )

    password = models.CharField(
        max_length=255,
        db_column='contraseña'
    )

    rol = models.CharField(
        max_length=20,
        choices=ROLES,
        default=USUARIO
    )

    activo = models.BooleanField(default=True)

    # La tabla existente no tiene last_login.
    last_login = None

    objects = UsuarioManager()

    USERNAME_FIELD = 'usuario'
    REQUIRED_FIELDS = ['nombre']

    @property
    def is_active(self):
        return self.activo

    class Meta:
        db_table = 'usuario'
        managed = False

    def __str__(self):
        return f"{self.nombre} ({self.get_rol_display()})"
