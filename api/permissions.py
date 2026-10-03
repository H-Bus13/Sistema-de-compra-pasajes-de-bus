"""
=============================================================================
PROYECTO: Reservas de Pasajes de Buses Interurbanos (Transporte)
ALUMNO: Hugo Bustos Barra
SECCIÓN: [Tu Sección]
AÑO: 2026
=============================================================================
DESCRIPCIÓN DE PERMISOS (RBAC):
- IsPasajero: Permite el acceso solo a usuarios con rol 'PASAJERO' o Superusuarios.
- IsAdminFlota: Permite la gestión administrativa solo a usuarios con rol 'ADMIN_FLOTA' o Superusuarios.
=============================================================================
"""

from rest_framework import permissions
from .models import Usuario


class IsPasajero(permissions.BasePermission):
    """
    Permite acceso únicamente a clientes/pasajeros autenticados.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.rol == Usuario.RolChoices.PASAJERO or request.user.is_staff or request.user.is_superuser)
        )


class IsAdminFlota(permissions.BasePermission):
    """
    Permite acceso únicamente a Administradores de Flota o Staff.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.rol == Usuario.RolChoices.ADMIN_FLOTA or request.user.is_staff or request.user.is_superuser)
        )