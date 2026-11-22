from django.urls import path
from . import views
from usuarios import views as usuarios_views

urlpatterns=[
    path('', views.dashboard, name='dashboard'),

    path('login/', usuarios_views.login, name='login'),
    path('logout/', usuarios_views.logout, name='logout'),
    # Verificación de identidad para reactivar registros
    path('verificar-reactivacion/', usuarios_views.login, {'modo': 'reactivacion'}, name='verificarReactivacion'),
    path('usuarios/', usuarios_views.catalogoUsuarios, name='catalogoUsuarios'),
    path('usuarios/agregar/', usuarios_views.agregarUsuario,name='agregarUsuario'),
    path('usuarios/editar/<int:id_usuario>/', usuarios_views.editarUsuario, name='editarUsuario'),
    path('usuarios/desactivar/<int:id_usuario>/',usuarios_views.desactivarUsuario,name='desactivarUsuario'),
    path('usuarios/activar/<int:id_usuario>/', usuarios_views.activarUsuario, name='activarUsuario'),

    path('productos/', views.catalogoProducto, name='catalogoProducto'),
    path('producto/agregar/', views.agregarProducto, name='agregarProducto'),
    path('producto/editar/<int:id_producto>/', views.editarProducto, name='editarProducto'),
    path('producto/eliminar/<int:id_producto>/', views.eliminarProducto, name='eliminarProducto'),

    path('categorias/', views.catalogoCategoria, name='catalogoCategoria'),
    path('categorias/agregar/', views.agregarCategoria, name='agregarCategoria'),
    path('categorias/editar/<int:id_categoria>/', views.editarCategoria, name='editarCategoria'),
    path('categorias/eliminar/<int:id_categoria>/', views.eliminarCategoria, name='eliminarCategoria'),

    path('historial/', views.historial, name='historial'),
    path('entrada/', views.registroEntrada, name='registroEntrada'),
    path('salida/', views.registroSalida, name='registroSalida'),
    path('movimiento/editar/<int:id_movimiento>/', views.editarMovimiento, name='editarMovimiento'),
    path('movimiento/eliminar/<int:id_movimiento>/', views.eliminarMovimiento, name='eliminarMovimiento'),

    path('registros-inactivos/', views.registrosInactivos,name='registrosInactivos'),
    path('reactivar-producto/<int:id_producto>/', views.reactivarProducto,name='reactivarProducto'),
    path('reactivar-categoria/<int:id_categoria>/',views.reactivarCategoria, name='reactivarCategoria'),

]