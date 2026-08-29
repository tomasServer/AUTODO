from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Count
from django.contrib import messages
from ..models import *


def dashboard_admin(request):
    hoy = timezone.now().date()
    mes_actual = hoy.replace(day=1)
    
    # === TARJETAS SUPERIORES ===
    ordenes_hoy = OrdenTrabajo.objects.filter(fecha_ingreso__date=hoy)
    vehiculos_ingresados = ordenes_hoy.count()
    vehiculos_pagados = ordenes_hoy.filter(estado_orden='COBRADA').count()
    
    pagos_hoy = Pago.objects.filter(fecha_pago__date=hoy, estado_pago='COBRADO')
    total_facturado = pagos_hoy.aggregate(Sum('monto_total'))['monto_total__sum'] or 0
    
    pagos_mes = Pago.objects.filter(fecha_pago__date__gte=mes_actual, estado_pago='COBRADO')
    total_mes = pagos_mes.aggregate(Sum('monto_total'))['monto_total__sum'] or 0
    
    # === SERVICIOS POR MECÁNICO ===
    servicios_por_mecanico = DetalleServicio.objects.filter(
        estado='FINALIZADO'
    ).values('id_mecanico__nombre', 'id_mecanico__apellido').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # === SERVICIOS MÁS REALIZADOS DEL MES ===
    servicios_mes = DetalleServicio.objects.filter(
        id_orden__fecha_ingreso__date__gte=mes_actual
    ).values('id_servicio__nombre').annotate(
        total=Count('id')
    ).order_by('-total')[:5]
    
    # === ÚLTIMOS VEHÍCULOS ===
    ultimos_vehiculos = OrdenTrabajo.objects.all().order_by('-fecha_ingreso')[:5]
    
    # === ÚLTIMAS ÓRDENES ===
    ultimas_ordenes = OrdenTrabajo.objects.all().order_by('-fecha_ingreso')[:10]
    
    # === STOCK BAJO ===
    stock_bajo = Producto.objects.filter(activo=True, stock_actual__lte=5)
    
    # === HALLAZGOS PENDIENTES ===
    hallazgos_pendientes = HallazgoAdicional.objects.filter(
        estado_autorizacion='PENDIENTE'
    ).order_by('-fecha_deteccion')
    
    contexto = {
        'vehiculos_ingresados': vehiculos_ingresados,
        'vehiculos_pagados': vehiculos_pagados,
        'total_facturado': total_facturado,
        'total_mes': total_mes,
        'servicios_por_mecanico': servicios_por_mecanico,
        'servicios_mes': servicios_mes,
        'ultimos_vehiculos': ultimos_vehiculos,
        'ultimas_ordenes': ultimas_ordenes,
        'stock_bajo': stock_bajo,
        'hallazgos_pendientes': hallazgos_pendientes,
        'hoy': hoy,
    }
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/dashboard.html', contexto)


def dashboard_jefe(request):
    hoy = timezone.now().date()
    
    ordenes_activas = OrdenTrabajo.objects.filter(
        estado_orden__in=['PENDIENTE', 'EN_PROCESO', 'FINALIZADA']
    ).order_by('-fecha_ingreso')
    
    ordenes_hoy = ordenes_activas.filter(fecha_ingreso__date=hoy).count()
    ordenes_sin_revision = ordenes_activas.filter(revisiones__isnull=True).count()
    
    pendientes_count = OrdenTrabajo.objects.filter(
        estado_orden__in=['PENDIENTE', 'EN_PROCESO']
    ).count()
    
    por_cobrar_count = OrdenTrabajo.objects.filter(
        estado_orden='POR_COBRAR'
    ).count()
    
    cobrado_hoy = Pago.objects.filter(
        fecha_pago__date=hoy, 
        estado_pago='COBRADO'
    ).aggregate(Sum('monto_total'))['monto_total__sum'] or 0
    
    ventas_rapidas_hoy = VentaRapida.objects.filter(
        fecha_venta__date=hoy
    ).aggregate(Sum('total'))['total__sum'] or 0
    
    # NUEVO: lista de ventas rápidas de hoy
    ventas_rapidas_lista = VentaRapida.objects.filter(
        fecha_venta__date=hoy
    ).order_by('-fecha_venta')
    
    hallazgos_pendientes = HallazgoAdicional.objects.filter(
        estado_autorizacion='PENDIENTE'
    ).order_by('-fecha_deteccion')
    
    ultimas_ordenes = OrdenTrabajo.objects.all().order_by('-fecha_ingreso')[:10]
    
    contexto = {
        'ordenes': ordenes_activas,
        'ordenes_hoy': ordenes_hoy,
        'ordenes_sin_revision': ordenes_sin_revision,
        'pendientes_count': pendientes_count,
        'por_cobrar_count': por_cobrar_count,
        'cobrado_hoy': cobrado_hoy,
        'ventas_rapidas_hoy': ventas_rapidas_hoy,
        'ventas_rapidas_lista': ventas_rapidas_lista,  # ← NUEVO
        'hallazgos_pendientes': hallazgos_pendientes,
        'ultimas_ordenes': ultimas_ordenes,
        'hoy': hoy,
    }
    return render(request, 'gestion_vehicular/jefe_mecanico/dashboard.html', contexto)

