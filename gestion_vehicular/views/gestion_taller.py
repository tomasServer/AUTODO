from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.db import connection
from ..models import *
from django.contrib.auth.decorators import login_required


def crear_orden(request):
    # ============ DETECTAR SI VIENE DE UNA VISITA ============
    visita_id = request.GET.get('visita_id')
    es_nueva_visita = request.GET.get('nueva_visita') == '1'
    orden_visita = None
    revision_existente = None
    detalle_revision = None
    revision_detalle = None
    
    # ============ OBTENER DETALLE DE REVISIÓN ============
    # 1️⃣ Primero desde la sesión (visita nueva)
    if request.session.get('revision_detalle'):
        revision_detalle = request.session.pop('revision_detalle')
    
    if visita_id:
        orden_visita = get_object_or_404(OrdenTrabajo, id=visita_id)
        if orden_visita.estado_orden != 'VISITA':
            messages.error(request, 'Esta orden no está en estado VISITA.')
            return redirect('modo_taller')
        
        # Usar los datos de la visita
        placa = orden_visita.id_vehiculo.placa
        vehiculo = orden_visita.id_vehiculo
        cliente = vehiculo.id_cliente
        
        # Obtener la revisión asociada a la visita (para mostrar detalles)
        revision_existente = RevisionTecnica.objects.filter(id_orden=orden_visita).first()
        if revision_existente:
            detalle_revision = DetalleRevision.objects.filter(
                id_revision=revision_existente
            ).select_related('id_componente')
            
            # 2️⃣ Si no hay sesión, construir desde la BD
            if not revision_detalle and detalle_revision.exists():
                estados = {'MALO': [], 'REGULAR': [], 'OK': []}
                componentes = []
                
                for detalle in detalle_revision:
                    nombre = detalle.id_componente.nombre
                    estado = detalle.estado
                    componentes.append({
                        'nombre': nombre,
                        'estado': estado,
                        'nota': detalle.nota or ''
                    })
                    if estado in estados:
                        estados[estado].append(nombre)
                
                revision_detalle = {
                    'porcentaje': revision_existente.isv_porcentaje or 0,
                    'resumen': estados,
                    'componentes': componentes,
                }
    # ============================================================
    
    orden_anterior_id = request.GET.get('orden_anterior_id')
    cotizacion_anterior = None
    
    if orden_anterior_id:
        cotizacion_anterior = OrdenTrabajo.objects.filter(
            id=orden_anterior_id, 
            estado_orden='CANCELADA'
        ).first()
    
    # Si no hay visita, buscar por placa o vehiculo_id (comportamiento normal)
    if not visita_id:
        placa = request.GET.get('placa', '')
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
        supervisor_id = request.POST.get('supervisor_id')
        complejidad_id = request.POST.get('complejidad_id')
        observacion = request.POST.get('observacion', '')
        kilometraje = request.POST.get('kilometraje')
        anio = request.POST.get('anio')
        color = request.POST.get('color')
        vin = request.POST.get('vin')
        
        # Crear o obtener cliente
        if cliente_telefono:
            cliente, _ = Cliente.objects.get_or_create(
                telefono=cliente_telefono,
                defaults={'nombre': cliente_nombre}
            )
        else:
            cliente = None
        
        # Crear o obtener vehículo
        vehiculo, created = Vehiculo.objects.get_or_create(
            placa=placa,
            defaults={
                'id_cliente': cliente,
                'anio': anio if anio else None,
                'color': color if color else None,
                'vin': vin if vin else None,
            }
        )
        
        # Actualizar datos del vehículo si ya existía
        if not created:
            if cliente:
                vehiculo.id_cliente = cliente
            if anio:
                vehiculo.anio = anio
            if color:
                vehiculo.color = color
            if vin:
                vehiculo.vin = vin
            vehiculo.save()
        
        if kilometraje:
            vehiculo.kilometraje_actual = int(kilometraje)
            vehiculo.save()
        
        # ============ SI ES UNA VISITA, ACTUALIZAR EN LUGAR DE CREAR ============
        if orden_visita:
            orden = orden_visita
            orden.id_jefe_tecnico_id = supervisor_id if supervisor_id else None
            orden.id_complejidad_id = complejidad_id if complejidad_id else None
            orden.observacion_general = observacion
            orden.estado_orden = 'PENDIENTE'  # Cambiar de VISITA a PENDIENTE
            orden.save()
            messages.info(request, f'Visita #{orden.id} convertida a PENDIENTE.')
        else:
            # Crear nueva orden (comportamiento normal)
            orden = OrdenTrabajo.objects.create(
                id_vehiculo=vehiculo,
                id_jefe_tecnico_id=supervisor_id if supervisor_id else None,
                id_complejidad_id=complejidad_id if complejidad_id else None,
                estado_orden='PENDIENTE',
                observacion_general=observacion,
                fecha_ingreso=timezone.now(),
                fecha_creacion=timezone.now(),
            )
        # ===========================================================

        # Guardar servicios (cada uno con su mecánico)
        for key in request.POST:
            if key.startswith('servicio_id_'):
                num = key.split('_')[-1]
                servicio_id = request.POST.get(key)
                precio = request.POST.get(f'precio_servicio_{num}', '0')
                mecanico_id = request.POST.get(f'mecanico_{num}')
                
                if servicio_id:
                    servicio = get_object_or_404(Servicio, id=servicio_id)
                    DetalleServicio.objects.create(
                        id_orden=orden,
                        id_servicio=servicio,
                        id_mecanico_id=mecanico_id if mecanico_id else None,
                        precio_cobrado=float(precio) if precio else servicio.precio_mano_obra,
                        costo_real=servicio.costo_mano_obra,
                        estado='PENDIENTE',
                    )
        
        # Guardar productos
        from django.db import connection
        for key in request.POST:
            if key.startswith('producto_id_'):
                num = key.split('_')[-1]
                producto_id = request.POST.get(key)
                cantidad = request.POST.get(f'cantidad_{num}', '1')
                precio_producto = request.POST.get(f'precio_producto_{num}', '0')
                
                if producto_id:
                    producto = get_object_or_404(Producto, id=producto_id)
                    cantidad_int = int(cantidad) if cantidad else 1
                    
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO detalle_producto (id_orden, id_producto, cantidad, costo_unitario, precio_unitario) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            [orden.id, producto.id, cantidad_int, 
                             producto.costo_unitario, 
                             float(precio_producto) if precio_producto else producto.precio_venta]
                        )
                    
                    producto.stock_actual -= cantidad_int
                    producto.save()
        
        messages.success(request, f'Orden #{orden.id} {"convertida de visita" if orden_visita else "creada"} para {placa}. Servicios y productos guardados.')
        return redirect('detalle_orden', orden_id=orden.id)
    
    # Supervisores (Admin y Jefe Mecánico)
    supervisores = Usuario.objects.filter(
        activo=True,
        id_rol_id__in=[1, 2]
    ).order_by('id_rol_id', 'nombre')
    
    # Mecánicos (Admin, Jefe, Ayudante)
    mecanicos = Usuario.objects.filter(
        activo=True,
        id_rol_id__in=[1, 2, 3]
    ).order_by('id_rol_id', 'nombre')
    
    # ============ FILTRO PARA AYUDANTE ============
    if request.user.id_rol_id == 3:  # AYUDANTE
        # Solo servicios con tiempo estimado MENOS DE 30 minutos
        servicios = Servicio.objects.filter(activo=True, tiempo_estimado_minutos__lt=30)
    else:
        servicios = Servicio.objects.filter(activo=True)
    # =============================================
    
    # Elegir template según rol
    if request.user.id_rol_id == 1:  # ADMIN
        template = 'gestion_vehicular/admin/gestion_taller/crear_orden.html'
    elif request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/crear_orden.html'
    else:  # AYUDANTE
        template = 'gestion_vehicular/ayudante/crear_orden.html'
    
    return render(request, template, {
        'supervisores': supervisores,
        'complejidades': Complejidad.objects.all(),
        'servicios': servicios,
        'productos': Producto.objects.filter(activo=True, stock_actual__gt=0),
        'mecanicos': mecanicos,
        'vehiculo': vehiculo,
        'cliente': cliente,
        'placa': placa,
        'cotizacion_anterior': cotizacion_anterior,
        'orden_visita': orden_visita,
        'es_nueva_visita': es_nueva_visita,
        'revision_existente': revision_existente,
        'detalle_revision': detalle_revision,
        'revision_detalle': revision_detalle,  # <-- Revisión formateada
    })


