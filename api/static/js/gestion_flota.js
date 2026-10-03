document.addEventListener('DOMContentLoaded', () => {
    // 1. Cargar la lista de buses, opciones del formulario y establecer fecha/hora mínima actual
    cargarBuses();
    cargarSelectsServicio();
    cargarServiciosProgramados();
    establecerFechasMinimas();

    // 2. Event listeners para formularios
    const formAgregarBus = document.getElementById('formAgregarBus');
    if (formAgregarBus) {
        formAgregarBus.addEventListener('submit', guardarNuevoBus);
    }

    const formAgregarRuta = document.getElementById('formAgregarRuta');
    if (formAgregarRuta) {
        formAgregarRuta.addEventListener('submit', guardarNuevaRuta);
    }

    const formAgregarServicio = document.getElementById('formAgregarServicio');
    if (formAgregarServicio) {
        formAgregarServicio.addEventListener('submit', guardarNuevoServicio);
    }
});

// Establece dinámicamente la fecha y hora mínima en los inputs datetime-local (no permite fechas pasadas)
function establecerFechasMinimas() {
    const inputFechaSalida = document.getElementById('inputFechaSalida');
    const inputFechaLlegada = document.getElementById('inputFechaLlegada');

    if (inputFechaSalida) {
        const ahora = new Date();
        ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset());
        const minISO = ahora.toISOString().slice(0, 16);

        inputFechaSalida.min = minISO;
        if (inputFechaLlegada) inputFechaLlegada.min = minISO;

        // Actualizar dinámicamente la llegada mínima al cambiar la fecha de salida
        inputFechaSalida.addEventListener('change', () => {
            if (inputFechaLlegada && inputFechaSalida.value) {
                inputFechaLlegada.min = inputFechaSalida.value;
            }
        });
    }
}

// Obtener cookie del CSRF Token de Django
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

// Carga asíncrona de buses registrados
async function cargarBuses() {
    const tbody = document.getElementById('tbodyBuses');
    if (!tbody) return;

    try {
        const response = await fetch('/api/buses/');
        
        if (response.ok) {
            const buses = await response.json();
            
            if (buses.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center text-muted py-3">
                            No hay buses registrados en la flota.
                        </td>
                    </tr>`;
                return;
            }

            tbody.innerHTML = buses.map(bus => `
                <tr class="${!bus.activo ? 'table-secondary text-muted' : ''}">
                    <td class="fw-bold ${bus.activo ? 'text-warning' : 'text-secondary'}">#${bus.numero_bus}</td>
                    <td><span class="badge bg-secondary fs-6">${bus.patente}</span></td>
                    <td>${bus.capacidad_asientos} asientos</td>
                    <td>
                        ${bus.activo 
                            ? '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Operativo</span>' 
                            : '<span class="badge bg-danger"><i class="bi bi-x-circle me-1"></i>Inactivo/Taller</span>'}
                    </td>
                    <td>
                        ${bus.activo ? `
                            <button class="btn btn-sm btn-outline-danger" onclick="desactivarBus(${bus.id})" title="Inactivar Bus">
                                <i class="bi bi-trash"></i> Inactivar
                            </button>
                        ` : `
                            <button class="btn btn-sm btn-outline-success" onclick="reactivarBus(${bus.id})" title="Reactivar Bus">
                                <i class="bi bi-arrow-counterclockwise"></i> Reactivar
                            </button>
                        `}
                    </td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">Error al cargar la lista de buses.</td></tr>`;
        }
    } catch (err) {
        console.error('Error al conectar con la API de buses:', err);
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger">Error de conexión con el servidor.</td></tr>`;
    }
}

// Guardar nuevo bus
async function guardarNuevoBus(e) {
    e.preventDefault();

    const numero_bus = document.getElementById('inputNumeroBus').value;
    const patente = document.getElementById('inputPatente').value.trim();
    const capacidad_asientos = document.getElementById('inputCapacidad').value;
    const alertError = document.getElementById('alertErrorBus');

    if (alertError) alertError.classList.add('d-none');

    try {
        const response = await fetch('/api/buses/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            },
            body: JSON.stringify({
                numero_bus: parseInt(numero_bus),
                patente: patente,
                capacidad_asientos: parseInt(capacidad_asientos),
                activo: true
            })
        });

        const data = await response.json();

        if (response.ok) {
            const modalEl = document.getElementById('modalAgregarBus');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) modalInstance.hide();

            document.getElementById('formAgregarBus').reset();
            cargarBuses();
            cargarSelectsServicio();
        } else {
            const msg = data.detail || data.patente || data.numero_bus || 'Error al guardar el bus.';
            if (alertError) {
                alertError.innerText = Array.isArray(msg) ? msg[0] : msg;
                alertError.classList.remove('d-none');
            } else {
                alert(msg);
            }
        }
    } catch (err) {
        console.error('Error al guardar bus:', err);
        alert('Error de conexión con el servidor.');
    }
}

