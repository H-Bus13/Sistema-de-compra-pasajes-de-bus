"""
=============================================================================
PROYECTO: Reservas de Pasajes de Buses Interurbanos (Transporte)
ALUMNO: Hugo Bustos Barra
SECCIÓN: IEC-N4-C1
AÑO: 2026
=============================================================================
DESCRIPCIÓN DE FILTROS:
- ServicioFilter: Permite filtrar el catálogo de servicios según:
  * Origen (ID de terminal o nombre de ciudad)
  * Destino (ID de terminal o nombre de ciudad)
  * Fecha exacta o rango de fechas de salida.
=============================================================================
"""

import django_filters
from .models import Servicio


class ServicioFilter(django_filters.FilterSet):
    origen_ciudad = django_filters.CharFilter(
        field_name='ruta__origen__ciudad', 
        lookup_expr='icontains', 
        label="Ciudad de Origen"
    )
    destino_ciudad = django_filters.CharFilter(
        field_name='ruta__destino__ciudad', 
        lookup_expr='icontains', 
        label="Ciudad de Destino"
    )
    fecha_salida = django_filters.DateFilter(
        field_name='fecha_hora_salida__date', 
        label="Fecha de Salida (YYYY-MM-DD)"
    )

    class Meta:
        model = Servicio
        fields = ['origen_ciudad', 'destino_ciudad', 'fecha_salida']