def detalle_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    total_servicios = sum(d.precio_cobrado or 0 for d in orden.detalles_servicio.all())
    total_productos = sum(d.subtotal_precio or 0 for d in orden.detalles_producto.all())
    
    if request.user.id_rol_id == 1:  # ADMIN
        template = 'gestion_vehicular/admin/gestion_taller/detalle_orden.html'
    elif request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/detalle_orden.html'
    else:
        template = 'gestion_vehicular/admin/gestion_taller/detalle_orden.html'
    
    return render(request, template, {
        'orden': orden,
        'servicios': Servicio.objects.filter(activo=True),
        'productos': Producto.objects.filter(activo=True, stock_actual__gt=0),
        'total_servicios': total_servicios,
        'total_productos': total_productos,
        'total_general': total_servicios + total_productos,
    })


def agregar_servicio_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    if request.method == 'POST':
        servicio_id = request.POST.get('servicio_id')
        precio_cobrado = request.POST.get('precio_cobrado')
        mecanico_id = request.POST.get('mecanico_id')
        
        if servicio_id:
            servicio = get_object_or_404(Servicio, id=servicio_id)
            precio = float(precio_cobrado) if precio_cobrado else float(servicio.precio_mano_obra)
            
            DetalleServicio.objects.create(
                id_orden=orden,
                id_servicio=servicio,
                id_mecanico_id=mecanico_id if mecanico_id else None,
                precio_cobrado=precio,
                costo_real=servicio.costo_mano_obra,
                estado='PENDIENTE',
            )
            messages.success(request, f'Servicio "{servicio.nombre}" agregado por Bs. {precio}')
    
    return redirect('taller_detalle', orden_id=orden.id)


