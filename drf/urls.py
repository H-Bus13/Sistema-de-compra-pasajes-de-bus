"""
=============================================================================
PROYECTO: Reservas de Pasajes de Buses Interurbanos (Transporte)
ALUMNO: Hugo Bustos Barra
AÑO: 2026
=============================================================================
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from api.permissions import IsAdminFlota

# Vistas de Swagger protegidas solo para Administrador de Flota con Autenticación por Sesión
class SchemaAdminView(SpectacularAPIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated, IsAdminFlota]

class SwaggerAdminView(SpectacularSwaggerView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated, IsAdminFlota]


from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render

# Función para renderizar el template 404 personalizado
def custom_404_view(request, exception=None):
    return render(request, '404.html', status=404)

# Asignación del handler a nivel global de Django
handler404 = 'drf.urls.custom_404_view'

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Documentación OpenAPI / Swagger restringida a Administrador
    path('api/schema/', SchemaAdminView.as_view(), name='schema'),
    path('api/docs/', SwaggerAdminView.as_view(url_name='schema'), name='swagger-ui'),

    # Rutas de la app (apuntando al nuevo archivo api_urls)
    path('', include('api.api_urls')),
]