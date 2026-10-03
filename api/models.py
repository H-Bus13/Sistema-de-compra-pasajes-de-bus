"""
=============================================================================
PROYECTO: Reservas de Pasajes de Buses Interurbanos (Transporte)
ALUMNO: Hugo Bustos Barra
SECCIÓN: IEC-N4-C1
AÑO: 2026
=============================================================================
DESCRIPCIÓN DE MODELOS:
- Usuario Custom (AbstractUser) con definición de Roles (Pasajero / Admin Flota).
- Terminal/Ciudad: Origen y destino de viajes.
- Ruta: Vincula origen y destino.
- Bus: Capacidad total, patente, número y estado activo (Soft Delete).
- Servicio: Itinerario puntual (Ruta + Bus + Fecha/Hora + Tarifa).
- AsientoServicio: Representa un asiento específico dentro de un servicio (con CHOICES de estado).
- CarroPasajes (1:1 con Usuario) e ItemCarro: Carro de compras persistente en PostgreSQL.
- Venta e ItemVenta: Histórico de transacciones (con CHOICES de estado) y emisión de Boletos.
=============================================================================
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone


# ---------------------------------------------------------------------------
# 1. MODELO DE USUARIO PERSONALIZADO (JWT + ROLES)
# ---------------------------------------------------------------------------
class Usuario(AbstractUser):
    """
    Modelo de usuario extendido para manejar los roles del sistema:
    - PASAJERO (Cliente)
    - ADMIN_FLOTA (Administrador de Flota)
    """
    class RolChoices(models.TextChoices):
        PASAJERO = 'PASAJERO', 'Pasajero'
        ADMIN_FLOTA = 'ADMIN_FLOTA', 'Administrador de Flota'

    rol = models.CharField(
        max_length=20,
        choices=RolChoices.choices,
        default=RolChoices.PASAJERO,
        verbose_name="Rol de Usuario"
    )

    def __str__(self):
        return f"{self.username} ({self.get_rol_display()})"


# ---------------------------------------------------------------------------
# 2. MODELOS DE INFRAESTRUCTURA DE TRANSPORTE
# ---------------------------------------------------------------------------
class Terminal(models.Model):
    """
    Representa una ciudad o terminal de buses.
    """
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Terminal / Ciudad")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad")

    def __str__(self):
        return f"{self.nombre} - {self.ciudad}"


class Ruta(models.Model):
    """
    Define el trayecto entre un terminal de origen y uno de destino.
    """
    origen = models.ForeignKey(Terminal, on_delete=models.CASCADE, related_name="rutas_origen")
    destino = models.ForeignKey(Terminal, on_delete=models.CASCADE, related_name="rutas_destino")
    duracion_estimada_horas = models.DecimalField(max_digits=4, decimal_places=2, help_text="Duración en horas")

    def __str__(self):
        return f"Ruta: {self.origen.ciudad} -> {self.destino.ciudad}"


class Bus(models.Model):
    """
    Vehículo asignado a los servicios de la flota.
    Soporta Soft Delete mediante el atributo 'activo'.
    """
    patente = models.CharField(max_length=10, unique=True, verbose_name="Patente")
    numero_bus = models.IntegerField(verbose_name="Número de Máquina")
    capacidad_asientos = models.PositiveIntegerField(default=40, verbose_name="Capacidad de Asientos")
    activo = models.BooleanField(default=True, verbose_name="Bus Activo / Operativo")

    def __str__(self):
        estado_str = "Operativo" if self.activo else "Inactivo/Taller"
        return f"Bus #{self.numero_bus} ({self.patente}) - [{estado_str}]"


# ---------------------------------------------------------------------------
# 3. MODELO DE SERVICIOS / ITINERARIOS Y ASIENTOS
# ---------------------------------------------------------------------------
class Servicio(models.Model):
    """
    Representa un viaje/itinerario programado.
    """
    ruta = models.ForeignKey(Ruta, on_delete=models.CASCADE, related_name="servicios")
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name="servicios")
    fecha_hora_salida = models.DateTimeField(verbose_name="Fecha y Hora de Salida")
    fecha_hora_llegada = models.DateTimeField(verbose_name="Fecha y Hora de Llegada Estimada")
    precio_base = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Base del Servicio")

    def __str__(self):
        return f"Servicio #{self.id}: {self.ruta} - {self.fecha_hora_salida.strftime('%d/%m/%Y %H:%M')}"


class AsientoServicio(models.Model):
    class TipoAsientoChoices(models.TextChoices):
        SEMICAMA = 'SEMICAMA', 'Semicama'
        CAMA = 'CAMA', 'Cama'

    class EstadoAsientoChoices(models.TextChoices):
        DISPONIBLE = 'DISPONIBLE', 'Disponible'
        RESERVADO_TEMPORAL = 'RESERVADO_TEMPORAL', 'Reservado Temporal'
        OCUPADO = 'OCUPADO', 'Ocupado'

    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name="asientos")
    numero_asiento = models.PositiveIntegerField(verbose_name="Número de Asiento")
    tipo = models.CharField(
        max_length=15,
        choices=TipoAsientoChoices.choices,
        default=TipoAsientoChoices.SEMICAMA,
        verbose_name="Tipo de Asiento"
    )
    tarifa = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Tarifa Específica")
    estado = models.CharField(
        max_length=20,
        choices=EstadoAsientoChoices.choices,
        default=EstadoAsientoChoices.DISPONIBLE,
        verbose_name="Estado de Disponibilidad"
    )
    
    bloqueado_hasta = models.DateTimeField(null=True, blank=True, verbose_name="Bloqueo Expiración")
    session_id = models.CharField(max_length=255, null=True, blank=True, verbose_name="ID Sesión Temporal")

    class Meta:
        unique_together = ('servicio', 'numero_asiento')

    def esta_bloqueado_o_comprado(self, current_session_id=None):
        if self.estado == self.EstadoAsientoChoices.OCUPADO:
            return True
            
        if self.estado == self.EstadoAsientoChoices.RESERVADO_TEMPORAL:
            if self.bloqueado_hasta and timezone.now() < self.bloqueado_hasta:
                if current_session_id and self.session_id == current_session_id:
                    return False
                return True
            else:
                self.estado = self.EstadoAsientoChoices.DISPONIBLE
                self.bloqueado_hasta = None
                self.session_id = None
                self.save()
                return False
                
        return False

    def __str__(self):
        return f"Asiento #{self.numero_asiento} ({self.get_tipo_display()}) - Servicio #{self.servicio.id} - [{self.get_estado_display()}]"


# ---------------------------------------------------------------------------
# 4. CARRO DE PASAJES PERSISTENTE (RELACIÓN 1 A 1 CON USUARIO)
# ---------------------------------------------------------------------------
class CarroPasajes(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carro_activo",
        verbose_name="Pasajero Propietario"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Carro Activo de {self.usuario.username}"


class ItemCarro(models.Model):
    carro = models.ForeignKey(CarroPasajes, on_delete=models.CASCADE, related_name="items")
    asiento_servicio = models.ForeignKey(AsientoServicio, on_delete=models.CASCADE)
    nombre_ocupante = models.CharField(max_length=150, verbose_name="Nombre Completo del Ocupante")
    identificacion_ocupante = models.CharField(max_length=20, verbose_name="RUT o Pasaporte")

    class Meta:
        unique_together = ('carro', 'asiento_servicio')

    def __str__(self):
        return f"Pasaje Asiento #{self.asiento_servicio.numero_asiento} para {self.nombre_ocupante}"


# ---------------------------------------------------------------------------
# 5. HISTÓRICO DE VENTAS Y EMISIÓN DE BOLETOS DE VIAJE
# ---------------------------------------------------------------------------
class Venta(models.Model):
    class EstadoVentaChoices(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        PAGADO = 'PAGADO', 'Pagado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="ventas"
    )
    
    nombre_comprador = models.CharField(max_length=100, default="Invitado", verbose_name="Nombre Comprador")
    apellido_comprador = models.CharField(max_length=100, default="", verbose_name="Apellido Comprador")
    email_comprador = models.EmailField(default="", verbose_name="Correo Comprador")
    telefono_comprador = models.CharField(max_length=20, default="", verbose_name="Teléfono Comprador")

    fecha_venta = models.DateTimeField(auto_now_add=True)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto Total")
    estado = models.CharField(
        max_length=15,
        choices=EstadoVentaChoices.choices,
        default=EstadoVentaChoices.PENDIENTE,
        verbose_name="Estado de Transacción"
    )

    def __str__(self):
        comprador = self.usuario.username if self.usuario else f"{self.nombre_comprador} {self.apellido_comprador}"
        return f"Venta #{self.id} - {comprador} - Total: ${self.monto_total} [{self.get_estado_display()}]"


class BoletoViaje(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="boletos")
    asiento_servicio = models.ForeignKey(AsientoServicio, on_delete=models.PROTECT)
    codigo_boleto = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nombre_ocupante = models.CharField(max_length=150)
    identificacion_ocupante = models.CharField(max_length=20)
    precio_pagado = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_emision = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Boleto {self.codigo_boleto} - Ocupante: {self.nombre_ocupante} - Asiento #{self.asiento_servicio.numero_asiento}"