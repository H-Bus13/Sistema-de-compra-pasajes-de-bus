"""
=============================================================================
PROYECTO: Reservas de Pasajes de Buses Interurbanos (Transporte)
ALUMNO: Hugo Bustos Barra
SECCIÓN: IEC-N4-C1
AÑO: 2026
=============================================================================
DESCRIPCIÓN DE SERIALIZADORES:
- CustomTokenObtainPairSerializer: Inyecta claims personalizadas (rol, username) al JWT.
- Serializadores CRUD para Terminal, Ruta, Bus, Servicio y AsientoServicio.
- ItemCarroSerializer y CarroPasajesSerializer: Gestiona el carro persistente con datos de ocupantes.
- CheckoutSerializer, BoletoViajeSerializer y VentaSerializer: Manejo de la transacción y emisión.
=============================================================================
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError

from .models import (
    Terminal, Ruta, Bus, Servicio, AsientoServicio,
    CarroPasajes, ItemCarro, Venta, BoletoViaje
)

Usuario = get_user_model()


# ---------------------------------------------------------------------------
# 1. SERIALIZADOR JWT CON CUSTOM CLAIMS
# ---------------------------------------------------------------------------
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['email'] = user.email
        token['rol'] = getattr(user, 'rol', 'PASAJERO')
        return token


# ---------------------------------------------------------------------------
# 2. SERIALIZADORES DE USUARIO Y CATÁLOGO DE TRANSPORTES
# ---------------------------------------------------------------------------
class UsuarioRegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name', 'rol']
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True}
        }

    def validate_username(self, value):
        if not value:
            raise serializers.ValidationError("El nombre de usuario/correo es obligatorio.")

        if Usuario.objects.filter(username=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta registrada con este correo electrónico.")

        return value

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("El correo electrónico es obligatorio.")
        
        try:
            validate_email(value)
        except DjangoValidationError:
            raise serializers.ValidationError("Ingrese una dirección de correo electrónico válida (ej: usuario@dominio.cl).")

        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado con otra cuenta.")

        return value

    def create(self, validated_data):
        email = validated_data.get('email') or validated_data.get('username')
        username = validated_data.get('username') or email

        try:
            user = Usuario.objects.create_user(
                username=username,
                email=email,
                password=validated_data['password'],
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
                rol=validated_data.get('rol', getattr(Usuario, 'RolChoices', None).PASAJERO if hasattr(Usuario, 'RolChoices') else 'PASAJERO')
            )
            CarroPasajes.objects.get_or_create(usuario=user)
            return user
        except IntegrityError:
            raise serializers.ValidationError({
                "email": "Ya existe una cuenta registrada con este correo electrónico."
            })


class TerminalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Terminal
        fields = '__all__'


class RutaSerializer(serializers.ModelSerializer):
    # Definimos origen y destino como CharField write_only para aceptar texto o ID entero
    origen = serializers.CharField(write_only=True)
    destino = serializers.CharField(write_only=True)

    # Detalle en JSON para lecturas (GET)
    origen_detalle = TerminalSerializer(source='origen', read_only=True)
    destino_detalle = TerminalSerializer(source='destino', read_only=True)

    class Meta:
        model = Ruta
        fields = ['id', 'origen', 'destino', 'origen_detalle', 'destino_detalle', 'duracion_estimada_horas']

    def create(self, validated_data):
        origen_val = validated_data.pop('origen')
        destino_val = validated_data.pop('destino')

        # 1. Resolver Origen (por ID entero o por Nombre de Ciudad)
        if str(origen_val).isdigit():
            terminal_origen = Terminal.objects.get(pk=int(origen_val))
        else:
            nombre_ciudad = str(origen_val).strip().title()
            terminal_origen, _ = Terminal.objects.get_or_create(
                ciudad__iexact=nombre_ciudad,
                defaults={'nombre': f"Terminal {nombre_ciudad}", 'ciudad': nombre_ciudad}
            )

        # 2. Resolver Destino (por ID entero o por Nombre de Ciudad)
        if str(destino_val).isdigit():
            terminal_destino = Terminal.objects.get(pk=int(destino_val))
        else:
            nombre_ciudad = str(destino_val).strip().title()
            terminal_destino, _ = Terminal.objects.get_or_create(
                ciudad__iexact=nombre_ciudad,
                defaults={'nombre': f"Terminal {nombre_ciudad}", 'ciudad': nombre_ciudad}
            )

        # 3. Crear el objeto Ruta en la base de datos
        duracion = validated_data.get('duracion_estimada_horas', 0)
        return Ruta.objects.create(
            origen=terminal_origen,
            destino=terminal_destino,
            duracion_estimada_horas=duracion
        )


class BusSerializer(serializers.ModelSerializer):
    """
    Serializador para la gestión integral del modelo Bus (CRUD Administrador de Flota).
    Incluye el campo 'activo' para soft-delete.
    """
    class Meta:
        model = Bus
        fields = ['id', 'patente', 'numero_bus', 'capacidad_asientos', 'activo']


class AsientoServicioSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = AsientoServicio
        fields = ['id', 'servicio', 'numero_asiento', 'tipo', 'tipo_display', 'tarifa', 'estado', 'estado_display', 'session_id']


class ServicioSerializer(serializers.ModelSerializer):
    ruta_detalle = RutaSerializer(source='ruta', read_only=True)
    bus_detalle = BusSerializer(source='bus', read_only=True)

    class Meta:
        model = Servicio
        fields = ['id', 'ruta', 'bus', 'ruta_detalle', 'bus_detalle', 'fecha_hora_salida', 'fecha_hora_llegada', 'precio_base']


# ---------------------------------------------------------------------------
# 3. SERIALIZADORES DEL CARRO DE PASAJES PERSISTENTE
# ---------------------------------------------------------------------------
class ItemCarroSerializer(serializers.ModelSerializer):
    asiento_detalle = AsientoServicioSerializer(source='asiento_servicio', read_only=True)

    class Meta:
        model = ItemCarro
        fields = ['id', 'asiento_servicio', 'asiento_detalle', 'nombre_ocupante', 'identificacion_ocupante']

    def validate_asiento_servicio(self, value):
        if value.estado == AsientoServicio.EstadoAsientoChoices.OCUPADO:
            raise serializers.ValidationError("El asiento seleccionado ya se encuentra ocupado por otro pasajero.")
        return value


class CarroPasajesSerializer(serializers.ModelSerializer):
    items = ItemCarroSerializer(many=True, read_only=True)
    total_carro = serializers.SerializerMethodField()

    class Meta:
        model = CarroPasajes
        fields = ['id', 'usuario', 'fecha_actualizacion', 'items', 'total_carro']

    def get_total_carro(self, obj):
        return sum(item.asiento_servicio.tarifa for item in obj.items.all())


# ---------------------------------------------------------------------------
# 4. SERIALIZADORES DE VENTAS, CHECKOUT Y BOLETOS
# ---------------------------------------------------------------------------
class BoletoViajeSerializer(serializers.ModelSerializer):
    asiento_numero = serializers.IntegerField(source='asiento_servicio.numero_asiento', read_only=True)
    servicio_info = serializers.CharField(source='asiento_servicio.servicio.__str__', read_only=True)

    class Meta:
        model = BoletoViaje
        fields = [
            'id', 'codigo_boleto', 'nombre_ocupante', 'identificacion_ocupante',
            'precio_pagado', 'fecha_emision', 'asiento_numero', 'servicio_info'
        ]


class VentaSerializer(serializers.ModelSerializer):
    boletos = BoletoViajeSerializer(many=True, read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Venta
        fields = ['id', 'usuario', 'fecha_venta', 'monto_total', 'estado', 'estado_display', 'boletos']


class ActualizarEstadoVentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venta
        fields = ['estado']


class BloquearAsientosSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=255)
    asientos_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )

class OcupanteInfoSerializer(serializers.Serializer):
    asiento_id = serializers.IntegerField()
    nombre_ocupante = serializers.CharField(max_length=150)
    identificacion_ocupante = serializers.CharField(max_length=20)

class CheckoutInvitadoSerializer(serializers.Serializer):
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100)
    correo = serializers.EmailField()
    telefono = serializers.CharField(max_length=20)
    session_id = serializers.CharField(max_length=255)
    ocupantes = OcupanteInfoSerializer(many=True)