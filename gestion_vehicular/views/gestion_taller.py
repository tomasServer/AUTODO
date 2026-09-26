from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from ..models import *
from django.db import connection 
from xhtml2pdf import pisa
from django.template.loader import render_to_string
from django.http import HttpResponse


def _revisar_estado_orden(orden):
    """
    Revisa el estado de la orden según sus servicios:
    - Si TODOS están FINALIZADOS → POR_COBRAR
    - Si alguno está EN_PROCESO o PENDIENTE → EN_PROCESO
    - Si no hay servicios → no cambia nada
    """
    servicios = DetalleServicio.objects.filter(id_orden=orden)
    
    if not servicios.exists():
        return
    
    todos_finalizados = all(s.estado == 'FINALIZADO' for s in servicios)
    alguno_en_proceso = any(s.estado == 'EN_PROCESO' for s in servicios)
    
    if todos_finalizados:
        if orden.estado_orden != 'POR_COBRAR':
            orden.estado_orden = 'POR_COBRAR'
            orden.fecha_finalizacion = timezone.now()
            orden.save()
    elif alguno_en_proceso or orden.estado_orden == 'POR_COBRAR':
        if orden.estado_orden != 'EN_PROCESO':
            orden.estado_orden = 'EN_PROCESO'
            orden.save()


# ============================================================
# CREAR ORDEN
# ============================================================

