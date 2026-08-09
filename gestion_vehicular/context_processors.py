from .models import HallazgoAdicional
from django.db import DatabaseError

def notificaciones(request):
    """
    Agrega el contador de hallazgos pendientes a TODAS las paginas.
    Protegido con try/except para evitar caídas si la tabla no existe en la BD.
    """
    try:
        cantidad = HallazgoAdicional.objects.filter(
            estado_autorizacion='PENDIENTE'
        ).count()
    except Exception:
        # Si la tabla no existe aún en la BD o falla la conexión,
        # retorna 0 para no tumbar la aplicación ni el /login/
        cantidad = 0

    return {
        'hallazgos_pendientes_count': cantidad,
    }