from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import (
    AsientoServicio,
    Bus,
    CarroPasajes,
    Ruta,
    Servicio,
    Terminal,
    Usuario,
    Venta,
)


class PassengerAccessAndCartTests(APITestCase):
    def setUp(self):
        self.pasajero = Usuario.objects.create_user(
            username='pasajero',
            email='pasajero@example.com',
            password='clave-segura',
            rol=Usuario.RolChoices.PASAJERO,
        )
        self.otro_pasajero = Usuario.objects.create_user(
            username='otro-pasajero',
            email='otro@example.com',
            password='clave-segura',
            rol=Usuario.RolChoices.PASAJERO,
        )
        self.administrador = Usuario.objects.create_user(
            username='admin-flota',
            email='admin@example.com',
            password='clave-segura',
            rol=Usuario.RolChoices.ADMIN_FLOTA,
        )
        origen = Terminal.objects.create(nombre='Terminal A', ciudad='Santiago')
        destino = Terminal.objects.create(nombre='Terminal B', ciudad='Temuco')
        ruta = Ruta.objects.create(
            origen=origen,
            destino=destino,
            duracion_estimada_horas=8,
        )
        bus = Bus.objects.create(
            patente='ABCD12',
            numero_bus=1,
            capacidad_asientos=40,
        )
        salida = timezone.now() + timedelta(days=1)
        self.servicio = Servicio.objects.create(
            ruta=ruta,
            bus=bus,
            fecha_hora_salida=salida,
            fecha_hora_llegada=salida + timedelta(hours=8),
            precio_base=15000,
        )
        self.asiento = AsientoServicio.objects.create(
            servicio=self.servicio,
            numero_asiento=1,
            tarifa=15000,
        )

    def test_passenger_login_rejects_fleet_admin(self):
        response = self.client.post(
            '/api/auth/login-web/',
            {
                'username': self.administrador.username,
                'password': 'clave-segura',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn('no es de pasajero', response.data['error'])

    def test_passenger_login_accepts_passenger(self):
        response = self.client.post(
            '/api/auth/login-web/',
            {
                'username': self.pasajero.username,
                'password': 'clave-segura',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['usuario']['rol'], Usuario.RolChoices.PASAJERO)

    def test_home_page_initializes_cart_for_the_logged_in_passenger(self):
        self.client.force_login(self.pasajero)

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'window.usuarioPasajeroId = {self.pasajero.id};')
        self.assertContains(response, 'async function bloquearAsientosYSeguir')
        self.assertNotContains(response, '<script src="/static/js/compra_invitado.js')

    def test_service_search_filters_by_origin_destination_and_departure_date(self):
        fecha_salida = timezone.localtime(self.servicio.fecha_hora_salida).date().isoformat()

        response = self.client.get(
            '/api/servicios/buscar/',
            {
                'origen_ciudad': 'santi',
                'destino_ciudad': 'temu',
                'fecha_salida': fecha_salida,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data], [self.servicio.id])

        response_sin_resultados = self.client.get(
            '/api/servicios/buscar/',
            {'origen_ciudad': 'ciudad-inexistente'},
        )
        self.assertEqual(response_sin_resultados.status_code, 200)
        self.assertEqual(response_sin_resultados.data, [])

    def test_admin_login_is_available_through_admin_role_only(self):
        response = self.client.post(
            '/',
            {
                'username': self.administrador.username,
                'password': 'clave-segura',
                'rol': Usuario.RolChoices.ADMIN_FLOTA,
            },
        )

        self.assertRedirects(response, '/panel/flota/', fetch_redirect_response=False)

    def test_seat_selection_is_stored_per_passenger_and_can_be_purchased(self):
        client_pasajero = APIClient()
        client_pasajero.force_authenticate(user=self.pasajero)
        response = client_pasajero.post(
            '/api/carro-pasajes/',
            {'asiento_servicio': self.asiento.id, 'session_id': 'sesion-pasajero'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data['items']), 1)

        client_otro = APIClient()
        client_otro.force_authenticate(user=self.otro_pasajero)
        response_otro = client_otro.get('/api/carro-pasajes/')
        self.assertEqual(response_otro.status_code, 200)
        self.assertEqual(response_otro.data['items'], [])

        response = client_pasajero.post(
            '/api/carro-pasajes/',
            {
                'asiento_servicio': self.asiento.id,
                'nombre_ocupante': 'Pasajero de prueba',
                'identificacion_ocupante': '12345678-5',
                'session_id': 'sesion-pasajero',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        response = client_pasajero.post(
            '/api/ventas/checkout/',
            {
                'session_id': 'sesion-pasajero',
                'asientos_ids': [self.asiento.id],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['usuario'], self.pasajero.id)
        self.assertEqual(Venta.objects.get().usuario, self.pasajero)
        self.assertEqual(
            AsientoServicio.objects.get(pk=self.asiento.id).estado,
            AsientoServicio.EstadoAsientoChoices.OCUPADO,
        )
        self.assertEqual(CarroPasajes.objects.get(usuario=self.pasajero).items.count(), 0)