def crear_orden(request):
    # ============ DETECTAR SI VIENE DE UNA VISITA ============
    visita_id = request.GET.get('visita_id')
    es_nueva_visita = request.GET.get('nueva_visita') == '1'
    orden_visita = None
    revision_existente = None
    detalle_revision = None
    revision_detalle = None
    
    # ============ OBTENER DETALLE DE REVISIÓN ============
    if request.session.get('revision_detalle'):
        revision_detalle = request.session.pop('revision_detalle')
    
    if visita_id:
        orden_visita = get_object_or_404(OrdenTrabajo, id=visita_id)
        if orden_visita.estado_orden != 'VISITA':
            messages.error(request, 'Esta orden no está en estado VISITA.')
            return redirect('modo_taller')
        
        placa = orden_visita.id_vehiculo.placa
        vehiculo = orden_visita.id_vehiculo
        cliente = vehiculo.id_cliente
        
        revision_existente = RevisionTecnica.objects.filter(id_orden=orden_visita).first()
        if revision_existente:
            detalle_revision = DetalleRevision.objects.filter(
                id_revision=revision_existente
            ).select_related('id_componente')
            
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
    
    # ============ DETECTAR COTIZACIÓN ANTERIOR ============
    orden_anterior_id = request.GET.get('orden_anterior_id')
    cotizacion_anterior = None
    
    if orden_anterior_id:
        cotizacion_anterior = OrdenTrabajo.objects.filter(
            id=orden_anterior_id, 
            estado_orden='CANCELADA'
        ).first()
    
    # ============ SI NO ES VISITA, BUSCAR POR PLACA O VEHICULO_ID ============
    if not visita_id:
        placa = request.GET.get('placa', '')
        vehiculo_id = request.GET.get('vehiculo_id')
        vehiculo = None
        cliente = None
        
        if vehiculo_id:
            try:
                vehiculo = Vehiculo.objects.get(id=vehiculo_id)
                cliente = vehiculo.id_cliente
                placa = vehiculo.placa
            except Vehiculo.DoesNotExist:
                pass
    
    # ============ PROCESAR POST ============
    if request.method == 'POST':
        placa = request.POST.get('placa', '').upper().strip()
        cliente_nombre = (request.POST.get('cliente_nombre') or '').strip()
        cliente_telefono = (request.POST.get('cliente_telefono') or '').strip()
        supervisor_id = request.POST.get('supervisor_id')
        complejidad_id = request.POST.get('complejidad_id')
        observacion = request.POST.get('observacion', '')
        kilometraje = request.POST.get('kilometraje')
        anio = request.POST.get('anio')
        color = request.POST.get('color')
        vin = request.POST.get('vin')
        
        # ============ GESTIÓN DEL CLIENTE ============
        cliente = None
        
        if cliente_telefono:
            cliente = Cliente.objects.filter(telefono=cliente_telefono).first()
            
            if cliente:
                if cliente_nombre and cliente.nombre != cliente_nombre:
                    cliente.nombre = cliente_nombre
                    cliente.save()
            else:
                cliente = Cliente.objects.create(
                    nombre=cliente_nombre or 'Cliente sin nombre',
                    telefono=cliente_telefono,
                )
        elif cliente_nombre:
            cliente = Cliente.objects.create(
                nombre=cliente_nombre,
                telefono=None,
            )
        
        # ============ CREAR O ACTUALIZAR VEHÍCULO ============
        vehiculo, created = Vehiculo.objects.get_or_create(
            placa=placa,
            defaults={
                'id_cliente': cliente,
                'anio': anio if anio else None,
                'color': color if color else None,
                'vin': vin if vin else None,
            }
        )
        
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
        
        # ============ CREAR O CONVERTIR ORDEN ============
        if orden_visita:
            orden = orden_visita
            orden.id_jefe_tecnico_id = supervisor_id if supervisor_id else None
            orden.id_complejidad_id = complejidad_id if complejidad_id else None
            orden.observacion_general = observacion
            orden.estado_orden = 'PENDIENTE'
            orden.save()
            messages.info(request, f'Visita #{orden.id} convertida a PENDIENTE.')
        else:
            orden = OrdenTrabajo.objects.create(
                id_vehiculo=vehiculo,
                id_jefe_tecnico_id=supervisor_id if supervisor_id else None,
                id_complejidad_id=complejidad_id if complejidad_id else None,
                estado_orden='PENDIENTE',
                observacion_general=observacion,
                fecha_ingreso=timezone.now(),
                fecha_creacion=timezone.now(),
            )
        
        # ============ GUARDAR SERVICIOS ============
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
        
        # ============ GUARDAR PRODUCTOS (SQL CRUDO) ============
        for key in request.POST:
            if key.startswith('producto_id_'):
                num = key.split('_')[-1]
                producto_id = request.POST.get(key)
                cantidad = request.POST.get(f'cantidad_{num}', '1')
                precio_producto = request.POST.get(f'precio_producto_{num}', '0')
                
                if producto_id:
                    producto = get_object_or_404(Producto, id=producto_id)
                    cantidad_int = int(cantidad) if cantidad else 1
                    precio_u = float(precio_producto) if precio_producto else float(producto.precio_venta)
                    
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO detalle_producto "
                            "(id_orden, id_producto, cantidad, costo_unitario, precio_unitario, registrado_por) "
                            "VALUES (%s, %s, %s, %s, %s, %s)",
                            [orden.id, producto.id, cantidad_int, 
                             producto.costo_unitario, 
                             precio_u,
                             request.user.id if request.user.is_authenticated else None]
                        )
                    
                    producto.stock_actual -= cantidad_int
                    producto.save()
        
        messages.success(request, f'Orden #{orden.id} {"convertida de visita" if orden_visita else "creada"} para {placa}.')
        return redirect('detalle_orden', orden_id=orden.id)
    
    # ============ CONTEXTO PARA RENDERIZAR ============
    supervisores = Usuario.objects.filter(
        activo=True,
        id_rol_id__in=[1, 2]
    ).order_by('id_rol_id', 'nombre')
    
    mecanicos = Usuario.objects.filter(
        activo=True,
        id_rol_id__in=[1, 2, 3]
    ).order_by('id_rol_id', 'nombre')
    
    if request.user.id_rol_id == 3:  # AYUDANTE
        servicios = Servicio.objects.filter(activo=True, tiempo_estimado_minutos__lt=30)
    else:
        servicios = Servicio.objects.filter(activo=True)
    
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
        'revision_detalle': revision_detalle,
    })


# ============================================================
# DETALLE DE ORDEN
# ============================================================

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


# ============================================================
# AGREGAR SERVICIO / PRODUCTO
# ============================================================

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
            
            _revisar_estado_orden(orden)
            
            messages.success(request, f'Servicio "{servicio.nombre}" agregado por Bs. {precio}')
    
    return redirect('taller_detalle', orden_id=orden.id)


