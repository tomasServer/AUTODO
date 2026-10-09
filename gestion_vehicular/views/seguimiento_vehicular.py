from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Sum
from django.contrib import messages
from ..models import *
from django.http import JsonResponse
from django.db.models import Q
from django.db import IntegrityError


def buscar_vehiculo(request):
    busqueda = request.GET.get('placa', '').strip()  # Acepta placa o VIN
    vehiculo = None
    ordenes = None

    if busqueda:
        # 🔍 Buscar por placa O por VIN
        vehiculo = (
            Vehiculo.objects
            .filter(
                Q(placa__iexact=busqueda) | Q(vin__iexact=busqueda)
            )
            .first()
        )

        if vehiculo:
            ordenes = (
                OrdenTrabajo.objects
                .filter(id_vehiculo=vehiculo)
                .order_by('-fecha_ingreso')[:5]
            )
            for orden in ordenes:
                total_servicios = sum(d.precio_cobrado or 0 for d in orden.detalles_servicio.all())
                total_productos = sum(d.subtotal_precio or 0 for d in orden.detalles_producto.all())
                orden.total_orden = total_servicios + total_productos
        else:
            messages.error(request, f'No se encontró el vehículo con placa/VIN "{busqueda}"')

    # Elegir template según rol
    if request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/buscar.html'
    else:
        template = 'gestion_vehicular/admin/seguimiento_vehicular/buscar.html'

    return render(request, template, {
        'vehiculo': vehiculo,
        'ordenes': ordenes,
        'placa': busqueda,
    })


def historial_vehiculo(request, placa):
    # 🔍 El parámetro "placa" puede ser placa O VIN
    vehiculo = get_object_or_404(
        Vehiculo,
        Q(placa__iexact=placa) | Q(vin__iexact=placa)
    )
    ordenes = OrdenTrabajo.objects.filter(id_vehiculo=vehiculo).order_by('-fecha_ingreso')

    for orden in ordenes:
        total_servicios = sum(d.precio_cobrado or 0 for d in orden.detalles_servicio.all())
        total_productos = sum(d.subtotal_precio or 0 for d in orden.detalles_producto.all())
        orden.total_orden = total_servicios + total_productos

    notas = NotaTecnica.objects.filter(id_vehiculo=vehiculo).order_by('-fecha')
    revisiones = RevisionTecnica.objects.filter(id_orden__id_vehiculo=vehiculo).order_by('-fecha_revision')
    ultima_revision = revisiones.first()
    total_gastado = (
        Pago.objects
        .filter(id_orden__id_vehiculo=vehiculo, estado_pago='COBRADO')
        .aggregate(Sum('monto_total'))['monto_total__sum'] or 0
    )

    if request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/historial.html'
    else:
        template = 'gestion_vehicular/admin/seguimiento_vehicular/historial.html'

    return render(request, template, {
        'vehiculo': vehiculo,
        'ordenes': ordenes,
        'notas': notas,
        'revisiones': revisiones,
        'ultima_revision': ultima_revision,
        'total_gastado': total_gastado,
    })


def revision_tecnica(request, orden_id):
    orden = get_object_or_404(OrdenTrabajo, id=orden_id)
    tipo = request.GET.get('tipo', 'COMPLETA')
    
    # Filtrar componentes según el tipo de revisión
    if tipo == 'VISITA':
        componentes = Componente.objects.filter(en_visita=True).order_by('orden')
    elif tipo == 'RAPIDA':
        componentes = Componente.objects.filter(en_rapida=True).order_by('orden')
    else:  # COMPLETA
        componentes = Componente.objects.filter(en_completa=True).order_by('orden')
    
    if request.method == 'POST':
        # ✅ Guardar con el tipo correcto (VISITA, RAPIDA o COMPLETA)
        revision = RevisionTecnica.objects.create(
            id_orden=orden,
            tipo_revision=request.POST.get('tipo_revision', tipo),
            fecha_revision=timezone.now()
        )
        
        for c in componentes:
            DetalleRevision.objects.create(
                id_revision=revision,
                id_componente=c,
                estado=request.POST.get(f'comp_{c.id}', 'OK'),
                nota=request.POST.get(f'nota_{c.id}', '')
            )
        
        # Cálculo del ISV
        total = revision.detalles.count()
        ok = revision.detalles.filter(estado='OK').count()
        regular = revision.detalles.filter(estado='REGULAR').count()
        revision.isv_porcentaje = round(((ok * 100) + (regular * 50)) / total, 2) if total > 0 else 0
        revision.save()
        
        messages.success(request, f'Revisión guardada. ISV: {revision.isv_porcentaje}%')
        return redirect('detalle_orden', orden_id=orden.id)
    
    # Elegir template según rol
    if request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/revision.html'
    else:  # ADMIN
        template = 'gestion_vehicular/admin/seguimiento_vehicular/revision.html'
    
    return render(request, template, {
        'orden': orden,
        'componentes': componentes,
        'notas_predefinidas': NotaPredefinida.objects.all(),
        'tipo': tipo,
    })


def registrar_hallazgo(request, orden_id):
    if request.method == 'POST':
        orden = get_object_or_404(OrdenTrabajo, id=orden_id)
        HallazgoAdicional.objects.create(
            id_orden=orden, 
            descripcion=request.POST.get('descripcion'), 
            costo_estimado=request.POST.get('costo_estimado', 0), 
            estado_autorizacion='PENDIENTE', 
            fecha_deteccion=timezone.now()
        )
        messages.success(request, 'Hallazgo registrado')
    return redirect('detalle_orden', orden_id=orden_id)


