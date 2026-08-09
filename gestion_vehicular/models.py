from django.db import models


class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    fecha_registro = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cliente'

    def __str__(self):
        return f"{self.nombre} {self.apellido or ''}".strip()


class Complejidad(models.Model):
    nombre = models.CharField(max_length=50)
    factor_precio = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    tiempo_extra_minutos = models.IntegerField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'complejidad'

    def __str__(self):
        return self.nombre


class Componente(models.Model):
    nombre = models.CharField(max_length=100)
    orden = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'componente'

    def __str__(self):
        return self.nombre


class NotaPredefinida(models.Model):
    id_componente = models.ForeignKey(Componente, models.DO_NOTHING, db_column='id_componente')
    estado = models.CharField(max_length=20)
    texto = models.CharField(max_length=200)

    class Meta:
        managed = False
        db_table = 'nota_predefinida'

    def __str__(self):
        return f"[{self.estado}] {self.texto[:50]}"


class DetalleProducto(models.Model):
    id_orden = models.ForeignKey('OrdenTrabajo', models.DO_NOTHING, db_column='id_orden', related_name='detalles_producto')
    id_producto = models.ForeignKey('Producto', models.DO_NOTHING, db_column='id_producto')
    cantidad = models.IntegerField()
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal_costo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    subtotal_precio = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    registrado_por = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='registrado_por', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'detalle_producto'

    def __str__(self):
        return f"Producto en orden {self.id_orden_id}"


class DetalleRevision(models.Model):
    id_revision = models.ForeignKey('RevisionTecnica', models.DO_NOTHING, db_column='id_revision', related_name='detalles')
    id_componente = models.ForeignKey(Componente, models.DO_NOTHING, db_column='id_componente')
    estado = models.CharField(max_length=20)
    nota = models.TextField(blank=True, null=True)
    foto_ruta = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'detalle_revision'

    def __str__(self):
        return f"{self.id_componente.nombre}: {self.estado}"


class DetalleServicio(models.Model):
    id_orden = models.ForeignKey('OrdenTrabajo', models.DO_NOTHING, db_column='id_orden', related_name='detalles_servicio')
    id_servicio = models.ForeignKey('Servicio', models.DO_NOTHING, db_column='id_servicio')
    id_mecanico = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='id_mecanico', blank=True, null=True)
    precio_cobrado = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    costo_real = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    estado = models.CharField(max_length=30, blank=True, null=True)
    fecha_inicio = models.DateTimeField(blank=True, null=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'detalle_servicio'

    def __str__(self):
        return f"{self.id_servicio.nombre if self.id_servicio else ''} en orden {self.id_orden_id}"


class HallazgoAdicional(models.Model):
    id_orden = models.ForeignKey('OrdenTrabajo', models.DO_NOTHING, db_column='id_orden', related_name='hallazgos')
    id_mecanico = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='id_mecanico', blank=True, null=True)
    descripcion = models.TextField()
    costo_estimado = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    estado_autorizacion = models.CharField(max_length=30, blank=True, null=True)
    fecha_deteccion = models.DateTimeField(blank=True, null=True)
    fecha_resolucion = models.DateTimeField(blank=True, null=True)
    resuelto_por = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='resuelto_por', related_name='hallazgos_resueltos', blank=True, null=True)
    foto_ruta = models.TextField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'hallazgo_adicional'

    def __str__(self):
        return f"Hallazgo en orden {self.id_orden_id}"


class HistorialEstadoOrden(models.Model):
    id_orden = models.ForeignKey('OrdenTrabajo', models.DO_NOTHING, db_column='id_orden')
    estado_anterior = models.CharField(max_length=30, blank=True, null=True)
    estado_nuevo = models.CharField(max_length=30)
    cambiado_por = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='cambiado_por', blank=True, null=True)
    fecha_cambio = models.DateTimeField(blank=True, null=True)
    comentario = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'historial_estado_orden'

    def __str__(self):
        return f"Orden {self.id_orden_id}: {self.estado_anterior} -> {self.estado_nuevo}"


class NotaTecnica(models.Model):
    id_vehiculo = models.ForeignKey('Vehiculo', models.DO_NOTHING, db_column='id_vehiculo', related_name='notas_tecnicas')
    id_usuario = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='id_usuario', blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)
    tipo = models.CharField(max_length=30)
    titulo = models.CharField(max_length=200, blank=True, null=True)
    descripcion = models.TextField()
    visible_en_proxima = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'nota_tecnica'

    def __str__(self):
        return f"Nota: {self.titulo or self.tipo}"