def agregar_producto_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = request.POST.get('cantidad', 1)
        
        if producto_id and cantidad:
            producto = get_object_or_404(Producto, id=producto_id)
            cantidad_int = int(cantidad)
            
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO detalle_producto (id_orden, id_producto, cantidad, costo_unitario, precio_unitario) VALUES (%s, %s, %s, %s, %s)",
                    [orden.id, producto.id, cantidad_int, producto.costo_unitario, producto.precio_venta]
                )
            
            producto.stock_actual -= cantidad_int
            producto.save()
            
            messages.success(request, f'Producto "{producto.nombre}" agregado')
        else:
            messages.error(request, 'Seleccione un producto y cantidad')
    
    return redirect('taller_detalle', orden_id=orden.id)


from django.db.models import Q

def modo_taller(request):
    if request.user.id_rol_id == 3:  # AYUDANTE
        # Órdenes donde el ayudante tiene al menos un servicio asignado
        ordenes_ids = DetalleServicio.objects.filter(
            id_mecanico=request.user
        ).values_list('id_orden_id', flat=True).distinct()
        
        ordenes_trabajo = OrdenTrabajo.objects.filter(
            id__in=ordenes_ids,
            estado_orden__in=['PENDIENTE', 'EN_PROCESO', 'VISITA']
        ).order_by('fecha_ingreso')
        
        ordenes_cobrar = OrdenTrabajo.objects.filter(
            id__in=ordenes_ids,
            estado_orden='POR_COBRAR'
        ).order_by('fecha_ingreso')
    else:
        # Admin o Jefe ven todas las órdenes
        ordenes_trabajo = OrdenTrabajo.objects.filter(
            estado_orden__in=['PENDIENTE', 'EN_PROCESO', 'VISITA']
        ).order_by('fecha_ingreso')
        
        ordenes_cobrar = OrdenTrabajo.objects.filter(
            estado_orden='POR_COBRAR'
        ).order_by('fecha_ingreso')
    
    # Elegir template según rol
    if request.user.id_rol_id == 1:  # ADMIN
        template = 'gestion_vehicular/admin/gestion_taller/taller.html'
    elif request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/modo_taller.html'
    else:  # AYUDANTE
        template = 'gestion_vehicular/ayudante/modo_taller.html'
    
    return render(request, template, {
        'ordenes_trabajo': ordenes_trabajo,
        'ordenes_cobrar': ordenes_cobrar,
    })


