const HEARTBEAT_INTERVAL = 30000;

function sendHeartbeat() {
    if (!window.userSessionId) {
        return;
    }

    fetch('/activity/heartbeat?session_id=' + encodeURIComponent(window.userSessionId), {
        method: 'GET',
        credentials: 'same-origin'
    })
    .then(response => {
        if (response.status === 401) {
            console.warn('Heartbeat: сессия недействительна, очищаем sessionId');
            window.userSessionId = null;
        } else if (!response.ok) {
            console.error('Heartbeat error:', response.status);
        }
    })
    .catch(error => {
        console.error('Heartbeat network error:', error);
    });
}

sendHeartbeat();
setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);

window.addEventListener('beforeunload', function() {
    window.userSessionId = null;
});