def dashboard_ayudante(request):
    hoy = timezone.now().date()
    
    ordenes_trabajo = OrdenTrabajo.objects.filter(
        estado_orden__in=['PENDIENTE', 'EN_PROCESO']
    ).order_by('fecha_ingreso')
    
    ventas_rapidas_lista = VentaRapida.objects.filter(
        fecha_venta__date=hoy,
        registrado_por=request.user
    ).order_by('-fecha_venta')
    
    return render(request, 'gestion_vehicular/ayudante/dashboard.html', {
        'ordenes_trabajo': ordenes_trabajo,
        'ventas_rapidas_lista': ventas_rapidas_lista,
        'hoy': hoy,
    })





def registrar_pago(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    # Verificar que la orden esté POR_COBRAR o FINALIZADA
    if orden.estado_orden not in ['POR_COBRAR', 'FINALIZADA']:
        messages.error(request, 'Esta orden no está lista para cobrar.')
        return redirect('modo_taller')
    
    # Sumar servicios
    ts = sum(d.precio_cobrado or 0 for d in orden.detalles_servicio.all())
    
    # Sumar productos
    tp = sum(d.subtotal_precio or 0 for d in orden.detalles_producto.all())
    
    # Sumar hallazgos AUTORIZADOS
    th = sum(h.costo_estimado or 0 for h in orden.hallazgos.filter(
        estado_autorizacion='AUTORIZADO_CLIENTE'
    ))
    
    # Total general
    tg = ts + tp + th
    
    if request.method == 'POST':
        Pago.objects.create(
            id_orden=orden,
            monto_total_servicios=ts,
            monto_total_productos=tp + th,
            monto_total=tg,
            metodo_pago=request.POST.get('metodo_pago'),
            estado_pago='COBRADO',
            fecha_pago=timezone.now()
        )
        orden.estado_orden = 'COBRADA'
        orden.save()
        messages.success(request, f'Pago registrado. Total: Bs. {tg}')
        return redirect('modo_taller')
    
    # Elegir template según rol
    if request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/pago.html'
    else:  # ADMIN
        template = 'gestion_vehicular/admin/gestion_administrativa/pago.html'
    
    return render(request, template, {
        'orden': orden,
        'total_servicios': ts,
        'total_productos': tp,
        'total_hallazgos': th,
        'total_general': tg
    })


def lista_insumos(request):
    p = Producto.objects.filter(activo=True).order_by('nombre')
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/insumos_lista.html', {
        'productos': p,
        'stock_bajo': p.filter(stock_actual__lte=5)
    })


def crear_insumo(request):
    if request.method == 'POST':
        Producto.objects.create(
            codigo=request.POST.get('codigo'),
            nombre=request.POST.get('nombre'),
            descripcion=request.POST.get('descripcion', ''),
            costo_unitario=request.POST.get('costo_unitario'),
            precio_venta=request.POST.get('precio_venta'),
            stock_actual=request.POST.get('stock_actual', 0),
            activo=True
        )
        messages.success(request, 'Producto agregado')
        return redirect('lista_insumos')
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/insumos_crear.html')