def agregar_producto_orden(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = request.POST.get('cantidad', 1)
        precio_unitario = request.POST.get('precio_unitario')
        
        if producto_id and cantidad:
            producto = get_object_or_404(Producto, id=producto_id)
            cantidad_int = int(cantidad)
            precio_u = float(precio_unitario) if precio_unitario else float(producto.precio_venta)
            
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO detalle_producto "
                    "(id_orden, id_producto, cantidad, costo_unitario, precio_unitario, registrado_por) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    [orden.id, producto.id, cantidad_int, 
                     producto.costo_unitario, 
                     precio_u,
                     request.user.id if request.user.is_authenticated else None]
                )
            
            producto.stock_actual -= cantidad_int
            producto.save()
            
            _revisar_estado_orden(orden)
            messages.success(request, f'Producto "{producto.nombre}" agregado')
        else:
            messages.error(request, 'Seleccione un producto y cantidad')
    
    return redirect('taller_detalle', orden_id=orden.id)

# ============================================================
# MODO TALLER
# ============================================================

def modo_taller(request):
    if request.user.id_rol_id == 3:  # AYUDANTE
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
        ordenes_trabajo = OrdenTrabajo.objects.filter(
            estado_orden__in=['PENDIENTE', 'EN_PROCESO', 'VISITA']
        ).order_by('fecha_ingreso')
        
        ordenes_cobrar = OrdenTrabajo.objects.filter(
            estado_orden='POR_COBRAR'
        ).order_by('fecha_ingreso')
    
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


# ============================================================
# TALLER DETALLE
# ============================================================