def taller_detalle(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    servicios_disponibles = Servicio.objects.filter(activo=True)
    productos_disponibles = Producto.objects.filter(activo=True, stock_actual__gt=0)
    mecanicos = Usuario.objects.filter(activo=True, id_rol_id__in=[1, 2, 3]).order_by('nombre')

    # ============ FILTRO PARA AYUDANTE ============
    if request.user.id_rol_id == 3:  # AYUDANTE
        # Solo muestra los servicios donde el ayudante es el mecánico asignado
        servicios_detalle = orden.detalles_servicio.filter(id_mecanico=request.user)
    else:
        # Admin y Jefe ven todos los servicios
        servicios_detalle = orden.detalles_servicio.all()
    # =============================================

    if request.user.id_rol_id == 1:  # ADMIN
        template = 'gestion_vehicular/admin/gestion_taller/taller_detalle.html'
    elif request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/taller_detalle.html'
    else:  # AYUDANTE
        template = 'gestion_vehicular/ayudante/trabajar_orden.html'
    
    return render(request, template, {
        'orden': orden,
        'servicios_detalle': servicios_detalle,  # <--- AHORA FILTRADO
        'servicios': servicios_disponibles,
        'productos': productos_disponibles,
        'mecanicos': mecanicos,
    })

def cambiar_estado_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    if request.method == 'POST':
        nuevo = request.POST.get('nuevo_estado')
        orden.estado_orden = nuevo
        if nuevo == 'EN_PROCESO':
            DetalleServicio.objects.filter(id_orden=orden, estado='PENDIENTE').update(estado='EN_PROCESO', fecha_inicio=timezone.now())
        if nuevo == 'FINALIZADA':
            orden.fecha_finalizacion = timezone.now()
            DetalleServicio.objects.filter(id_orden=orden).update(estado='FINALIZADO', fecha_fin=timezone.now())
        orden.save()
        messages.success(request, f'Orden #{orden.id} cambiada a {nuevo}')
    return redirect('modo_taller')


@login_required
def cambiar_estado_servicio(request, detalle_id):
    detalle = get_object_or_404(DetalleServicio, id=detalle_id)
    orden = detalle.id_orden
    
    # Verificar permisos: solo admin o el mecánico asignado
    if request.user.id_rol_id != 1 and detalle.id_mecanico_id != request.user.id:
        messages.error(request, 'No tienes permiso para modificar este servicio.')
        return redirect('taller_detalle', orden_id=orden.id)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('nuevo_estado')
        
        detalle.estado = nuevo_estado
        if nuevo_estado == 'EN_PROCESO':
            detalle.fecha_inicio = timezone.now()
        if nuevo_estado == 'FINALIZADO':
            detalle.fecha_fin = timezone.now()
        detalle.save()
        
        servicios_orden = DetalleServicio.objects.filter(id_orden=orden)
        todos_finalizados = all(s.estado == 'FINALIZADO' for s in servicios_orden)
        
        if todos_finalizados:
            orden.estado_orden = 'POR_COBRAR'
            orden.fecha_finalizacion = timezone.now()
            orden.save()
            messages.success(request, f'Todos los servicios finalizados. Orden #{orden.id} está lista para cobrar.')
        else:
            if any(s.estado == 'EN_PROCESO' for s in servicios_orden):
                orden.estado_orden = 'EN_PROCESO'
                orden.save()
            messages.success(request, f'Servicio cambiado a {nuevo_estado}')
        
        return redirect('taller_detalle', orden_id=orden.id)
    
    # Si no es POST, redirigir al detalle de la orden
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
    
    return redirect('taller_detalle', orden_id=orden.id)


@login_required
def editar_precio_servicio(request, detalle_id):
    detalle = get_object_or_404(DetalleServicio, id=detalle_id)
    
    # Verificar permisos: solo admin o el mecánico asignado
    if request.user.id_rol_id != 1 and detalle.id_mecanico_id != request.user.id:
        messages.error(request, 'No tienes permiso para editar este servicio.')
        return redirect('taller_detalle', orden_id=detalle.id_orden.id)
    
    if request.method == 'POST':
        nuevo_precio = request.POST.get('nuevo_precio')
        if nuevo_precio:
            detalle.precio_cobrado = float(nuevo_precio)  # Considera usar Decimal para mayor precisión
            detalle.save()
            messages.success(request, f'Precio actualizado a Bs. {nuevo_precio}')
        else:
            messages.error(request, 'Ingrese un precio válido')
    
    return redirect('taller_detalle', orden_id=detalle.id_orden.id)



def cancelar_visita(request):
    if request.method == 'POST':
        placa = request.POST.get('placa', '').upper()
        vehiculo = Vehiculo.objects.filter(placa=placa).first()
        
        if vehiculo:
            orden = OrdenTrabajo.objects.filter(
                id_vehiculo=vehiculo, 
                estado_orden='VISITA'
            ).order_by('-fecha_creacion').first()
            
            if orden:
                for key in request.POST:
                    if key.startswith('servicio_adicional_'):
                        num = key.split('_')[-1]
                        servicio_id = request.POST.get(key)
                        precio = request.POST.get(f'precio_adicional_{num}', '0')
                        
                        if servicio_id:
                            servicio = get_object_or_404(Servicio, id=servicio_id)
                            DetalleServicio.objects.create(
                                id_orden=orden,
                                id_servicio=servicio,
                                precio_cobrado=float(precio) if precio else servicio.precio_mano_obra,
                                costo_real=servicio.costo_mano_obra,
                                estado='PENDIENTE',
                            )
                
                for key in request.POST:
                    if key.startswith('producto_') and not key.startswith('precio_producto_'):
                        num = key.split('_')[-1]
                        producto_id = request.POST.get(key)
                        cantidad = request.POST.get(f'cantidad_{num}', '1')
                        precio = request.POST.get(f'precio_producto_{num}', '0')
                        
                        if producto_id:
                            producto = get_object_or_404(Producto, id=producto_id)
                            with connection.cursor() as cursor:
                                cursor.execute(
                                    "INSERT INTO detalle_producto (id_orden, id_producto, cantidad, costo_unitario, precio_unitario) "
                                    "VALUES (%s, %s, %s, %s, %s)",
                                    [orden.id, producto.id, int(cantidad), 
                                     producto.costo_unitario, 
                                     float(precio) if precio else producto.precio_venta]
                                )
                
                orden.estado_orden = 'CANCELADA'
                orden.save()
                messages.success(request, 'Visita guardada como cancelada con los servicios cotizados')
            else:
                messages.warning(request, 'No se encontró visita activa')
        else:
            messages.warning(request, 'No se encontró el vehículo')
    
    return redirect('buscar_vehiculo')


#5/9/2026 mejoras convertir visita en orden

def convertir_visita_en_orden(request, orden_id):
    """
    Redirige a crear_orden con los datos de la visita precargados.
    """
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    # Verificar que la orden esté en estado VISITA
    if orden.estado_orden != 'VISITA':
        messages.error(request, 'Esta orden no está en estado VISITA.')
        return redirect('modo_taller')
    
    # Redirigir a crear_orden con el ID de la visita
    return redirect(f'/orden/crear/?visita_id={orden.id}')