// Soft delete y Reactivación de buses
async function desactivarBus(busId) {
    if (!confirm('¿Estás seguro de que deseas dar de baja este bus?')) return;

    try {
        const response = await fetch(`/api/buses/${busId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            }
        });

        if (response.ok || response.status === 204) {
            cargarBuses();
            cargarSelectsServicio();
        } else {
            alert('No se pudo inactivar el bus.');
        }
    } catch (err) {
        console.error('Error al inactivar bus:', err);
    }
}

async function reactivarBus(busId) {
    try {
        const response = await fetch(`/api/buses/${busId}/`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            },
            body: JSON.stringify({ activo: true })
        });

        if (response.ok) {
            cargarBuses();
            cargarSelectsServicio();
        } else {
            alert('No se pudo reactivar el bus.');
        }
    } catch (err) {
        console.error('Error al reactivar bus:', err);
    }
}

// Guardar nueva ruta
async function guardarNuevaRuta(e) {
    e.preventDefault();

    const origen = document.getElementById('inputOrigen')?.value.trim();
    const destino = document.getElementById('inputDestino')?.value.trim();
    const duracion = document.getElementById('inputDuracion')?.value || 0;

    if (!origen || !destino) {
        alert('Por favor, ingresa tanto la ciudad de origen como la de destino.');
        return;
    }

    try {
        const response = await fetch('/api/rutas/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            },
            body: JSON.stringify({
                origen: origen,
                destino: destino,
                duracion_estimada_horas: parseFloat(duracion)
            })
        });

        if (response.ok) {
            const modalEl = document.getElementById('modalGestionarRutas');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) modalInstance.hide();
            
            document.getElementById('formAgregarRuta').reset();
            alert('¡Ruta creada exitosamente!');
            cargarSelectsServicio();
        } else {
            const errData = await response.json();
            console.error('Detalles del error devuelto por Django:', errData);
            
            let mensajeError = 'Error al guardar la ruta: ';
            if (typeof errData === 'object') {
                mensajeError += Object.entries(errData)
                    .map(([campo, msgs]) => `${campo}: ${Array.isArray(msgs) ? msgs.join(', ') : msgs}`)
                    .join(' | ');
            } else {
                mensajeError += JSON.stringify(errData);
            }
            alert(mensajeError);
        }
    } catch (err) {
        console.error('Error de red al guardar la ruta:', err);
        alert('Error de conexión con el servidor al guardar la ruta.');
    }
}

// Carga las opciones de rutas y buses en los selectores del modal de Viajes
async function cargarSelectsServicio() {
    const selectRuta = document.getElementById('selectRutaServicio');
    const selectBus = document.getElementById('selectBusServicio');

    if (!selectRuta || !selectBus) return;

    try {
        const [resRutas, resBuses] = await Promise.all([
            fetch('/api/rutas/'),
            fetch('/api/buses/')
        ]);

        if (resRutas.ok) {
            const rutas = await resRutas.json();
            selectRuta.innerHTML = '<option value="">Seleccione una Ruta...</option>' + 
                rutas.map(r => `<option value="${r.id}">${r.origen_detalle?.ciudad || r.origen} ➔ ${r.destino_detalle?.ciudad || r.destino}</option>`).join('');
        }

        if (resBuses.ok) {
            const buses = await resBuses.json();
            const busesActivos = buses.filter(b => b.activo);
            selectBus.innerHTML = '<option value="">Seleccione un Bus...</option>' + 
                busesActivos.map(b => `<option value="${b.id}">Bus #${b.numero_bus} - Patente: ${b.patente} (${b.capacidad_asientos} as.)</option>`).join('');
        }
    } catch (err) {
        console.error('Error al cargar datos para asociar viajes:', err);
    }
}

