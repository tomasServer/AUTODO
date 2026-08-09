from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.db import connection
from ..models import *


def crear_orden(request):
    vehiculo_id = request.GET.get('vehiculo_id')
    vehiculo = None
    cliente = None
    
    if vehiculo_id:
        try:
            vehiculo = Vehiculo.objects.get(id=vehiculo_id)
            cliente = vehiculo.id_cliente
        except Vehiculo.DoesNotExist:
            pass
    
    if request.method == 'POST':
        placa = request.POST.get('placa').upper()
        cliente_nombre = request.POST.get('cliente_nombre')
        cliente_telefono = request.POST.get('cliente_telefono')
        tipo_servicio_id = request.POST.get('tipo_servicio')
        complejidad_id = request.POST.get('complejidad')
        servicio_id = request.POST.get('servicio')
        mecanico_id = request.POST.get('mecanico')
        observacion = request.POST.get('observacion', '')
        kilometraje = request.POST.get('kilometraje')
        anio = request.POST.get('anio')
        color = request.POST.get('color')
        vin = request.POST.get('vin')
        
        # Crear o obtener cliente
        cliente, _ = Cliente.objects.get_or_create(
            telefono=cliente_telefono,
            defaults={'nombre': cliente_nombre}
        )
        
        # Crear o obtener vehículo
        vehiculo, _ = Vehiculo.objects.get_or_create(
            placa=placa,
            defaults={
                'id_cliente': cliente,
                'anio': anio if anio else None,
                'color': color if color else None,
                'vin': vin if vin else None,
            }
        )
        
        if kilometraje:
            vehiculo.kilometraje_actual = int(kilometraje)
            vehiculo.save()
        
        # Crear la orden
        orden = OrdenTrabajo.objects.create(
            id_vehiculo=vehiculo,
            id_tipo_servicio_id=tipo_servicio_id,
            id_complejidad_id=complejidad_id,
            id_servicio_id=servicio_id,
            estado_orden='PENDIENTE',
            observacion_general=observacion,
            fecha_ingreso=timezone.now(),
            fecha_creacion=timezone.now(),
        )
        
        # Crear el detalle del servicio con el mecánico
        servicio = get_object_or_404(Servicio, id=servicio_id)
        DetalleServicio.objects.create(
            id_orden=orden,
            id_servicio=servicio,
            id_mecanico_id=mecanico_id if mecanico_id else None,
            precio_cobrado=servicio.precio_mano_obra,
            costo_real=servicio.costo_mano_obra,
            estado='PENDIENTE',
        )
        
        messages.success(request, f'Orden #{orden.id} creada para {placa}')
        return redirect('detalle_orden', orden_id=orden.id)
    
    # Obtener todos los usuarios activos que pueden ser mecánicos
    from django.db.models import Q
    mecanicos = Usuario.objects.filter(
        activo=True
    ).filter(
        Q(id_rol_id=1) | Q(id_rol_id=2) | Q(id_rol_id=3)
    ).order_by('id_rol_id', 'nombre')
    
    return render(request, 'gestion_vehicular/admin/gestion_taller/crear_orden.html', {
        'tipos_servicio': TipoServicio.objects.filter(activo=True),
        'complejidades': Complejidad.objects.all(),
        'servicios': Servicio.objects.filter(activo=True),
        'mecanicos': mecanicos,
        'vehiculo': vehiculo,
        'cliente': cliente,
    })


def detalle_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    total_servicios = sum(d.precio_cobrado or 0 for d in orden.detalles_servicio.all())
    total_productos = sum(d.subtotal_precio or 0 for d in orden.detalles_producto.all())
    return render(request, 'gestion_vehicular/admin/gestion_taller/detalle_orden.html', {
        'orden': orden, 'servicios': Servicio.objects.filter(activo=True),
        'productos': Producto.objects.filter(activo=True, stock_actual__gt=0),
        'total_servicios': total_servicios, 'total_productos': total_productos,
        'total_general': total_servicios + total_productos,
    })


def agregar_servicio_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    if request.method == 'POST':
        servicio_id = request.POST.get('servicio_id')
        precio_cobrado = request.POST.get('precio_cobrado')
        
        if servicio_id:
            servicio = get_object_or_404(Servicio, id=servicio_id)
            
            # Si no se envió precio, usar el precio por defecto del servicio
            if precio_cobrado and precio_cobrado.strip():
                precio = float(precio_cobrado)
            else:
                precio = float(servicio.precio_mano_obra)
            
            DetalleServicio.objects.create(
                id_orden=orden,
                id_servicio=servicio,
                precio_cobrado=precio,
                costo_real=servicio.costo_mano_obra,
                estado='PENDIENTE',
            )
            messages.success(request, f'Servicio "{servicio.nombre}" agregado por Bs. {precio}')
        else:
            messages.error(request, 'Seleccione un servicio')
    
    return redirect('taller_detalle', orden_id=orden.id)


