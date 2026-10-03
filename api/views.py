"""
=============================================================================
PROYECTO: Reservas de Pasajes de Buses Interurbanos (Transporte)
ALUMNO: Hugo Bustos Barra
SECCIÓN: IEC-N4-C1
AÑO: 2026
=============================================================================
"""

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from datetime import timedelta
from django.utils import timezone
from django.views import View
    
from .models import (
    Usuario, Terminal, Ruta, Bus, Servicio, AsientoServicio,
    CarroPasajes, ItemCarro, Venta, BoletoViaje
)
from .serializers import (
    UsuarioRegistroSerializer, TerminalSerializer, RutaSerializer, BusSerializer,
    ServicioSerializer, AsientoServicioSerializer, ItemCarroSerializer,
    CarroPasajesSerializer, VentaSerializer, BoletoViajeSerializer,
    ActualizarEstadoVentaSerializer, BloquearAsientosSerializer, CheckoutInvitadoSerializer
)
from .permissions import IsPasajero, IsAdminFlota
from .filters import ServicioFilter
from django.db.models import Q

#=============================================================================
# 0. CONTROLADOR Y VALIDACIÓN DEL PANEL DE ADMINISTRACIÓN DE FLOTA
#=============================================================================
def es_administrador_flota(user):
    return user.is_authenticated and (
        user.is_superuser or 
        user.is_staff or 
        getattr(user, 'rol', '') == Usuario.RolChoices.ADMIN_FLOTA
    )

@user_passes_test(es_administrador_flota, login_url='/', redirect_field_name=None)
def admin_flota_view(request):
    return render(request, 'panel_flota.html')

# ---------------------------------------------------------------------------
# 1. AUTENTICACIÓN Y REGISTRO DE USUARIOS
# ---------------------------------------------------------------------------
class RegistroUsuarioView(generics.CreateAPIView):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioRegistroSerializer
    permission_classes = [permissions.AllowAny]


