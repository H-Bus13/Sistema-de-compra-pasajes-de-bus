/**
 * Valida un RUT chileno utilizando el algoritmo Módulo 11.
 * Acepta formatos con o sin puntos y con guion (ej: 12.345.678-9 o 12345678-K).
 */
function validarRutChileno(rutCompleto) {
    let valor = rutCompleto.replace(/\./g, '').replace(/-/g, '').trim().toUpperCase();

    if (valor.length < 8) return false;

    let cuerpo = valor.slice(0, -1);
    let dv = valor.slice(-1);

    if (!/^[0-9]+$/.test(cuerpo)) return false;

    let suma = 0;
    let multiplo = 2;

    for (let i = 1; i <= cuerpo.length; i++) {
        let index = multiplo * parseInt(valor.charAt(cuerpo.length - i), 10);
        suma += index;
        multiplo = multiplo < 7 ? multiplo + 1 : 2;
    }

    let dvEsperado = 11 - (suma % 11);
    let dvTexto = '';

    if (dvEsperado === 11) dvTexto = '0';
    else if (dvEsperado === 10) dvTexto = 'K';
    else dvTexto = dvEsperado.toString();

    return dv === dvTexto;
}

// Variable global para bloquear solicitudes simultáneas o dobles clicks
let procesandoRegistro = false;

document.addEventListener('DOMContentLoaded', () => {
    const formRegistro = document.getElementById('formRegistroPasajero');
    if (!formRegistro) return;

    formRegistro.addEventListener('submit', async (e) => {
        // DETENER CUALQUIER ENVÍO PARALELO O EVENTO POR DEFECTO
        e.preventDefault();
        e.stopPropagation();

        // CONTROL RIGUROSO ANTI-DOBLE ENVÍO
        if (procesandoRegistro) {
            return false;
        }
        procesandoRegistro = true;

        const btnSubmit = formRegistro.querySelector('button[type="submit"]');
        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerText = 'Registrando...';
        }

        const nombre = document.getElementById('regNombre').value.trim();
        const apellido = document.getElementById('regApellido').value.trim();
        const rut = document.getElementById('regRut').value.trim();
        const email = document.getElementById('regEmail').value.trim();
        const password = document.getElementById('regPassword').value;

        const errorBox = document.getElementById('mensajeErrorRegistro');
        const exitoBox = document.getElementById('mensajeExitoRegistro');

        if (errorBox) {
            errorBox.classList.add('d-none');
            errorBox.innerText = '';
        }
        if (exitoBox) {
            exitoBox.classList.add('d-none');
            exitoBox.innerText = '';
        }

        // VALIDACIÓN DEL RUT EN EL FRONTEND
        if (!validarRutChileno(rut)) {
            if (errorBox) {
                errorBox.innerText = 'El RUT ingresado no es válido. Verifica el número y el dígito verificador (Ej: 12345678-9).';
                errorBox.classList.remove('d-none');
            }
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerText = 'Registrarme';
            }
            procesandoRegistro = false;
            return;
        }

        try {
            const response = await fetch('/api/auth/registro-web/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
                },
                body: JSON.stringify({
                    username: email,
                    first_name: nombre,
                    last_name: apellido,
                    rut: rut,
                    email: email,
                    password: password
                })
            });

            const contentType = response.headers.get('content-type');
            let data = {};

            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                const textoError = await response.text();
                console.error('El servidor no devolvió JSON:', textoError);
                throw new Error(`Error ${response.status} en el servidor. Revisa la consola de Django.`);
            }

            if (response.ok) {
                if (exitoBox) {
                    exitoBox.innerText = '¡Cuenta creada con éxito! Redirigiendo al inicio de sesión...';
                    exitoBox.classList.remove('d-none');
                }
                formRegistro.reset();

                setTimeout(() => {
                    const modalRegistroEl = document.getElementById('modalRegistroPasajero');
                    const modalRegistro = bootstrap.Modal.getInstance(modalRegistroEl);
                    if (modalRegistro) modalRegistro.hide();

                    const modalLoginEl = document.getElementById('modalLogin');
                    if (modalLoginEl) {
                        const modalLogin = new bootstrap.Modal(modalLoginEl);
                        modalLogin.show();
                    }
                }, 2000);
            } else {
                // MANEJO DE ERRORES HTTP 400
                let errorMsg = '';
                if (typeof data === 'object' && !data.detail && !data.error) {
                    const mensajesDetalle = [];
                    const mapaCampos = {
                        'username': 'Correo/Usuario',
                        'email': 'Correo',
                        'first_name': 'Nombre',
                        'last_name': 'Apellido',
                        'password': 'Contraseña',
                        'rut': 'RUT'
                    };

                    for (const [campo, mensajes] of Object.entries(data)) {
                        const nombreEtiqueta = mapaCampos[campo] || campo;
                        const texto = Array.isArray(mensajes) ? mensajes.join(', ') : mensajes;
                        mensajesDetalle.push(`${nombreEtiqueta}: ${texto}`);
                    }
                    errorMsg = mensajesDetalle.join(' | ');
                } else {
                    errorMsg = data.detail || data.error || 'Ocurrió un error al registrar la cuenta.';
                }

                if (errorBox) {
                    errorBox.innerText = errorMsg;
                    errorBox.classList.remove('d-none');
                }
                if (btnSubmit) {
                    btnSubmit.disabled = false;
                    btnSubmit.innerText = 'Registrarme';
                }
                procesandoRegistro = false;
            }
        } catch (err) {
            console.error('Error en registro:', err);
            if (errorBox) {
                errorBox.innerText = err.message || 'Error de conexión con el servidor.';
                errorBox.classList.remove('d-none');
            }
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerText = 'Registrarme';
            }
            procesandoRegistro = false;
        }
    });
});