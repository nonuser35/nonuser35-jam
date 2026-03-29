let player1, player2;
let playerAtivo = null;

let isPlaying = false;
let audioActivated = false;

let apiReady = false;
let onReadyCallback = null;
let onStateChangeCallback = null;

function getHostAccessToken() {
    const params = new URLSearchParams(window.location.search);
    return (params.get('host') || '').trim();
}

const tag = document.createElement('script');
tag.src = "https://www.youtube.com/iframe_api";
document.head.appendChild(tag);

let playersReadyCount = 0;

window.onYouTubeIframeAPIReady = function () {
    console.log("YT API pronta");
    apiReady = true;

    player1 = createPlayer('player1');
    player2 = createPlayer('player2');

    playerAtivo = player1;
    syncVisiblePlayerShell();
};

function syncVisiblePlayerShell() {
    const player1Shell = document.getElementById('player1-shell');
    const player2Shell = document.getElementById('player2-shell');
    if (!player1Shell || !player2Shell) return;

    const player1Active = playerAtivo === player1;
    player1Shell.classList.toggle('is-active', player1Active);
    player1Shell.classList.toggle('is-hidden', !player1Active);
    player2Shell.classList.toggle('is-active', !player1Active);
    player2Shell.classList.toggle('is-hidden', player1Active);
}

function createPlayer(elementId) {
    return new YT.Player(elementId, {
        height: '200',
        width: '336',
        playerVars: {
            autoplay: 0,
            controls: 1,
            enablejsapi: 1,
            origin: window.location.origin,
            playsinline: 1,
            rel: 0
        },
        events: {
            onReady: (event) => {
                console.log("Player pronto:", elementId);
                event.target.mute();
                syncVisiblePlayerShell();

                playersReadyCount++;
                if (playersReadyCount === 2 && onReadyCallback) {
                    onReadyCallback();
                }
            },
            onStateChange: (event) => {
                if (onStateChangeCallback) {
                    onStateChangeCallback(event);
                }
            }
        }
    });
}

function initYouTube(onReady, onStateChange) {
    onReadyCallback = onReady;
    onStateChangeCallback = onStateChange;
}

function turnOnAudio(shouldResume = false) {
    audioActivated = true;

    if (playerAtivo) {
        if (typeof playerAtivo.unMute === 'function') {
            playerAtivo.unMute();
        }
        if (shouldResume && typeof playerAtivo.playVideo === 'function') {
            playerAtivo.playVideo();
        }
    }
}

function setPlayerAtivo(p) {
    playerAtivo = p;
    syncVisiblePlayerShell();
}

function setIsPlaying(state) {
    isPlaying = state;
}

async function sendSpotifyCommand(cmd) {
    try {
        const headers = {};
        const hostToken = getHostAccessToken();
        if (hostToken) {
            headers['X-Host-Token'] = hostToken;
        }
        await fetch(`/${cmd}`, { method: 'POST', headers });
    } catch (e) {}
}

window.PlayerDebug = {
    getPlayer: () => playerAtivo
};

export {
    player1,
    player2,
    playerAtivo,
    isPlaying,
    audioActivated,
    initYouTube,
    setPlayerAtivo,
    setIsPlaying,
    turnOnAudio,
    sendSpotifyCommand,
    syncVisiblePlayerShell
};