def autorizar_hallazgo(request, hallazgo_id):
    hallazgo = get_object_or_404(HallazgoAdicional, id=hallazgo_id)
    accion = request.GET.get('accion', request.POST.get('accion'))
    
    if accion == 'autorizar':
        hallazgo.estado_autorizacion = 'AUTORIZADO_CLIENTE'
        messages.success(request, 'Hallazgo aceptado')
    elif accion == 'rechazar':
        hallazgo.estado_autorizacion = 'RECHAZADO_CLIENTE'
        messages.warning(request, 'Hallazgo rechazado')
    else:
        if request.method == 'POST':
            hallazgo.estado_autorizacion = 'AUTORIZADO_CLIENTE' if request.POST.get('accion') == 'autorizar' else 'RECHAZADO_CLIENTE'
            messages.success(request, f'Hallazgo {hallazgo.estado_autorizacion}')
    
    hallazgo.fecha_resolucion = timezone.now()
    hallazgo.save()
    return redirect('detalle_orden', orden_id=hallazgo.id_orden.id)

def rechazar_hallazgo(request, hallazgo_id):
    hallazgo = get_object_or_404(HallazgoAdicional, id=hallazgo_id)
    hallazgo.estado_autorizacion = 'RECHAZADO_CLIENTE'
    hallazgo.fecha_resolucion = timezone.now()
    hallazgo.save()
    messages.warning(request, 'Hallazgo rechazado')
    return redirect('dashboard_admin')


##codigo 22/08/2026 23:59
def revision_rapida_placa(request):
    """Revisión rápida para vehículo nuevo (sin orden formal)"""
    placa = request.GET.get('placa', '')
    componentes = Componente.objects.filter(en_visita=True).order_by('orden')
    
    # ✅ Elegir template según rol
    if request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/revision_rapida.html'
    else:  # ADMIN
        template = 'gestion_vehicular/admin/seguimiento_vehicular/revision_rapida.html'
    
    return render(request, template, {
        'placa': placa,
        'componentes': componentes,
    })


def guardar_revision_rapida(request):
    """Guarda la revisión rápida como orden VISITA"""
    if request.method == 'POST':
        placa = request.POST.get('placa', '').upper()
        componentes = Componente.objects.filter(en_visita=True).order_by('orden')
        
        # Crear vehículo si no existe
        vehiculo, created = Vehiculo.objects.get_or_create(
            placa=placa,
            defaults={}
        )
        
        # Crear orden VISITA
        orden = OrdenTrabajo.objects.create(
            id_vehiculo=vehiculo,
            id_cliente=vehiculo.id_cliente,  # ✅ Asignar cliente si existe
            estado_orden='VISITA',
            fecha_ingreso=timezone.now(),
            fecha_creacion=timezone.now(),
        )
        
        # Crear revisión
        revision = RevisionTecnica.objects.create(
            id_orden=orden,
            tipo_revision='VISITA',
            fecha_revision=timezone.now(),
        )
        
        # Guardar componentes
        detalles = []
        estados = {'MALO': [], 'REGULAR': [], 'OK': []}
        
        for componente in componentes:
            estado = request.POST.get(f'comp_{componente.id}', 'OK')
            nota = request.POST.get(f'nota_{componente.id}', '')
            
            DetalleRevision.objects.create(
                id_revision=revision,
                id_componente=componente,
                estado=estado,
                nota=nota,
            )
            
            detalles.append({
                'nombre': componente.nombre,
                'estado': estado,
                'nota': nota
            })
            
            if estado in estados:
                estados[estado].append(componente.nombre)
        
        # Calcular porcentaje
        total = revision.detalles.count()
        ok = revision.detalles.filter(estado='OK').count()
        regular = revision.detalles.filter(estado='REGULAR').count()
        estado_porcentaje = round(((ok * 100) + (regular * 50)) / total, 2) if total > 0 else 0
        revision.isv_porcentaje = estado_porcentaje
        revision.save()
        
        # Guardar en sesión
        request.session['revision_detalle'] = {
            'porcentaje': estado_porcentaje,
            'resumen': estados,
            'componentes': detalles,
        }
        
        messages.success(request, f"Revisión guardada. Estado del vehículo: {estado_porcentaje}%")
        return redirect(f'/orden/crear/?visita_id={orden.id}&nueva_visita=1')
    
    return redirect('buscar_vehiculo')


def api_vehiculo_por_placa(request):
    """
    Devuelve datos del vehículo + cliente actual en JSON.
    Acepta ?placa=X o ?vin=Y (o ambos).
    """
    from django.db.models import Q

    placa = (request.GET.get('placa') or '').strip().upper()
    vin = (request.GET.get('vin') or '').strip().upper()

    if not placa and not vin:
        return JsonResponse({'existe': False})

    q = Q()
    if placa:
        q |= Q(placa__iexact=placa)
    if vin:
        q |= Q(vin__iexact=vin)

    vehiculo = (
        Vehiculo.objects
        .select_related('id_cliente')
        .filter(q)
        .first()
    )

    if not vehiculo:
        return JsonResponse({'existe': False})

    cliente = vehiculo.id_cliente
    return JsonResponse({
        'existe': True,
        'vehiculo': {
            'placa':  vehiculo.placa or '',
            'marca':  vehiculo.marca or '',
            'modelo': vehiculo.modelo or '',
            'anio':   vehiculo.anio or '',
            'color':  vehiculo.color or '',
            'vin':    vehiculo.vin or '',
            'kilometraje': vehiculo.kilometraje_actual or '',
        },
        'cliente': {
            'id':       cliente.id if cliente else None,
            'nombre':   cliente.nombre if cliente else '',
            'apellido': cliente.apellido if cliente else '',
            'telefono': cliente.telefono if cliente else '',
            'ci':       getattr(cliente, 'ci', '') if cliente else '',
        },
    })