def editar_insumo(request, producto_id):
    p = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        p.codigo = request.POST.get('codigo')
        p.nombre = request.POST.get('nombre')
        p.descripcion = request.POST.get('descripcion', '')
        p.costo_unitario = request.POST.get('costo_unitario')
        p.precio_venta = request.POST.get('precio_venta')
        p.stock_actual = request.POST.get('stock_actual')
        p.save()
        messages.success(request, 'Producto actualizado')
        return redirect('lista_insumos')
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/insumos_editar.html', {'producto': p})


def desactivar_insumo(request, producto_id):
    p = get_object_or_404(Producto, id=producto_id)
    p.activo = False
    p.save()
    messages.success(request, f'Producto "{p.nombre}" desactivado')
    return redirect('lista_insumos')

#.........
#editar_servicios
#.........
def lista_servicios(request):
    """Lista todos los servicios del taller"""
    servicios = Servicio.objects.filter(activo=True).order_by('id_tipo_servicio__nombre', 'nombre')
    tipos = TipoServicio.objects.filter(activo=True)
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/servicios_lista.html', {
        'servicios': servicios,
        'tipos': tipos,
    })


def crear_servicio(request):
    """Crear un nuevo servicio"""
    if request.method == 'POST':
        Servicio.objects.create(
            id_tipo_servicio_id=request.POST.get('tipo_servicio'),
            nombre=request.POST.get('nombre'),
            descripcion=request.POST.get('descripcion', ''),
            costo_mano_obra=request.POST.get('costo_mano_obra'),
            precio_mano_obra=request.POST.get('precio_mano_obra'),
            tiempo_estimado_minutos=request.POST.get('tiempo_estimado_minutos'),
            activo=True,
        )
        messages.success(request, 'Servicio agregado')
        return redirect('lista_servicios')
    
    tipos = TipoServicio.objects.filter(activo=True)
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/servicios_crear.html', {
        'tipos': tipos,
    })


def editar_servicio(request, servicio_id):
    """Editar un servicio existente"""
    servicio = get_object_or_404(Servicio, id=servicio_id)
    if request.method == 'POST':
        servicio.id_tipo_servicio_id = request.POST.get('tipo_servicio')
        servicio.nombre = request.POST.get('nombre')
        servicio.descripcion = request.POST.get('descripcion', '')
        servicio.costo_mano_obra = request.POST.get('costo_mano_obra')
        servicio.precio_mano_obra = request.POST.get('precio_mano_obra')
        servicio.tiempo_estimado_minutos = request.POST.get('tiempo_estimado_minutos')
        servicio.save()
        messages.success(request, 'Servicio actualizado')
        return redirect('lista_servicios')
    
    tipos = TipoServicio.objects.filter(activo=True)
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/servicios_editar.html', {
        'servicio': servicio,
        'tipos': tipos,
    })


def desactivar_servicio(request, servicio_id):
    """Desactivar un servicio (borrado lógico)"""
    servicio = get_object_or_404(Servicio, id=servicio_id)
    servicio.activo = False
    servicio.save()
    messages.success(request, f'Servicio "{servicio.nombre}" desactivado')
    return redirect('lista_servicios')

    #administrativa#
    #...........
    #reportes
    #...
