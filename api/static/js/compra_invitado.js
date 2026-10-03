// 1. Identificador de sesión para el invitado
let sessionId = localStorage.getItem('session_id');
if (!sessionId) {
    sessionId = 'invitado_' + Math.random().toString(36).substring(2, 9) + '_' + Date.now();
    localStorage.setItem('session_id', sessionId);
}

// Variables para almacenar selección actual
let asientosSeleccionadosIds = [];

// Helper para obtener Cookie CSRF de Django
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Helper: Algoritmo Módulo 11 para validación de RUT Chileno
function validarRutChileno(rut) {
    if (!rut || typeof rut !== 'string') return false;

    // Limpia puntos, guiones y espacios; convierte K a mayúscula
    const valor = rut.replace(/[^0-9kK]/g, '').toUpperCase();
    if (valor.length < 8) return false;

    const cuerpo = valor.slice(0, -1);
    const dvIngresado = valor.slice(-1);

    let suma = 0;
    let multiplicador = 2;

    for (let i = cuerpo.length - 1; i >= 0; i--) {
        suma += parseInt(cuerpo.charAt(i), 10) * multiplicador;
        multiplicador = multiplicador < 7 ? multiplicador + 1 : 2;
    }

    const dvEsperadoNum = 11 - (suma % 11);
    let dvEsperado = '';

    if (dvEsperadoNum === 11) dvEsperado = '0';
    else if (dvEsperadoNum === 10) dvEsperado = 'K';
    else dvEsperado = dvEsperadoNum.toString();

    return dvIngresado === dvEsperado;
}

// 2. Función para bloquear asientos temporalmente y abrir modal
async function bloquearAsientosYSeguir(asientoIds, servicioId) {
    let miSessionId = localStorage.getItem('session_id');
    if (!miSessionId) {
        miSessionId = 'sess_' + Math.random().toString(36).substring(2, 15);
        localStorage.setItem('session_id', miSessionId);
    }

    try {
        const res = await fetch('/api/asientos/bloquear-temporal/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                asientos_ids: asientoIds,
                session_id: miSessionId,
                servicio_id: servicioId || null
            })
        });

        const data = await res.json();

        if (!res.ok) {
            alert(data.error || "No se pudieron bloquear los asientos seleccionados.");
            return;
        }

        const idsReales = data.asientos_ids || asientoIds;
        asientosSeleccionadosIds = idsReales;

        generarCamposPasajeros(idsReales);

        const modalFormEl = document.getElementById('modalCompraInvitado');
        if (modalFormEl) {
            const modalForm = bootstrap.Modal.getOrCreateInstance(modalFormEl);
            modalForm.show();
        }
    } catch (e) {
        console.error("Error al bloquear asientos:", e);
        alert("Ocurrió un error al procesar la reserva temporal.");
    }
}

// 3. Generar dinámicamente los campos para RUT/Nombre de cada pasajero
function generarCamposPasajeros(asientos) {
    const contenedor = document.getElementById('contenedorPasajeros');
    if (!contenedor) return;
    
    contenedor.innerHTML = '';

    asientos.forEach((asientoId, index) => {
        contenedor.innerHTML += `
            <div class="card mb-3 border-secondary">
                <div class="card-body">
                    <h6 class="card-title fw-bold text-primary">Pasajero ${index + 1} (Asiento ID: ${asientoId})</h6>
                    <div class="row g-2">
                        <div class="col-md-7">
                            <label class="form-label text-dark fw-semibold small">Nombre Completo</label>
                            <input type="text" class="form-control" name="nombre_ocupante_${asientoId}" required placeholder="Ej: Juan Pérez">
                        </div>
                        <div class="col-md-5">
                            <label class="form-label text-dark fw-semibold small">RUT</label>
                            <input type="text" class="form-control" name="rut_ocupante_${asientoId}" required placeholder="Ej: 19876543-2">
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
}

// 4. Capturar el envío del formulario y hacer Checkout
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('formCheckoutInvitado');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (asientosSeleccionadosIds.length === 0) {
            alert("No hay asientos seleccionados para procesar.");
            return;
        }

        // --- VALIDACIÓN DE RUTS DE PASAJEROS ---
        const ocupantes = [];
        for (let i = 0; i < asientosSeleccionadosIds.length; i++) {
            const asientoId = asientosSeleccionadosIds[i];
            const inputNombre = form[`nombre_ocupante_${asientoId}`];
            const inputRut = form[`rut_ocupante_${asientoId}`];

            const nombreVal = inputNombre ? inputNombre.value.trim() : '';
            const rutVal = inputRut ? inputRut.value.trim() : '';

            if (!validarRutChileno(rutVal)) {
                alert(`El RUT "${rutVal}" ingresado para el Pasajero ${i + 1} no es válido. Por favor verifique el número y dígito verificador.`);
                if (inputRut) inputRut.focus();
                return;
            }

            ocupantes.push({
                asiento_id: asientoId,
                nombre_ocupante: nombreVal,
                identificacion_ocupante: rutVal
            });
        }

        const miSessionId = localStorage.getItem('session_id') || sessionId;

        const payload = {
            nombre: document.getElementById('invitadoNombre').value,
            apellido: document.getElementById('invitadoApellido').value,
            correo: document.getElementById('invitadoCorreo').value,
            telefono: document.getElementById('invitadoTelefono').value,
            session_id: miSessionId,
            ocupantes: ocupantes
        };

        try {
            const respuesta = await fetch('/api/ventas/checkout-invitado/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(payload)
            });

            const data = await respuesta.json();

            if (respuesta.status === 201) {
                alert(`¡Compra realizada con éxito!\nNúmero de Venta: #${data.id}\nTotal pagado: $${data.monto_total}`);
                location.reload();
            } else {
                alert("Error al finalizar la compra: " + (data.error || JSON.stringify(data)));
            }
        } catch (error) {
            console.error("Error en checkout:", error);
            alert("Ocurrió un error al procesar el pago.");
        }
    });
});