def agregar_producto_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = request.POST.get('cantidad', 1)
        
        if producto_id and cantidad:
            producto = get_object_or_404(Producto, id=producto_id)
            
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO detalle_producto (id_orden, id_producto, cantidad, costo_unitario, precio_unitario) VALUES (%s, %s, %s, %s, %s)",
                    [orden.id, producto.id, cantidad, producto.costo_unitario, producto.precio_venta]
                )
            messages.success(request, f'Producto "{producto.nombre}" agregado')
        else:
            messages.error(request, 'Seleccione un producto y cantidad')
    
    # Redirige de vuelta a la misma página
    return redirect('taller_detalle', orden_id=orden.id)


def modo_taller(request):
    # Órdenes para trabajar (PENDIENTE o EN_PROCESO)
    ordenes_trabajo = OrdenTrabajo.objects.filter(
        estado_orden__in=['PENDIENTE', 'EN_PROCESO']
    ).order_by('fecha_ingreso')
    
    # Órdenes para cobrar (POR_COBRAR)
    ordenes_cobrar = OrdenTrabajo.objects.filter(
        estado_orden='POR_COBRAR'
    ).order_by('fecha_ingreso')
    
    return render(request, 'gestion_vehicular/admin/gestion_taller/taller.html', {
        'ordenes_trabajo': ordenes_trabajo,
        'ordenes_cobrar': ordenes_cobrar,
    })


def taller_detalle(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    # Obtener servicios y productos disponibles para agregar
    servicios_disponibles = Servicio.objects.filter(activo=True)
    productos_disponibles = Producto.objects.filter(activo=True, stock_actual__gt=0)
    
    return render(request, 'gestion_vehicular/admin/gestion_taller/taller_detalle.html', {
        'orden': orden,
        'servicios_detalle': orden.detalles_servicio.all(),
        'servicios': servicios_disponibles,  # <--- PARA AGREGAR SERVICIOS
        'productos': productos_disponibles,  # <--- PARA AGREGAR PRODUCTOS
    })


def cambiar_estado_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    if request.method == 'POST':
        nuevo = request.POST.get('nuevo_estado')
        orden.estado_orden = nuevo
        if nuevo == 'EN_PROCESO': DetalleServicio.objects.filter(id_orden=orden, estado='PENDIENTE').update(estado='EN_PROCESO', fecha_inicio=timezone.now())
        if nuevo == 'FINALIZADA': orden.fecha_finalizacion = timezone.now(); DetalleServicio.objects.filter(id_orden=orden).update(estado='FINALIZADO', fecha_fin=timezone.now())
        orden.save()
        messages.success(request, f'Orden #{orden.id} cambiada a {nuevo}')
    return redirect('modo_taller')


def cambiar_estado_servicio(request, detalle_id):
    detalle = get_object_or_404(DetalleServicio, id=detalle_id)
    orden = detalle.id_orden
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('nuevo_estado')
        
        # Cambiar estado del servicio
        detalle.estado = nuevo_estado
        if nuevo_estado == 'EN_PROCESO':
            detalle.fecha_inicio = timezone.now()
        if nuevo_estado == 'FINALIZADO':
            detalle.fecha_fin = timezone.now()
        detalle.save()
        
        # Verificar si todos los servicios están FINALIZADOS
        servicios_orden = DetalleServicio.objects.filter(id_orden=orden)
        todos_finalizados = all(s.estado == 'FINALIZADO' for s in servicios_orden)
        
        if todos_finalizados:
            # Cambiar a POR_COBRAR
            orden.estado_orden = 'POR_COBRAR'
            orden.fecha_finalizacion = timezone.now()
            orden.save()
            messages.success(request, f'Todos los servicios finalizados. Orden #{orden.id} está lista para cobrar.')
        else:
            # Si hay servicios en proceso, la orden está EN_PROCESO
            if any(s.estado == 'EN_PROCESO' for s in servicios_orden):
                orden.estado_orden = 'EN_PROCESO'
                orden.save()
            messages.success(request, f'Servicio cambiado a {nuevo_estado}')
        
        return redirect('taller_detalle', orden_id=orden.id)


def agregar_hallazgo_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    if request.method == 'POST':
        descripcion = request.POST.get('descripcion')
        costo_estimado = request.POST.get('costo_estimado')
        
        if descripcion:
            HallazgoAdicional.objects.create(
                id_orden=orden,
                descripcion=descripcion,
                costo_estimado=costo_estimado if costo_estimado else None,
                estado_autorizacion='PENDIENTE',
                fecha_deteccion=timezone.now()
            )
            messages.success(request, 'Hallazgo agregado correctamente')
        else:
            messages.error(request, 'La descripción es obligatoria')
    
    # Redirige de vuelta a la misma página
    return redirect('taller_detalle', orden_id=orden.id)


def editar_precio_servicio(request, detalle_id):
    detalle = get_object_or_404(DetalleServicio, id=detalle_id)
    
    if request.method == 'POST':
        nuevo_precio = request.POST.get('nuevo_precio')
        if nuevo_precio:
            detalle.precio_cobrado = float(nuevo_precio)
            detalle.save()
            messages.success(request, f'Precio actualizado a Bs. {nuevo_precio}')
        else:
            messages.error(request, 'Ingrese un precio válido')
    
    return redirect('taller_detalle', orden_id=detalle.id_orden.id)