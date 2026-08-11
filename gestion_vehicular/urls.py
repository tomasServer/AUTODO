from django.urls import path
from .views import gestion_basica, gestion_taller, seguimiento_vehicular, gestion_administrativa
#dashboard_views

urlpatterns = [

    #fecha: 30/may/2026
    # primer incremeto 
    path('login/', gestion_basica.login_view, name='login'),
    path('logout/', gestion_basica.logout_view, name='logout'),
    path('', gestion_basica.dashboard, name='dashboard'),
    path('usuarios/', gestion_basica.lista_usuarios, name='lista_usuarios'),
    path('usuarios/crear/', gestion_basica.crear_usuario, name='crear_usuario'),
    path('usuarios/<int:usuario_id>/editar/', gestion_basica.editar_usuario, name='editar_usuario'),

    #fecha 15 de junio de 2026
    # segun incremente
    path('orden/crear/', gestion_taller.crear_orden, name='crear_orden'),
    path('orden/<int:orden_id>/', gestion_taller.detalle_orden, name='detalle_orden'),
    path('orden/<int:orden_id>/agregar-servicio/', gestion_taller.agregar_servicio_orden, name='agregar_servicio_orden'),
    path('orden/<int:orden_id>/agregar-producto/', gestion_taller.agregar_producto_orden, name='agregar_producto_orden'),
    path('taller/editar-precio-servicio/<int:detalle_id>/', gestion_taller.editar_precio_servicio, name='editar_precio_servicio'),
    path('taller/', gestion_taller.modo_taller, name='modo_taller'),
    path('taller/<int:orden_id>/', gestion_taller.taller_detalle, name='taller_detalle'),
    path('orden/<int:orden_id>/cambiar-estado/', gestion_taller.cambiar_estado_orden, name='cambiar_estado_orden'),
    path('servicio/<int:detalle_id>/cambiar-estado/', gestion_taller.cambiar_estado_servicio, name='cambiar_estado_servicio'),
    
    path('taller/hallazgo/agregar/<int:orden_id>/', gestion_taller.agregar_hallazgo_orden, name='agregar_hallazgo_orden'),
    
    # 3er incremt
    #fecha 2 de julio de 2026
    path('buscar/', seguimiento_vehicular.buscar_vehiculo, name='buscar_vehiculo'),
    path('historial/<str:placa>/', seguimiento_vehicular.historial_vehiculo, name='historial_vehiculo'),
    path('orden/<int:orden_id>/revision/', seguimiento_vehicular.revision_tecnica, name='revision_tecnica'),
    path('orden/<int:orden_id>/hallazgo/', seguimiento_vehicular.registrar_hallazgo, name='registrar_hallazgo'),
    path('hallazgo/autorizar/<int:hallazgo_id>/', seguimiento_vehicular.autorizar_hallazgo, name='autorizar_hallazgo'),
    path('hallazgo/rechazar/<int:hallazgo_id>/', seguimiento_vehicular.rechazar_hallazgo, name='rechazar_hallazgo'), 

       
    # ultimo aministrativo
    #fecha: 17 de julio de 2026
    path('admin-dashboard/', gestion_administrativa.dashboard_admin, name='dashboard_admin'),
    path('jefe-dashboard/', gestion_administrativa.dashboard_jefe, name='dashboard_jefe'),

    path('orden/<int:orden_id>/pago/', gestion_administrativa.registrar_pago, name='registrar_pago'),
    path('insumos/', gestion_administrativa.lista_insumos, name='lista_insumos'),
    path('insumos/crear/', gestion_administrativa.crear_insumo, name='crear_insumo'),
    path('insumos/<int:producto_id>/editar/', gestion_administrativa.editar_insumo, name='editar_insumo'),
    path('insumos/<int:producto_id>/desactivar/', gestion_administrativa.desactivar_insumo, name='desactivar_insumo'),
    #8/8/2026
    path('servicios/', gestion_administrativa.lista_servicios, name='lista_servicios'),
    path('servicios/crear/', gestion_administrativa.crear_servicio, name='crear_servicio'),
    path('servicios/<int:servicio_id>/editar/', gestion_administrativa.editar_servicio, name='editar_servicio'),

    path('servicios/<int:servicio_id>/desactivar/', gestion_administrativa.desactivar_servicio, name='desactivar_servicio'),
    path('reportes/', gestion_administrativa.reportes, name='reportes'),
    path('reportes/producto/<int:producto_id>/', gestion_administrativa.detalle_producto_vendido, name='detalle_producto_vendido'),
    path('reportes/mecanico/<int:mecanico_id>/', gestion_administrativa.detalle_mecanico, name='detalle_mecanico'),
    #31 de julio de 2026
    #path('dashboard/', dashboard_views.dashboard, name='dashboard'),

]