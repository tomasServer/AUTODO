from django.contrib import admin
from .models import *

# Register your models here.

# Registrar todos los modelos
admin.site.register(Rol)
admin.site.register(Usuario)
admin.site.register(Cliente)
admin.site.register(Vehiculo)
admin.site.register(TipoServicio)
admin.site.register(Complejidad)
admin.site.register(Componente)
admin.site.register(Servicio)
admin.site.register(Producto)
admin.site.register(OrdenTrabajo)
admin.site.register(DetalleServicio)
admin.site.register(DetalleProducto)
admin.site.register(HallazgoAdicional)
admin.site.register(RevisionTecnica)
admin.site.register(DetalleRevision)
admin.site.register(HistorialEstadoOrden)
admin.site.register(Pago)
admin.site.register(NotaPredefinida)
admin.site.register(VentaRapida)
admin.site.register(DetalleVentaRapida)
admin.site.register(ClienteVenta)