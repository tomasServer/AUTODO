from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.db import connection
from ..models import Producto, VentaRapida, DetalleVentaRapida, Usuario


def venta_rapida(request):
    """Muestra el formulario de venta rápida"""
    productos = Producto.objects.filter(activo=True, stock_actual__gt=0).order_by('nombre')
    
    return render(request, 'gestion_vehicular/admin/gestion_ventas/venta_rapida.html', {
        'productos': productos,
    })


def guardar_venta_rapida(request):
    """Guarda la venta rápida y descuenta stock"""
    if request.method == 'POST':
        # Crear venta rápida
        venta = VentaRapida.objects.create(
            fecha_venta=timezone.now(),
            registrado_por=request.user if request.user.is_authenticated else None,
        )
        
        total = 0
        productos_vendidos = []
        
        # Recorrer los productos enviados
        for key in request.POST:
            if key.startswith('producto_') and not key.startswith('precio_producto_'):
                num = key.split('_')[-1]
                producto_id = request.POST.get(key)
                cantidad = request.POST.get(f'cantidad_{num}', '1')
                precio = request.POST.get(f'precio_producto_{num}', '0')
                
                if producto_id and cantidad:
                    producto = get_object_or_404(Producto, id=producto_id)
                    cantidad_int = int(cantidad)
                    precio_float = float(precio) if precio else float(producto.precio_venta)
                    
                    DetalleVentaRapida.objects.create(
                        id_venta=venta,
                        id_producto=producto,
                        cantidad=cantidad_int,
                        precio_venta=precio_float,
                    )
                    
                    # Descontar stock
                    producto.stock_actual -= cantidad_int
                    producto.save()
                    
                    total += precio_float * cantidad_int
                    productos_vendidos.append(f"{producto.nombre} x{cantidad_int}")
        
        if total > 0:
            venta.total = total
            venta.save()
            messages.success(request, f'Venta registrada. Total: Bs. {total}')
        else:
            messages.warning(request, 'No se seleccionaron productos')
        
        return redirect('venta_rapida')
    
    return redirect('venta_rapida')


def lista_ventas_rapidas(request):
    """Lista las ventas rápidas del día"""
    ventas = VentaRapida.objects.all().order_by('-fecha_venta')[:50]
    
    return render(request, 'gestion_vehicular/admin/gestion_ventas/ventas_lista.html', {
        'ventas': ventas,
    })

def detalle_venta(request, venta_id):
    """Muestra el detalle de una venta rápida"""
    venta = get_object_or_404(VentaRapida, id=venta_id)
    
    return render(request, 'gestion_vehicular/admin/gestion_ventas/detalle_venta.html', {
        'venta': venta,
    })