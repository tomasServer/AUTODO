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
    return render(request, 'gestion_vehicular/jefe_mecanico/gestion_administrativa/dashboard_jefe.html', contexto)


def dashboard_jefe(request):
    hoy = timezone.now().date()
    
    ordenes_activas = OrdenTrabajo.objects.filter(
        estado_orden__in=['PENDIENTE', 'EN_PROCESO', 'FINALIZADA']
    ).order_by('-fecha_ingreso')
    
    ordenes_hoy = ordenes_activas.filter(fecha_ingreso__date=hoy).count()
    ordenes_sin_revision = ordenes_activas.filter(revisiones__isnull=True).count()
    
    contexto = {
        'ordenes': ordenes_activas,
        'ordenes_hoy': ordenes_hoy,
        'ordenes_sin_revision': ordenes_sin_revision,
        'hoy': hoy,
    }
    return render(request, 'gestion_vehicular/gestion_mecanico/gestion_taller/dashboard_jefe.html', contexto)



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
    
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/pago.html', {
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
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    
    # === FILTROS BASE ===
    productos_filter = DetalleProducto.objects.all()
    servicios_filter = DetalleServicio.objects.filter(estado='FINALIZADO')
    pagos_filter = Pago.objects.filter(estado_pago='COBRADO')
    
    if fecha_inicio and fecha_fin:
        productos_filter = productos_filter.filter(
            id_orden__fecha_ingreso__date__gte=fecha_inicio,
            id_orden__fecha_ingreso__date__lte=fecha_fin
        )
        servicios_filter = servicios_filter.filter(
            id_orden__fecha_ingreso__date__gte=fecha_inicio,
            id_orden__fecha_ingreso__date__lte=fecha_fin
        )
        pagos_filter = pagos_filter.filter(
            fecha_pago__date__gte=fecha_inicio,
            fecha_pago__date__lte=fecha_fin
        )
    
    # === PRODUCTOS VENDIDOS (con ID para enlace) ===
    productos_vendidos = productos_filter.values(
        'id_producto__id', 'id_producto__nombre'
    ).annotate(
        total_vendido=Sum('cantidad'),
        total_bs=Sum('subtotal_precio')
    ).order_by('-total_vendido')
    
    # === SERVICIOS POR MECÁNICO (con ID para enlace) ===
    servicios_por_mecanico = servicios_filter.values(
        'id_mecanico__id', 'id_mecanico__nombre', 'id_mecanico__apellido'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    # === SERVICIOS MÁS REALIZADOS ===
    servicios_mas_realizados = servicios_filter.values(
        'id_servicio__nombre'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    # === TOTALES ===
    total_productos_bs = productos_filter.aggregate(Sum('subtotal_precio'))['subtotal_precio__sum'] or 0
    total_servicios_bs = servicios_filter.aggregate(Sum('precio_cobrado'))['precio_cobrado__sum'] or 0
    total_pagado = pagos_filter.aggregate(Sum('monto_total'))['monto_total__sum'] or 0
    
    contexto = {
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'productos_vendidos': productos_vendidos,
        'servicios_por_mecanico': servicios_por_mecanico,
        'servicios_mas_realizados': servicios_mas_realizados,
        'total_productos_bs': total_productos_bs,
        'total_servicios_bs': total_servicios_bs,
        'total_pagado': total_pagado,
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


def detalle_producto_vendido(request, producto_id):
    """Muestra las órdenes donde se vendió un producto específico"""
    producto = get_object_or_404(Producto, id=producto_id)
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    
    ventas = DetalleProducto.objects.filter(id_producto=producto).order_by('-id_orden__fecha_ingreso')
    
    if fecha_inicio and fecha_fin:
        ventas = ventas.filter(id_orden__fecha_ingreso__date__gte=fecha_inicio, id_orden__fecha_ingreso__date__lte=fecha_fin)
    
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
    
    servicios = DetalleServicio.objects.filter(id_mecanico=mecanico, estado='FINALIZADO').order_by('-fecha_fin')
    
    if fecha_inicio and fecha_fin:
        servicios = servicios.filter(id_orden__fecha_ingreso__date__gte=fecha_inicio, id_orden__fecha_ingreso__date__lte=fecha_fin)
    
    return render(request, 'gestion_vehicular/admin/gestion_administrativa/detalle_mecanico.html', {
        'mecanico': mecanico,
        'servicios': servicios,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    })