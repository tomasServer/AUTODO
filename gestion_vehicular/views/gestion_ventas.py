from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.db import connection
from ..models import Producto, VentaRapida, DetalleVentaRapida, Usuario, ClienteVenta
from decimal import Decimal

def venta_rapida(request):
    """Muestra el formulario de venta rápida"""
    productos = Producto.objects.filter(activo=True, stock_actual__gt=0).order_by('nombre')
    
    # Elegir template según rol
    if request.user.id_rol_id == 1:  # ADMIN
        template = 'gestion_vehicular/admin/gestion_ventas/venta_rapida.html'
    elif request.user.id_rol_id == 2:  # JEFE
        template = 'gestion_vehicular/jefe_mecanico/venta_rapida.html'
    else:  # AYUDANTE
        template = 'gestion_vehicular/ayudante/venta_rapida.html'
    
    return render(request, template, {
        'productos': productos,
    })



def guardar_venta_rapida(request):
    """Guarda la venta rápida y descuenta stock"""
    if request.method == 'POST':
        # entrada de datos 
        cliente_nombre = request.POST.get('cliente_nombre').strip()
        cliente_telefono = request.POST.get('cliente_telefono').strip()
        cliente_ci = request.POST.get('cliente_ci').strip()
        sin_registrar = request.POST.get('sin_registrar') == 'true'

        #BUSCAR
        cliente_venta = None

        if not sin_registrar:
            if cliente_telefono:
                cliente_venta = ClienteVenta.objects.filter(telefono=cliente_telefono).first()

                if not cliente_venta and (cliente_nombre or cliente_telefono):
                    cliente_venta = ClienteVenta.objects.create(
                        nombre=cliente_nombre if cliente_nombre else None,
                        telefono=cliente_telefono if cliente_telefono else None,
                        ci=cliente_ci if cliente_ci else None,
                    )






        venta = VentaRapida.objects.create(
            fecha_venta=timezone.now(),
            registrado_por=request.user if request.user.is_authenticated else None,
            id_cliente_venta=cliente_venta  #puede ser nulo
        )
        
        total = 0
        
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
                    
                    producto.stock_actual -= cantidad_int
                    producto.save()
                    
                    total += precio_float * cantidad_int
        
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