class OrdenTrabajo(models.Model):
    id_vehiculo = models.ForeignKey('Vehiculo', models.DO_NOTHING, db_column='id_vehiculo')
    id_jefe_tecnico = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='id_jefe_tecnico', blank=True, null=True, related_name='ordenes_supervisadas')
    id_tipo_servicio = models.ForeignKey('TipoServicio', models.DO_NOTHING, db_column='id_tipo_servicio', blank=True, null=True)
    id_complejidad = models.ForeignKey(Complejidad, models.DO_NOTHING, db_column='id_complejidad', blank=True, null=True)
    id_servicio = models.ForeignKey('Servicio', models.DO_NOTHING, db_column='id_servicio', blank=True, null=True)
    fecha_ingreso = models.DateTimeField(blank=True, null=True)
    fecha_finalizacion = models.DateTimeField(blank=True, null=True)
    estado_orden = models.CharField(max_length=30, blank=True, null=True)
    observacion_general = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='creado_por', related_name='ordenes_creadas', blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'orden_trabajo'

    def __str__(self):
        return f"Orden #{self.id} - {self.id_vehiculo.placa if self.id_vehiculo else ''}"


class Pago(models.Model):
    id_orden = models.ForeignKey(OrdenTrabajo, models.DO_NOTHING, db_column='id_orden', related_name='pago')
    monto_total_servicios = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    monto_total_productos = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    monto_total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=50, blank=True, null=True)
    estado_pago = models.CharField(max_length=30, blank=True, null=True)
    fecha_pago = models.DateTimeField(blank=True, null=True)
    cobrado_por = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='cobrado_por', blank=True, null=True)
    comprobante = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pago'

    def __str__(self):
        return f"Pago orden #{self.id_orden_id}: Bs. {self.monto_total}"


class Producto(models.Model):
    codigo = models.CharField(unique=True, max_length=50, blank=True, null=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    stock_actual = models.IntegerField(blank=True, null=True)
    activo = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'producto'

    def __str__(self):
        return f"{self.codigo or ''} - {self.nombre}"


class RevisionTecnica(models.Model):
    id_orden = models.ForeignKey(OrdenTrabajo, models.DO_NOTHING, db_column='id_orden', related_name='revisiones')
    id_mecanico = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='id_mecanico', blank=True, null=True)
    tipo_revision = models.CharField(max_length=30)
    fecha_revision = models.DateTimeField(blank=True, null=True)
    isv_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'revision_tecnica'

    def __str__(self):
        return f"Revision {self.tipo_revision} - Orden #{self.id_orden_id}"


class Rol(models.Model):
    nombre = models.CharField(unique=True, max_length=50)

    class Meta:
        managed = False
        db_table = 'rol'

    def __str__(self):
        return self.nombre


class Servicio(models.Model):
    id_tipo_servicio = models.ForeignKey('TipoServicio', models.DO_NOTHING, db_column='id_tipo_servicio', blank=True, null=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    costo_mano_obra = models.DecimalField(max_digits=10, decimal_places=2)
    precio_mano_obra = models.DecimalField(max_digits=10, decimal_places=2)
    tiempo_estimado_minutos = models.IntegerField(blank=True, null=True)
    activo = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'servicio'

    def __str__(self):
        return self.nombre


class TipoServicio(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tipo_servicio'

    def __str__(self):
        return self.nombre


class Usuario(models.Model):
    id_rol = models.ForeignKey(Rol, models.DO_NOTHING, db_column='id_rol')
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, blank=True, null=True)
    ci = models.CharField(unique=True, max_length=20, blank=True, null=True)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    usuario_login = models.CharField(unique=True, max_length=50)
    contrasena_hash = models.CharField(max_length=255)
    activo = models.BooleanField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    last_login = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usuario'

    def __str__(self):
        return f"{self.usuario_login} ({self.nombre} {self.apellido or ''})"

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return self.activo

    @property
    def is_staff(self):
        return self.id_rol_id == 1  # 1 = ADMINISTRADOR

    @property
    def is_superuser(self):
        return self.id_rol_id == 1  # 1 = ADMINISTRADOR
    

    def get_username(self):
        return self.usuario_login

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.contrasena_hash = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.contrasena_hash)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido or ''}".strip()

    def has_perm(self, perm, obj=None):
        return True

    def has_perms(self, perm_list, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

class Vehiculo(models.Model):
    id_cliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='id_cliente', blank=True, null=True)
    placa = models.CharField(unique=True, max_length=20)
    marca = models.CharField(max_length=50, blank=True, null=True)
    modelo = models.CharField(max_length=50, blank=True, null=True)
    anio = models.IntegerField(blank=True, null=True)
    color = models.CharField(max_length=30, blank=True, null=True)
    vin = models.CharField(unique=True, max_length=50, blank=True, null=True)
    kilometraje_actual = models.IntegerField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'vehiculo'

    def __str__(self):
        return f"{self.placa} - {self.marca or ''} {self.modelo or ''}"