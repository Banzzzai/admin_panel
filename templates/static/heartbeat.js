const HEARTBEAT_INTERVAL = 30000;

function sendHeartbeat() {
    if (!window.userSessionId) {
        // Если session_id отсутствует
        return;
    }

    fetch('/activity/heartbeat?session_id=' + encodeURIComponent(window.userSessionId), {
        method: 'GET',
        credentials: 'same-origin' // чтобы отправлялись cookie сессии Flask
    })
    .then(response => {
        if (response.status === 401) {
            // Сессия истекла или пользователь разлогинен на сервере
            console.warn('Heartbeat: сессия недействительна, очищаем sessionId');
            window.userSessionId = null;
            //перенаправление на страницу входа
            // window.location.href = '/login';
        } else if (!response.ok) {
            console.error('Heartbeat error:', response.status);
        }
    })
    .catch(error => {
        console.error('Heartbeat network error:', error);
    });
}

// Запускаем первый heartbeat сразу, затем повторяем по интервалу
sendHeartbeat();
setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);

// При выходе из системы (logout) очищаем session_id, чтобы прекратить отправку
window.addEventListener('beforeunload', function() {
    // Опционально: можно отправить уведомление о закрытии страницы,
    // но надёжнее полагаться на logout на сервере.
    window.userSessionId = null;
});