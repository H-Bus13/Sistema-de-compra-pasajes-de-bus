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

async function procesarLoginModal(event) {
    event.preventDefault();

    const form = event.target;
    const alertError = document.getElementById('alertLoginModalError');
    const btnSubmit = form.querySelector('button[type="submit"]');

    if (alertError) {
        alertError.classList.add('d-none');
        alertError.innerText = '';
    }

    if (btnSubmit) btnSubmit.disabled = true;

    const emailInput = form.querySelector('input[name="username"]');
    const passwordInput = form.querySelector('input[name="password"]');
    const rolInput = form.querySelector('select[name="rol"]');

    const emailValue = emailInput ? emailInput.value.trim() : '';

    const payload = {
        correo: emailValue,
        username: emailValue,
        password: passwordInput ? passwordInput.value : '',
        rol: rolInput ? rolInput.value : 'PASAJERO'
    };

    try {
        const response = await fetch('/api/auth/login-web/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const data = await response.json();
            if (data.usuario) {
                localStorage.setItem('usuario_logeado', JSON.stringify(data.usuario));
            }
            
            // Si el rol devuelto o seleccionado es ADMIN_FLOTA, redirige al panel principal de flota
            const rolUsuario = (data.usuario && data.usuario.rol) || (rolInput ? rolInput.value : '');
            if (rolUsuario === 'ADMIN_FLOTA') {
                window.location.href = '/panel/flota/';
            } else {
                window.location.reload();
            }
            return;
        }

        if (response.status === 400 || response.status === 401 || response.status === 403) {
            const data = await response.json();
            const mensajeErr = data.error || data.detail || 'Correo o contraseña incorrectos. Por favor intente de nuevo.';
            if (alertError) {
                alertError.innerText = mensajeErr;
                alertError.classList.remove('d-none');
            } else {
                alert(mensajeErr);
            }
            if (btnSubmit) btnSubmit.disabled = false;
            return;
        }

        form.submit();

    } catch (error) {
        console.warn('Fallback a envío POST tradicional por error de red:', error);
        form.submit();
    }
}