class LoginPasajeroApiView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identificador = request.data.get('correo') or request.data.get('username')
        password = request.data.get('password')

        if not identificador or not password:
            return Response(
                {"error": "Debes ingresar tu correo/usuario y contraseña."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user_obj = Usuario.objects.filter(
            Q(username__iexact=identificador) | Q(email__iexact=identificador)
        ).first()

        if user_obj is None:
            return Response(
                {"error": "Credenciales inválidas. Verifica tu correo/usuario y contraseña."}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            return Response(
                {"error": "Contraseña incorrecta."}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {"error": "Esta cuenta se encuentra desactivada."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        login(request, user)

        return Response({
            "mensaje": f"¡Bienvenido/a {user.first_name or user.username}!",
            "usuario": {
                "id": user.id,
                "username": user.username,
                "nombre": user.first_name,
                "apellido": user.last_name,
                "email": user.email,
                "rol": user.rol
            }
        }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# 2. ENDPOINTS PÚBLICOS (CATÁLOGO Y ASIENTOS)
# ---------------------------------------------------------------------------
class BuscarServiciosView(generics.ListAPIView):
    """
    GET /api/servicios/buscar/
    Acceso PÚBLICO: Lista servicios filtrables por ciudad origen, ciudad destino y fecha.
    Filtra automáticamente solo los servicios cuyo bus asignado esté ACTIVO.
    """
    serializer_class = ServicioSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_class = ServicioFilter

    def get_queryset(self):
        return Servicio.objects.filter(bus__activo=True).order_by('fecha_hora_salida')


class AsientosServicioView(generics.ListAPIView):
    serializer_class = AsientoServicioSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        servicio_id = self.kwargs.get('pk')
        return AsientoServicio.objects.filter(servicio_id=servicio_id).order_by('numero_asiento')


# ---------------------------------------------------------------------------
# 3. ENDPOINTS DEL PASAJERO (CARRO PERSISTENTE, CHECKOUT Y BOLETOS)
# ---------------------------------------------------------------------------
class CarroPasajesView(APIView):
    permission_classes = [IsPasajero]

    def get(self, request):
        carro, _ = CarroPasajes.objects.get_or_create(usuario=request.user)
        serializer = CarroPasajesSerializer(carro)
        return Response(serializer.data)

    def post(self, request):
        carro, _ = CarroPasajes.objects.get_or_create(usuario=request.user)
        serializer = ItemCarroSerializer(data=request.data)
        
        if serializer.is_valid():
            asiento = serializer.validated_data['asiento_servicio']
            
            if asiento.estado == AsientoServicio.EstadoAsientoChoices.OCUPADO:
                return Response(
                    {"error": "El asiento ya se encuentra ocupado por otro usuario."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if ItemCarro.objects.filter(carro=carro, asiento_servicio=asiento).exists():
                return Response(
                    {"error": "El asiento ya fue agregado previamente a tu carro."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer.save(carro=carro)
            return Response(CarroPasajesSerializer(carro).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        carro, _ = CarroPasajes.objects.get_or_create(usuario=request.user)
        item_id = request.data.get('item_id') or request.query_params.get('item_id')

        if item_id:
            item = ItemCarro.objects.filter(carro=carro, id=item_id).first()
            if item:
                item.delete()
                return Response({"mensaje": f"Ítem {item_id} eliminado del carro."})
            return Response({"error": "Ítem no encontrado en el carro."}, status=status.HTTP_404_NOT_FOUND)
        
        carro.items.all().delete()
        return Response({"mensaje": "Carro de pasajes vaciado correctamente."})


class CheckoutVentaView(APIView):
    permission_classes = [IsPasajero]

    @transaction.atomic
    def post(self, request):
        carro, _ = CarroPasajes.objects.get_or_create(usuario=request.user)
        items = carro.items.select_related('asiento_servicio').all()

        if not items.exists():
            return Response({"error": "El carro de pasajes está vacío."}, status=status.HTTP_400_BAD_REQUEST)

        for item in items:
            asiento = AsientoServicio.objects.select_for_update().get(id=item.asiento_servicio.id)
            
            if asiento.estado == AsientoServicio.EstadoAsientoChoices.OCUPADO:
                return Response(
                    {"error": f"El asiento #{asiento.numero_asiento} del servicio {asiento.servicio.id} acaba de ser comprado por otro usuario."},
                    status=status.HTTP_409_CONFLICT
                )

        monto_total = sum(item.asiento_servicio.tarifa for item in items)

        venta = Venta.objects.create(
            usuario=request.user,
            monto_total=monto_total,
            estado=Venta.EstadoVentaChoices.PAGADO
        )

        boletos_creados = []
        for item in items:
            asiento = item.asiento_servicio
            asiento.estado = AsientoServicio.EstadoAsientoChoices.OCUPADO
            asiento.save()

            boleto = BoletoViaje.objects.create(
                venta=venta,
                asiento_servicio=asiento,
                nombre_ocupante=item.nombre_ocupante,
                identificacion_ocupante=item.identificacion_ocupante,
                precio_pagado=asiento.tarifa
            )
            boletos_creados.append(boleto)

        items.delete()

        serializer = VentaSerializer(venta)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MisBoletosView(generics.ListAPIView):
    serializer_class = BoletoViajeSerializer
    permission_classes = [IsPasajero]

    def get_queryset(self):
        return BoletoViaje.objects.filter(venta__usuario=self.request.user).order_by('-fecha_emision')


# ---------------------------------------------------------------------------
# 4. ENDPOINTS DEL ADMINISTRADOR DE FLOTA
# ---------------------------------------------------------------------------
class BusViewSet(viewsets.ModelViewSet):
    """
    GET, POST, PUT, PATCH, DELETE /api/buses/
    Acceso ADMINISTRADOR DE FLOTA: CRUD de buses con Soft Delete.
    """
    queryset = Bus.objects.all().order_by('numero_bus')
    serializer_class = BusSerializer
    permission_classes = [IsAdminFlota]

    def perform_destroy(self, instance):
        # Soft Delete: Inactiva el bus en lugar de borrarlo físicamente
        instance.activo = False
        instance.save()


class RutaViewSet(viewsets.ModelViewSet):
    """
    GET, POST, PUT, PATCH, DELETE /api/rutas/
    Acceso ADMINISTRADOR DE FLOTA: CRUD de rutas.
    """
    queryset = Ruta.objects.all()
    serializer_class = RutaSerializer
    permission_classes = [IsAdminFlota]


class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.all()
    serializer_class = ServicioSerializer
    permission_classes = [IsAdminFlota]


class CambiarEstadoVentaView(APIView):
    permission_classes = [IsAdminFlota]

    @transaction.atomic
    def patch(self, request, pk):
        try:
            venta = Venta.objects.get(pk=pk)
        except Venta.DoesNotExist:
            return Response({"error": "Venta no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        nuevo_estado = request.data.get('estado')
        if nuevo_estado not in Venta.EstadoVentaChoices.values:
            return Response({"error": f"Estado inválido. Opciones válidas: {Venta.EstadoVentaChoices.values}"}, status=status.HTTP_400_BAD_REQUEST)

        if nuevo_estado == Venta.EstadoVentaChoices.CANCELADO and venta.estado != Venta.EstadoVentaChoices.CANCELADO:
            boletos = venta.boletos.all()
            for boleto in boletos:
                asiento = boleto.asiento_servicio
                asiento.estado = AsientoServicio.EstadoAsientoChoices.DISPONIBLE
                asiento.save()

        venta.estado = nuevo_estado
        venta.save()

        return Response(VentaSerializer(venta).data)


# ---------------------------------------------------------------------------
# 5. VISTA BASE HTML CON INICIO DE SESIÓN, SELECTOR DE ROL Y FOOTER
# ---------------------------------------------------------------------------
class InicioFooterView(APIView):
    permission_classes = [permissions.AllowAny]

    def get_context_alumno(self):
        return {
            "nombre": "Hugo Bustos Barra",
            "carrera": "Ingeniería en Ciberseguridad / Analista Programador",
            "seccion": "IEC-N4-C1",
            "anio": "2026",
            "proyecto": "Proyecto 4: Reservas de Pasajes de Buses Interurbanos"
        }

    def get(self, request):
        return render(request, "inicio.html", {"alumno": self.get_context_alumno()})

    def post(self, request):
        accion = request.data.get('accion') or request.POST.get('accion')

        if accion == 'logout':
            logout(request)
            return redirect('/')

        elif accion == 'registro':
            username = request.data.get('reg_username') or request.POST.get('reg_username')
            email = request.data.get('reg_email') or request.POST.get('reg_email')
            password = request.data.get('reg_password') or request.POST.get('reg_password')

            try:
                validate_email(email)
            except DjangoValidationError:
                return render(request, "inicio.html", {
                    "alumno": self.get_context_alumno(),
                    "error": f"El correo electrónico '{email}' no tiene una estructura válida."
                })

            if Usuario.objects.filter(username=username).exists():
                return render(request, "inicio.html", {
                    "alumno": self.get_context_alumno(),
                    "error": f"El nombre de usuario '{username}' ya se encuentra registrado."
                })

            if Usuario.objects.filter(email=email).exists():
                return render(request, "inicio.html", {
                    "alumno": self.get_context_alumno(),
                    "error": f"El correo electrónico '{email}' ya está registrado con otra cuenta."
                })

            nuevo_pasajero = Usuario.objects.create_user(
                username=username,
                email=email,
                password=password,
                rol=Usuario.RolChoices.PASAJERO
            )
            CarroPasajes.objects.get_or_create(usuario=nuevo_pasajero)

            return render(request, "inicio.html", {
                "alumno": self.get_context_alumno(),
                "mensaje_exito": f"¡Cuenta de Pasajero '{username}' creada exitosamente! Ya puedes iniciar sesión."
            })

        else:
            username = request.data.get('username') or request.POST.get('username')
            password = request.data.get('password') or request.POST.get('password')
            rol_seleccionado = request.data.get('rol') or request.POST.get('rol')

            user_obj = Usuario.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).first()

            if user_obj:
                user = authenticate(request, username=user_obj.username, password=password)
            else:
                user = None

            if user is not None:
                if user.rol == rol_seleccionado or not rol_seleccionado:
                    login(request, user)
                    if user.rol == Usuario.RolChoices.ADMIN_FLOTA:
                        return redirect('admin_flota')
                    else:
                        return redirect('/')
                else:
                    error = f"El usuario no coincide con el rol seleccionado ({rol_seleccionado})."
            else:
                error = "Credenciales inválidas. Por favor, verifica el usuario y contraseña."

            return render(request, "inicio.html", {
                "alumno": self.get_context_alumno(),
                "error": error
            })


# ---------------------------------------------------------------------------
# 6. SECCIÓN DE AYUDA Y RESERVAS TEMPORALES / INVITADOS
# ---------------------------------------------------------------------------
class AyudaView(View):
    def get(self, request):
        return render(request, 'ayuda.html')

    def post(self, request):
        return render(request, 'ayuda.html', {'mensaje': '¡Requerimiento enviado con éxito!'})


class BloquearAsientosTemporalView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        asientos_raw = request.data.get('asientos_ids') or request.data.get('asiento_ids')
        session_id = request.data.get('session_id')
        servicio_id = request.data.get('servicio_id') or 1

        if not session_id or not asientos_raw:
            return Response(
                {"error": "Se requieren 'session_id' y 'asientos_ids'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(asientos_raw, list):
            return Response({"error": "'asientos_ids' debe ser una lista."}, status=status.HTTP_400_BAD_REQUEST)

        ids_db = []
        numeros_asientos = []

        for item in asientos_raw:
            if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
                ids_db.append(int(item))
            elif isinstance(item, str) and item.startswith("virtual-"):
                try:
                    num = int(item.split("-")[1])
                    numeros_asientos.append(num)
                except (IndexError, ValueError):
                    pass

        with transaction.atomic():
            asientos = []

            if ids_db:
                asientos.extend(list(AsientoServicio.objects.select_for_update().filter(id__in=ids_db)))

            if numeros_asientos:
                servicio_obj = Servicio.objects.filter(id=servicio_id).first()
                if not servicio_obj:
                    servicio_obj = Servicio.objects.first()

                if servicio_obj:
                    for num in numeros_asientos:
                        asiento_obj, _ = AsientoServicio.objects.get_or_create(
                            servicio=servicio_obj,
                            numero_asiento=num,
                            defaults={
                                'estado': AsientoServicio.EstadoAsientoChoices.DISPONIBLE,
                                'tarifa': getattr(servicio_obj, 'precio_base', 10000)
                            }
                        )
                        asientos.append(asiento_obj)

            if not asientos:
                return Response(
                    {"error": "No se pudieron obtener ni generar los asientos para la solicitud."},
                    status=status.HTTP_404_NOT_FOUND
                )

            for asiento in asientos:
                if asiento.esta_bloqueado_o_comprado(current_session_id=session_id):
                    return Response(
                        {"error": f"El asiento #{asiento.numero_asiento} ya no está disponible."},
                        status=status.HTTP_409_CONFLICT
                    )

            expiracion = timezone.now() + timedelta(minutes=10)
            for asiento in asientos:
                asiento.estado = AsientoServicio.EstadoAsientoChoices.RESERVADO_TEMPORAL
                asiento.bloqueado_hasta = expiracion
                asiento.session_id = session_id
                asiento.save()

            ids_reales_bloqueados = [a.id for a in asientos]

        return Response({
            "mensaje": "Asientos bloqueados temporalmente por 10 minutos.",
            "asientos_ids": ids_reales_bloqueados,
            "expira_en": expiracion
        }, status=status.HTTP_200_OK)


class CheckoutInvitadoView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutInvitadoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        datos = serializer.validated_data
        session_id = datos['session_id']
        ocupantes_map = {item['asiento_id']: item for item in datos['ocupantes']}
        asientos_ids = list(ocupantes_map.keys())

        asientos = AsientoServicio.objects.select_for_update().filter(id__in=asientos_ids)

        if len(asientos) != len(asientos_ids):
            return Response({"error": "Uno o más asientos no existen."}, status=status.HTTP_404_NOT_FOUND)

        for asiento in asientos:
            if asiento.estado == AsientoServicio.EstadoAsientoChoices.OCUPADO or \
               (asiento.estado == AsientoServicio.EstadoAsientoChoices.RESERVADO_TEMPORAL and asiento.session_id != session_id):
                return Response({
                    "error": f"El tiempo de reserva del asiento #{asiento.numero_asiento} expiró o fue tomado por otra persona."
                }, status=status.HTTP_409_CONFLICT)

        monto_total = sum(asiento.tarifa for asiento in asientos)

        venta = Venta.objects.create(
            usuario=None,
            nombre_comprador=datos['nombre'],
            apellido_comprador=datos['apellido'],
            email_comprador=datos['correo'],
            telefono_comprador=datos['telefono'],
            monto_total=monto_total,
            estado=Venta.EstadoVentaChoices.PAGADO
        )

        boletos_creados = []
        for asiento in asientos:
            info_ocupante = ocupantes_map[asiento.id]

            asiento.estado = AsientoServicio.EstadoAsientoChoices.OCUPADO
            asiento.bloqueado_hasta = None
            asiento.session_id = None
            asiento.save()

            boleto = BoletoViaje.objects.create(
                venta=venta,
                asiento_servicio=asiento,
                nombre_ocupante=info_ocupante['nombre_ocupante'],
                identificacion_ocupante=info_ocupante['identificacion_ocupante'],
                precio_pagado=asiento.tarifa
            )
            boletos_creados.append(boleto)

        serializer_venta = VentaSerializer(venta)
        return Response(serializer_venta.data, status=status.HTTP_201_CREATED)


class LiberarAsientosView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        session_id = request.data.get('session_id')
        asiento_id = request.data.get('asiento_id')

        if not session_id:
            return Response({"error": "El session_id es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            query = AsientoServicio.objects.filter(
                session_id=session_id,
                estado=AsientoServicio.EstadoAsientoChoices.RESERVADO_TEMPORAL
            )

            if asiento_id:
                query = query.filter(id=asiento_id)

            cantidad = query.update(
                estado=AsientoServicio.EstadoAsientoChoices.DISPONIBLE,
                session_id=None,
                bloqueado_hasta=None
            )

        return Response({
            "mensaje": "Asientos liberados correctamente.",
            "cantidad_liberada": cantidad
        }, status=status.HTTP_200_OK)