def reportes(request):
    # === PRODUCTOS ===
    fecha_inicio_p = request.GET.get('fecha_inicio_p', '')
    fecha_fin_p = request.GET.get('fecha_fin_p', '')
    producto_buscar = request.GET.get('producto', '')
    
    productos_detalle = DetalleProducto.objects.all().order_by('-id_orden__fecha_ingreso')
    
    if producto_buscar:
        productos_detalle = productos_detalle.filter(id_producto__nombre__icontains=producto_buscar)
    if fecha_inicio_p and fecha_fin_p:
        productos_detalle = productos_detalle.filter(id_orden__fecha_ingreso__date__gte=fecha_inicio_p, id_orden__fecha_ingreso__date__lte=fecha_fin_p)

    
    # === SERVICIOS ===
    fecha_inicio_s = request.GET.get('fecha_inicio_s', '')
    fecha_fin_s = request.GET.get('fecha_fin_s', '')
    servicio_buscar = request.GET.get('servicio', '')
    
    servicios_detalle = DetalleServicio.objects.all().order_by('-fecha_fin')
    
    if servicio_buscar:
        servicios_detalle = servicios_detalle.filter(id_servicio__nombre__icontains=servicio_buscar)
    if fecha_inicio_s and fecha_fin_s:
        servicios_detalle = servicios_detalle.filter(id_orden__fecha_ingreso__date__gte=fecha_inicio_s, id_orden__fecha_ingreso__date__lte=fecha_fin_s)
    
    # === MECÁNICOS ===
    fecha_inicio_m = request.GET.get('fecha_inicio_m', '')
    fecha_fin_m = request.GET.get('fecha_fin_m', '')
    
    servicios_por_mecanico = DetalleServicio.objects.filter(estado='FINALIZADO').values(
        'id_mecanico__id', 'id_mecanico__nombre', 'id_mecanico__apellido'
    ).annotate(total=Count('id')).order_by('-total')
    
    if fecha_inicio_m and fecha_fin_m:
        servicios_por_mecanico = servicios_por_mecanico.filter(id_orden__fecha_ingreso__date__gte=fecha_inicio_m, id_orden__fecha_ingreso__date__lte=fecha_fin_m)

    # === VENTAS RAPIDAS ===
    fecha_inicio_v = request.GET.get('fecha_inicio_v', '')
    fecha_fin_v = request.GET.get('fecha_fin_v', '')

    ventas_rapidas = VentaRapida.objects.all().order_by('-fecha_venta')

    if fecha_inicio_v and fecha_fin_v:
        ventas_rapidas = ventas_rapidas.filter(fecha_venta__date__gte=fecha_inicio_v, fecha_venta__date__lte=fecha_fin_v)
        
    contexto = {
        'fecha_inicio_p': fecha_inicio_p, 'fecha_fin_p': fecha_fin_p, 'producto_buscar': producto_buscar,
        'fecha_inicio_s': fecha_inicio_s, 'fecha_fin_s': fecha_fin_s, 'servicio_buscar': servicio_buscar,
        'fecha_inicio_m': fecha_inicio_m, 'fecha_fin_m': fecha_fin_m,
        'productos_detalle': productos_detalle,
        'servicios_detalle': servicios_detalle,
        'servicios_por_mecanico': servicios_por_mecanico,

        'ventas_rapidas': ventas_rapidas,
        'fecha_inicio_v': fecha_inicio_v, 'fecha_fin_v': fecha_fin_v,
    }
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/reportes.html', contexto)

def detalle_producto_vendido(request, producto_id):
    """Muestra las órdenes donde se vendió un producto específico"""
    producto = get_object_or_404(Producto, id=producto_id)
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    
    ventas = DetalleProducto.objects.filter(id_producto=producto).order_by('-id_orden__fecha_ingreso')
    
    if fecha_inicio and fecha_fin:
        ventas = ventas.filter(
            id_orden__fecha_ingreso__date__gte=fecha_inicio,
            id_orden__fecha_ingreso__date__lte=fecha_fin
        )
    
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/detalle_producto.html', {
        'producto': producto,
        'ventas': ventas,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    })


def detalle_mecanico(request, mecanico_id):
    """Muestra los servicios realizados por un mecánico específico"""
    mecanico = get_object_or_404(Usuario, id=mecanico_id)
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    
    servicios = DetalleServicio.objects.filter(
        id_mecanico=mecanico,
        estado='FINALIZADO'
    ).order_by('-fecha_fin')
    
    if fecha_inicio and fecha_fin:
        servicios = servicios.filter(
            id_orden__fecha_ingreso__date__gte=fecha_inicio,
            id_orden__fecha_ingreso__date__lte=fecha_fin
        )
    
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/detalle_mecanico.html', {
        'mecanico': mecanico,
        'servicios': servicios,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    })



## visualizar la gestion de revisiones
def gestionar_revisiones(request):
    """Administrar qué componentes aparecen en cada tipo de revisión"""
    componentes = Componente.objects.all().order_by('orden')
    
    if request.method == 'POST':
        for componente in componentes:
            componente.en_visita = request.POST.get(f'en_visita_{componente.id}') == 'on'
            componente.en_rapida = request.POST.get(f'en_rapida_{componente.id}') == 'on'
            componente.en_completa = request.POST.get(f'en_completa_{componente.id}') == 'on'
            componente.save()
        
        messages.success(request, 'Configuración de revisiones actualizada')
        return redirect('gestionar_revisiones')
    
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/revisiones.html', {
        'componentes': componentes,
    })