// Asociar Bus + Ruta + Fecha (Publicar Viaje)
async function guardarNuevoServicio(e) {
    e.preventDefault();

    const rutaId = document.getElementById('selectRutaServicio').value;
    const busId = document.getElementById('selectBusServicio').value;
    const fechaSalida = document.getElementById('inputFechaSalida').value;
    const fechaLlegada = document.getElementById('inputFechaLlegada').value;
    const precioBase = document.getElementById('inputPrecioBase').value;

    // Validación de seguridad previa al envío
    const fechaActual = new Date();
    if (new Date(fechaSalida) < fechaActual) {
        alert('La fecha y hora de salida no puede ser anterior a la hora actual.');
        return;
    }
    if (new Date(fechaLlegada) <= new Date(fechaSalida)) {
        alert('La fecha y hora de llegada debe ser posterior a la fecha de salida.');
        return;
    }

    try {
        const response = await fetch('/api/servicios/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            },
            body: JSON.stringify({
                ruta: parseInt(rutaId),
                bus: parseInt(busId),
                fecha_hora_salida: fechaSalida,
                fecha_hora_llegada: fechaLlegada,
                precio_base: parseFloat(precioBase)
            })
        });

        if (response.ok) {
            const modalEl = document.getElementById('modalAgregarServicio');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) modalInstance.hide();

            document.getElementById('formAgregarServicio').reset();
            establecerFechasMinimas();
            alert('¡Viaje programado y publicado exitosamente para los clientes!');
            cargarServiciosProgramados();
        } else {
            const errData = await response.json();
            alert('Error al publicar el viaje: ' + JSON.stringify(errData));
        }
    } catch (err) {
        console.error('Error al crear el viaje:', err);
        alert('Error de conexión al guardar el viaje.');
    }
}

// Lista los viajes creados en el panel de administración
async function cargarServiciosProgramados() {
    const tbody = document.getElementById('tbodyServicios');
    if (!tbody) return;

    try {
        const response = await fetch('/api/servicios/');
        if (response.ok) {
            const servicios = await response.json();
            if (servicios.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-3">No hay viajes programados.</td></tr>`;
                return;
            }

            tbody.innerHTML = servicios.map(s => `
                <tr>
                    <td><strong class="text-warning">${s.ruta_detalle?.origen_detalle?.ciudad || 'Origen'} ➔ ${s.ruta_detalle?.destino_detalle?.ciudad || 'Destino'}</strong></td>
                    <td>Bus #${s.bus_detalle?.numero_bus} (${s.bus_detalle?.patente})</td>
                    <td>${new Date(s.fecha_hora_salida).toLocaleString('es-CL')}</td>
                    <td class="text-success fw-bold">$${parseInt(s.precio_base).toLocaleString('es-CL')}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-danger" onclick="eliminarServicio(${s.id})">
                            <i class="bi bi-trash"></i> Cancelar
                        </button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (err) {
        console.error('Error al cargar lista de viajes:', err);
    }
}

async function eliminarServicio(servicioId) {
    if (!confirm('¿Deseas cancelar y eliminar este viaje programado?')) return;
    try {
        const response = await fetch(`/api/servicios/${servicioId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            }
        });
        if (response.ok) cargarServiciosProgramados();
    } catch (err) {
        console.error('Error al eliminar servicio:', err);
    }
}