def taller_detalle(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    servicios_disponibles = Servicio.objects.filter(activo=True)
    productos_disponibles = Producto.objects.filter(activo=True, stock_actual__gt=0)
    mecanicos = Usuario.objects.filter(activo=True, id_rol_id__in=[1, 2, 3]).order_by('nombre')

    # FILTRO PARA AYUDANTE
    if request.user.id_rol_id == 3:  # AYUDANTE
        servicios_detalle = orden.detalles_servicio.filter(id_mecanico=request.user)
    else:
        servicios_detalle = orden.detalles_servicio.all()

    if request.user.id_rol_id == 1:  # ADMIN
        template = 'gestion_vehicular/admin/gestion_taller/taller_detalle.html'
    elif request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/taller_detalle.html'
    else:  # AYUDANTE
        template = 'gestion_vehicular/ayudante/trabajar_orden.html'
    
    return render(request, template, {
        'orden': orden,
        'servicios_detalle': servicios_detalle,
        'servicios': servicios_disponibles,
        'productos': productos_disponibles,
        'mecanicos': mecanicos,
    })


# ============================================================
# CAMBIAR ESTADO DE SERVICIO
# ============================================================

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
        
        # ✅ Usar función auxiliar para revisar el estado
        _revisar_estado_orden(orden)
        
        messages.success(request, f'Servicio cambiado a {nuevo_estado}')
        
        return redirect('taller_detalle', orden_id=orden.id)
    
    return redirect('taller_detalle', orden_id=orden.id)


# ============================================================
# HALLAZGOS
# ============================================================

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


# ============================================================
# EDITAR PRECIO DE SERVICIO
# ============================================================

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
            detalle.precio_cobrado = float(nuevo_precio)
            detalle.save()
            messages.success(request, f'Precio actualizado a Bs. {nuevo_precio}')
        else:
            messages.error(request, 'Ingrese un precio válido')
    
    return redirect('taller_detalle', orden_id=detalle.id_orden.id)


# ============================================================
# ELIMINAR SERVICIO / PRODUCTO
# ============================================================

def eliminar_servicio_orden(request, detalle_id):
    """Elimina un servicio de la orden (solo si está PENDIENTE)."""
    detalle = get_object_or_404(DetalleServicio, id=detalle_id)
    orden = detalle.id_orden
    
    if detalle.estado != 'PENDIENTE':
        messages.error(request, 'No se puede eliminar un servicio que ya fue iniciado.')
        return redirect('taller_detalle', orden_id=orden.id)
    
    nombre = detalle.id_servicio.nombre
    detalle.delete()
    
    # ✅ Revisar estado de la orden después de eliminar
    _revisar_estado_orden(orden)
    
    messages.success(request, f'Servicio "{nombre}" eliminado de la orden.')
    return redirect('taller_detalle', orden_id=orden.id)


def eliminar_producto_orden(request, detalle_id):
    """Elimina un producto de la orden y devuelve el stock."""
    detalle = get_object_or_404(DetalleProducto, id=detalle_id)
    orden = detalle.id_orden
    
    producto = detalle.id_producto
    if producto:
        producto.stock_actual += detalle.cantidad
        producto.save()
    
    nombre = producto.nombre if producto else 'Producto'
    detalle.delete()
    messages.success(request, f'Producto "{nombre}" eliminado. Stock devuelto.')
    return redirect('taller_detalle', orden_id=orden.id)


# ============================================================
# CANCELAR VISITA
# ============================================================

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
                # Guardar servicios adicionales
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
                
                # Guardar productos adicionales (SQL crudo)
                for key in request.POST:
                    if key.startswith('producto_') and not key.startswith('precio_producto_'):
                        num = key.split('_')[-1]
                        producto_id = request.POST.get(key)
                        cantidad = request.POST.get(f'cantidad_{num}', '1')
                        precio = request.POST.get(f'precio_producto_{num}', '0')
                        
                        if producto_id:
                            producto = get_object_or_404(Producto, id=producto_id)
                            cantidad_int = int(cantidad) if cantidad else 1
                            precio_u = float(precio) if precio else float(producto.precio_venta)
                            
                            with connection.cursor() as cursor:
                                cursor.execute(
                                    "INSERT INTO detalle_producto "
                                    "(id_orden, id_producto, cantidad, costo_unitario, precio_unitario, registrado_por) "
                                    "VALUES (%s, %s, %s, %s, %s, %s)",
                                    [orden.id, producto.id, cantidad_int, 
                                     producto.costo_unitario, 
                                     precio_u,
                                     request.user.id if request.user.is_authenticated else None]
                                )
                            
                            producto.stock_actual -= cantidad_int
                            producto.save()
                
                orden.estado_orden = 'CANCELADA'
                orden.save()
                messages.success(request, 'Visita guardada como cancelada con los servicios cotizados')
            else:
                messages.warning(request, 'No se encontró visita activa')
        else:
            messages.warning(request, 'No se encontró el vehículo')
    
    return redirect('buscar_vehiculo')


# ============================================================
# CONVERTIR VISITA EN ORDEN
# ============================================================

def convertir_visita_en_orden(request, orden_id):
    """
    Redirige a crear_orden con los datos de la visita precargados.
    """
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    if orden.estado_orden != 'VISITA':
        messages.error(request, 'Esta orden no está en estado VISITA.')
        return redirect('modo_taller')
    
    return redirect(f'/orden/crear/?visita_id={orden.id}')



    # ============================================================
# GENERAR PDF DE LA ORDEN (xhtml2pdf)
# ============================================================




def orden_pdf(request, orden_id):
    """Genera un PDF con los servicios, insumos y totales de la orden."""
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    
    # ✅ Calcular totales
    total_servicios = sum(float(d.precio_cobrado or 0) for d in orden.detalles_servicio.all())
    total_productos = sum(float(d.subtotal_precio or 0) for d in orden.detalles_producto.all())
    total_general = total_servicios + total_productos
    
    # ✅ Renderizar el template HTML
    html_string = render_to_string(
        'gestion_vehicular/admin/gestion_taller/recibo_pdf.html',
        {
            'orden': orden,
            'total_servicios': total_servicios,
            'total_productos': total_productos,
            'total_general': total_general,
        }
    )
    
    # ✅ Crear respuesta HTTP con tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="orden_{orden.id}.pdf"'
    
    # ✅ Convertir HTML a PDF
    pisa_status = pisa.CreatePDF(html_string, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    
    return response