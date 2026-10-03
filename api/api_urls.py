"""
=============================================================================
PROYECTO: Reservas de Pasajes de Buses Interurbanos (Transporte)
ALUMNO: Hugo Bustos Barra
AÑO: 2026
=============================================================================
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    InicioFooterView,
    AyudaView,
    RegistroUsuarioView,
    BuscarServiciosView,
    AsientosServicioView,
    BloquearAsientosTemporalView,
    LiberarAsientosView,
    CheckoutInvitadoView,
    CarroPasajesView,
    CheckoutVentaView,
    MisBoletosView,
    BusViewSet,
    RutaViewSet,
    ServicioViewSet,
    CambiarEstadoVentaView,
    LoginPasajeroApiView,
    admin_flota_view,
)

router = DefaultRouter()
router.register(r'buses', BusViewSet, basename='admin-buses')
router.register(r'rutas', RutaViewSet, basename='admin-rutas')
router.register(r'servicios', ServicioViewSet, basename='admin-servicios')

urlpatterns = [
    # Vista Base HTML y Ayuda
    path('', InicioFooterView.as_view(), name='inicio-footer'),
    path('ayuda/', AyudaView.as_view(), name='ayuda'),

    # Ingreso a Panel de Administración de Flota (Nombre unificado: 'admin_flota')
    path('panel/flota/', admin_flota_view, name='admin_flota'),
    path('panel-flota/', admin_flota_view, name='panel_flota'), # Alias de compatibilidad para evitar errores de plantilla

    # Autenticación y Registro Pasajero Web
    path('api/auth/registro/', RegistroUsuarioView.as_view(), name='registro'),
    path('api/auth/registro-web/', RegistroUsuarioView.as_view(), name='registro_web'),
    path('api/auth/login-web/', LoginPasajeroApiView.as_view(), name='login_pasajero_web'),
    path('api/auth/login-pasajero/', LoginPasajeroApiView.as_view(), name='login_pasajero_api'),
        
    # JWT Tokens
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Endpoints Públicos / Proceso de Compra Invitado
    path('api/servicios/buscar/', BuscarServiciosView.as_view(), name='buscar-servicios'),
    path('api/servicios/<int:pk>/asientos/', AsientosServicioView.as_view(), name='ver-asientos'),
    path('api/asientos/bloquear-temporal/', BloquearAsientosTemporalView.as_view(), name='bloquear-asientos-temporal'),
    path('api/asientos/liberar/', LiberarAsientosView.as_view(), name='liberar-asientos'),
    path('api/ventas/checkout-invitado/', CheckoutInvitadoView.as_view(), name='checkout-invitado'),

    # Endpoints Pasajero Autenticado
    path('api/carro-pasajes/', CarroPasajesView.as_view(), name='carro-pasajes'),
    path('api/ventas/checkout/', CheckoutVentaView.as_view(), name='ventas-checkout'),
    path('api/mis-boletos/', MisBoletosView.as_view(), name='mis-boletos'),

    # Endpoints Administrador de Flota
    path('api/ventas/<int:pk>/estado/', CambiarEstadoVentaView.as_view(), name='cambiar-estado-venta'),
    path('api/', include(router.urls)),
]