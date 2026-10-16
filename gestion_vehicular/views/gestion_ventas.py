#@author:  Tomas Jonatan Lopez Cruz
#@email:   20461973hola@gmail.com
#@date:    2026-10-13    
#@version: 0.0.1
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages
from django.db import connection
from ..models import Producto, VentaRapida, DetalleVentaRapida, Usuario, Cliente
from decimal import Decimal
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa

def venta_rapida(request):
    """Muestra el formulario de venta rápida"""
    productos = Producto.objects.filter(activo=True, stock_actual__gt=0).order_by('nombre')
    clientes = Cliente.objects.all().order_by('nombre')  # ✅ Ahora usa Cliente
    
    if request.user.id_rol_id == 1:
        template = 'gestion_vehicular/admin/gestion_ventas/venta_rapida.html'
    elif request.user.id_rol_id == 2:
        template = 'gestion_vehicular/jefe_mecanico/venta_rapida.html'
    else:
        template = 'gestion_vehicular/ayudante/venta_rapida.html'
    
    return render(request, template, {
        'productos': productos,
        'clientes': clientes,  # ✅ Cambió el nombre
    })


def guardar_venta_rapida(request):
    """Guarda la venta rápida y descuenta stock"""
    if request.method == 'POST':
        # ====== DATOS DEL CLIENTE ======
        cliente_nombre = (request.POST.get('cliente_nombre') or '').strip()
        cliente_apellido = (request.POST.get('cliente_apellido') or '').strip()
        cliente_telefono = (request.POST.get('cliente_telefono') or '').strip()
        cliente_ci = (request.POST.get('cliente_ci') or '').strip()
        
        sin_registrar = (request.POST.get('sin_registrar') or '') == 'true'
        
        # ====== BUSCAR O CREAR CLIENTE ======
        cliente = None
        
        if not sin_registrar:
            # 1️⃣ BUSCAR POR CI
            if cliente_ci:
                cliente = Cliente.objects.filter(ci=cliente_ci).first()
                
                # Actualizar datos si ya existe
                if cliente:
                    if cliente_nombre:
                        cliente.nombre = cliente_nombre
                    if cliente_telefono:
                        cliente.telefono = cliente_telefono
                    cliente.save()
            
            # 2️⃣ Si no existe por CI, buscar por teléfono
            if not cliente and cliente_telefono:
                cliente = Cliente.objects.filter(telefono=cliente_telefono).first()
            
            # 3️⃣ Si no existe, crear uno nuevo
            if not cliente and (cliente_nombre or cliente_telefono or cliente_ci):
                cliente = Cliente.objects.create(
                    nombre=cliente_nombre or 'Cliente sin nombre',
                    apellido=cliente_apellido or None,
                    telefono=cliente_telefono if cliente_telefono else None,
                    ci=cliente_ci if cliente_ci else None,
                )
        
        # ====== CREAR LA VENTA ======
        venta = VentaRapida.objects.create(
            fecha_venta=timezone.now(),
            registrado_por=request.user if request.user.is_authenticated else None,
            id_cliente=cliente,  # ✅ Ahora apunta a Cliente
        )
        
        total = Decimal('0.00')
        
        # ====== GUARDAR PRODUCTOS ======
        for key in request.POST:
            if key.startswith('producto_') and not key.startswith('precio_producto_'):
                num = key.split('_')[-1]
                producto_id = request.POST.get(key)
                cantidad = request.POST.get(f'cantidad_{num}', '1')
                precio = request.POST.get(f'precio_producto_{num}', '0')
                
                if producto_id and cantidad:
                    producto = get_object_or_404(Producto, id=producto_id)
                    cantidad_int = int(cantidad)
                    precio_decimal = Decimal(precio) if precio else producto.precio_venta
                    
                    DetalleVentaRapida.objects.create(
                        id_venta=venta,
                        id_producto=producto,
                        cantidad=cantidad_int,
                        precio_venta=precio_decimal,
                    )
                    
                    producto.stock_actual -= cantidad_int
                    producto.save()
                    
                    total += precio_decimal * cantidad_int
        
        if total > 0:
            venta.total = total
            venta.save()
            messages.success(request, f'✅ Venta registrada. Total: Bs. {total}')
        else:
            messages.warning(request, '⚠️ No se seleccionaron productos')
        
        return redirect('venta_rapida')
    
    return redirect(f"/ventas/{venta.id}/?imprimir=1")



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





def venta_pdf(request, venta_id):
    """Genera el PDF de una venta rápida."""
    venta = get_object_or_404(VentaRapida, id=venta_id)
    detalles = venta.detalles.select_related('id_producto').all()

    html_string = render_to_string(
        'gestion_vehicular/admin/gestion_ventas/venta_pdf.html',
        {
            'venta': venta,
            'detalles': detalles,
        }
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="venta_{venta.id}.pdf"'

    pisa_status = pisa.CreatePDF(html_string, dest=response)

    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)

    return response