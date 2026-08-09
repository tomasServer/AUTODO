from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Sum
from django.contrib import messages
from ..models import *


def buscar_vehiculo(request):
    placa = request.GET.get('placa', '')
    vehiculo = None
    ordenes = None
    
    if placa:
        try:
            vehiculo = Vehiculo.objects.get(placa__iexact=placa)
            ordenes = OrdenTrabajo.objects.filter(id_vehiculo=vehiculo).order_by('-fecha_ingreso')[:5]
            
            # Calcular total de cada orden
            for orden in ordenes:
                total_servicios = sum(d.precio_cobrado or 0 for d in orden.detalles_servicio.all())
                total_productos = sum(d.subtotal_precio or 0 for d in orden.detalles_producto.all())
                orden.total_orden = total_servicios + total_productos
                
        except Vehiculo.DoesNotExist:
            messages.error(request, f'No se encontro el vehiculo "{placa}"')
            
    return render(request, 'gestion_vehicular/admin/seguimiento_vehicular/buscar.html', {
        'vehiculo': vehiculo, 
        'ordenes': ordenes, 
        'placa': placa
    })


def historial_vehiculo(request, placa):
    vehiculo = get_object_or_404(Vehiculo, placa__iexact=placa)
    ordenes = OrdenTrabajo.objects.filter(id_vehiculo=vehiculo).order_by('-fecha_ingreso')
    
    # Calcular total de cada orden
    for orden in ordenes:
        total_servicios = sum(d.precio_cobrado or 0 for d in orden.detalles_servicio.all())
        total_productos = sum(d.subtotal_precio or 0 for d in orden.detalles_producto.all())
        orden.total_orden = total_servicios + total_productos
    
    notas = NotaTecnica.objects.filter(id_vehiculo=vehiculo).order_by('-fecha')
    revisiones = RevisionTecnica.objects.filter(id_orden__id_vehiculo=vehiculo).order_by('-fecha_revision')
    ultima_revision = revisiones.first()
    total_gastado = Pago.objects.filter(id_orden__id_vehiculo=vehiculo, estado_pago='COBRADO').aggregate(Sum('monto_total'))['monto_total__sum'] or 0
    
    return render(request, 'gestion_vehicular/admin/seguimiento_vehicular/historial.html', {
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
    componentes = Componente.objects.filter(orden__lte=5).order_by('orden') if tipo == 'RAPIDA' else Componente.objects.all().order_by('orden')
    
    if request.method == 'POST':
        revision = RevisionTecnica.objects.create(id_orden=orden, tipo_revision=request.POST.get('tipo_revision', 'COMPLETA'), fecha_revision=timezone.now())
        for c in componentes:
            DetalleRevision.objects.create(id_revision=revision, id_componente=c, estado=request.POST.get(f'comp_{c.id}', 'OK'), nota=request.POST.get(f'nota_{c.id}', ''))
        total = revision.detalles.count()
        ok = revision.detalles.filter(estado='OK').count()
        regular = revision.detalles.filter(estado='REGULAR').count()
        revision.isv_porcentaje = round(((ok * 100) + (regular * 50)) / total, 2) if total > 0 else 0
        revision.save()
        messages.success(request, f'Revision guardada. ISV: {revision.isv_porcentaje}%')
        return redirect('detalle_orden', orden_id=orden.id)
    
    return render(request, 'gestion_vehicular/admin/seguimiento_vehicular/revision.html', {
        'orden': orden, 'componentes': componentes, 'notas_predefinidas': NotaPredefinida.objects.all(), 'tipo': tipo,
    })


def registrar_hallazgo(request, orden_id):
    if request.method == 'POST':
        orden = get_object_or_404(OrdenTrabajo, id=orden_id)
        HallazgoAdicional.objects.create(id_orden=orden, descripcion=request.POST.get('descripcion'), costo_estimado=request.POST.get('costo_estimado', 0), estado_autorizacion='PENDIENTE', fecha_deteccion=timezone.now())
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
