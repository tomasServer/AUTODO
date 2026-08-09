from .models import HallazgoAdicional

def notificaciones(request):
    """
    Agrega el contador de hallazgos pendientes a TODAS las paginas.
    """
    cantidad = HallazgoAdicional.objects.filter(
        estado_autorizacion='PENDIENTE'
    ).count()
    
    return {
        'hallazgos_pendientes_count': cantidad,
    }