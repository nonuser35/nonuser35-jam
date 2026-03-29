// ==UserScript==
// @name         YT Music Sync Remote
// @namespace    yt-music-sync
// @version      2.0.0
// @description  Script unico para sincronizar YT Music por servidor HTTP local publicado com Cloudflare Tunnel.
// @match        https://music.youtube.com/*
// @grant        GM_xmlhttpRequest
// @connect      *
// ==/UserScript==

(function () {
    'use strict';

    const ROLE_KEY = 'yt-sync-role';
    const TAB_ID_KEY = 'yt-sync-tab-id';
    const SERVER_URL_KEY = 'yt-sync-server-url';
    const TOKEN_KEY = 'yt-sync-token';
    const POLL_INTERVAL_MS = 1000;

    const TAB_ID = sessionStorage.getItem(TAB_ID_KEY) || `tab-${Math.random().toString(36).slice(2)}`;
    sessionStorage.setItem(TAB_ID_KEY, TAB_ID);

    let role = sessionStorage.getItem(ROLE_KEY) || 'idle';
    let videoEl = null;
    let attachedVideo = null;
    let attachedControlVideo = null;
    let lastPublishedAt = 0;
    let lastAppliedRevision = 0;
    let isApplying = false;
    let pendingTrackState = null;
    let pendingState = null;
    let pollTimer = null;
    let suppressPublishUntil = 0;
    let jamControlEnabled = false;
    let jamConfigLoaded = false;
    let syncStatus = 'idle';
    let lastRequestedVideoId = null;
    let lastNavigationAt = 0;
    let bootstrapApplied = false;
    let lastBootstrapHash = '';
    let localRuntimePollTimer = null;

    function log(...args) {
        console.log('[yt-sync]', ...args);
    }

    function setSyncStatus(nextStatus) {
        syncStatus = nextStatus;
        ensurePanel();
    }

    function getServerUrl() {
        return (localStorage.getItem(SERVER_URL_KEY) || '').trim().replace(/\/+$/, '');
    }

    function getToken() {
        return (localStorage.getItem(TOKEN_KEY) || '').trim();
    }

    function getHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        const token = getToken();
        if (token) {
            headers.Authorization = `Bearer ${token}`;
        }
        return headers;
    }

    function getRole() {
        return sessionStorage.getItem(ROLE_KEY) || 'idle';
    }

    function setRole(nextRole) {
        if (nextRole) {
            sessionStorage.setItem(ROLE_KEY, nextRole);
        } else {
            sessionStorage.removeItem(ROLE_KEY);
        }
        window.location.reload();
    }

    function getVideo() {
        return document.querySelector('video');
    }

    function consumeBootstrapConfig() {
        const rawHash = window.location.hash || '';
        const rawSearch = window.location.search || '';
        const bootstrapKey = `${rawSearch}|${rawHash}`;
        if ((!rawHash && !rawSearch) || bootstrapKey === lastBootstrapHash) {
            return;
        }

        let bootstrapServer = null;
        let bootstrapToken = null;
        let bootstrapRole = null;

        if (rawSearch.includes('yt_sync_bootstrap=')) {
            try {
                const searchParams = new URLSearchParams(rawSearch.replace(/^\?/, ''));
                const payload = searchParams.get('yt_sync_bootstrap');
                if (payload) {
                    const decoded = JSON.parse(atob(payload));
                    bootstrapServer = decoded.server || null;
                    bootstrapToken = decoded.token || null;
                    bootstrapRole = decoded.role || null;
                }
            } catch (error) {
                log('falha ao consumir bootstrap por query', error);
            }
        } else if (rawHash.includes('yt-sync-bootstrap=')) {
            try {
                const hashParams = new URLSearchParams(rawHash.replace(/^#/, ''));
                const payload = hashParams.get('yt-sync-bootstrap');
                if (payload) {
                    const decoded = JSON.parse(atob(payload));
                    bootstrapServer = decoded.server || null;
                    bootstrapToken = decoded.token || null;
                    bootstrapRole = decoded.role || null;
                }
            } catch (error) {
                log('falha ao consumir bootstrap codificado', error);
            }
        } else if (rawHash.includes('yt-sync-server=')) {
            const hashParams = new URLSearchParams(rawHash.replace(/^#/, ''));
            bootstrapServer = hashParams.get('yt-sync-server');
            bootstrapToken = hashParams.get('yt-sync-token');
            bootstrapRole = hashParams.get('yt-sync-role');
        } else {
            return;
        }

        if (bootstrapServer) {
            localStorage.setItem(SERVER_URL_KEY, bootstrapServer.trim().replace(/\/+$/, ''));
            bootstrapApplied = true;
        }

        if (bootstrapToken) {
            localStorage.setItem(TOKEN_KEY, bootstrapToken.trim());
            bootstrapApplied = true;
        }

        if (bootstrapRole === 'host' || bootstrapRole === 'client' || bootstrapRole === 'idle') {
            sessionStorage.setItem(ROLE_KEY, bootstrapRole);
            role = bootstrapRole;
            bootstrapApplied = true;
        }

        if (bootstrapApplied) {
            lastBootstrapHash = bootstrapKey;
            setSyncStatus(`bootstrap-${bootstrapRole || 'applied'}`);
            history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
        }
    }

    function applyRuntimeConfig(runtime, statusLabel) {
        if (!runtime || !runtime.public_url || !runtime.token) {
            return false;
        }

        const nextServer = String(runtime.public_url).trim().replace(/\/+$/, '');
        const nextToken = String(runtime.token).trim();
        const currentServer = getServerUrl();
        const currentToken = getToken();
        const changed = currentServer !== nextServer || currentToken !== nextToken;

        if (changed || !currentServer || !currentToken) {
            localStorage.setItem(SERVER_URL_KEY, nextServer);
            localStorage.setItem(TOKEN_KEY, nextToken);
            bootstrapApplied = true;
            setSyncStatus(statusLabel || 'runtime-auto');
            ensurePanel();
        }

        return changed;
    }

    async function tryAutoImportLocalRuntime(force = false) {
        try {
            const response = await new Promise((resolve, reject) => {
                GM_xmlhttpRequest({
                    method: 'GET',
                    url: 'http://127.0.0.1:8765/runtime',
                    onload: resolve,
                    onerror: reject,
                    ontimeout: reject
                });
            });

            if (!response || response.status < 200 || response.status >= 300 || !response.responseText) {
                return;
            }

            const runtime = JSON.parse(response.responseText);
            const changed = applyRuntimeConfig(runtime, force ? 'runtime-imported' : 'runtime-auto');
            if (!changed && force) {
                setSyncStatus('runtime-imported');
                ensurePanel();
            }
        } catch (error) {
            if (force) {
                log('falha ao importar runtime local', error);
                setSyncStatus('import-error');
            }
        }
    }

    function startLocalRuntimeWatcher() {
        if (localRuntimePollTimer) {
            window.clearInterval(localRuntimePollTimer);
        }

        localRuntimePollTimer = window.setInterval(() => {
            tryAutoImportLocalRuntime(false);
        }, 2000);
    }

    function getVideoId() {
        try {
            return new URL(window.location.href).searchParams.get('v');
        } catch (_error) {
            return null;
        }
    }

    function buildState() {
        if (!videoEl || videoEl.readyState < 2 || !Number.isFinite(videoEl.duration)) {
            return null;
        }

        return {
            video_id: getVideoId(),
            is_playing: !videoEl.paused && !videoEl.ended,
            progress_ms: Math.max(0, Math.floor(videoEl.currentTime * 1000)),
            duration_ms: Math.max(0, Math.floor(videoEl.duration * 1000))
        };
    }

    function ensurePanel() {
        if (!document.body) {
            return;
        }

        let root = document.getElementById('yt-sync-panel');
        role = getRole();

        if (!root) {
            root = document.createElement('div');
            root.id = 'yt-sync-panel';
            root.style.position = 'fixed';
            root.style.top = '12px';
            root.style.right = '12px';
            root.style.zIndex = '999999';
            root.style.width = '250px';
            root.style.padding = '10px';
            root.style.borderRadius = '12px';
            root.style.background = 'rgba(20,20,20,0.94)';
            root.style.color = '#fff';
            root.style.font = '12px/1.35 monospace';
            root.style.boxShadow = '0 8px 24px rgba(0,0,0,0.35)';

            const title = document.createElement('div');
            title.id = 'yt-sync-panel-title';
            title.style.fontWeight = '700';
            title.style.marginBottom = '8px';
            root.appendChild(title);

            const buttons = document.createElement('div');
            buttons.style.display = 'flex';
            buttons.style.gap = '6px';
            buttons.style.marginBottom = '8px';

            function makeButton(label, onClick) {
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = label;
                button.style.flex = '1';
                button.style.border = '0';
                button.style.borderRadius = '8px';
                button.style.padding = '6px 8px';
                button.style.cursor = 'pointer';
                button.style.font = '12px monospace';
                button.onclick = onClick;
                return button;
            }

            buttons.appendChild(makeButton('Host', () => setRole('host')));
            buttons.appendChild(makeButton('Client', () => setRole('client')));
            buttons.appendChild(makeButton('Idle', () => setRole('idle')));
            root.appendChild(buttons);

            const configButtons = document.createElement('div');
            configButtons.style.display = 'flex';
            configButtons.style.gap = '6px';
            configButtons.style.marginBottom = '8px';
            configButtons.appendChild(makeButton('Server URL', () => {
                const next = window.prompt('Cole a URL publica do tunnel ou a URL local do servidor:', getServerUrl());
                if (next !== null) {
                    localStorage.setItem(SERVER_URL_KEY, next.trim().replace(/\/+$/, ''));
                    ensurePanel();
                }
            }));
            configButtons.appendChild(makeButton('Token', () => {
                const next = window.prompt('Cole o token secreto:', getToken());
                if (next !== null) {
                    localStorage.setItem(TOKEN_KEY, next.trim());
                    ensurePanel();
                }
            }));
            configButtons.appendChild(makeButton('Import Local', () => {
                tryAutoImportLocalRuntime(true);
            }));
            root.appendChild(configButtons);

            const jamRow = document.createElement('div');
            jamRow.id = 'yt-sync-jam-row';
            jamRow.style.display = 'flex';
            jamRow.style.gap = '6px';
            jamRow.style.marginBottom = '8px';
            jamRow.appendChild(makeButton('Jam Toggle', () => {
                updateJamControl(!jamControlEnabled);
            }));
            root.appendChild(jamRow);

            const details = document.createElement('div');
            details.id = 'yt-sync-panel-details';
            details.style.whiteSpace = 'pre-wrap';
            details.style.opacity = '0.85';
            root.appendChild(details);

            document.body.appendChild(root);
        }

        const title = root.querySelector('#yt-sync-panel-title');
        const details = root.querySelector('#yt-sync-panel-details');
        const jamRow = root.querySelector('#yt-sync-jam-row');
        const serverUrl = getServerUrl() || '(nao definido)';
        const token = getToken();

        title.textContent = `YT Sync ${role.toUpperCase()}`;
        root.style.background = role === 'host'
            ? 'rgba(16,128,67,0.94)'
            : role === 'client'
                ? 'rgba(0,102,204,0.94)'
                : 'rgba(60,60,60,0.94)';

        if (jamRow) {
            jamRow.style.display = role === 'host' ? 'flex' : 'none';
        }

        if (details) {
            details.textContent = [
                `Tab: ${TAB_ID.slice(-6)}`,
                `Server: ${serverUrl}`,
                `Token: ${token ? 'ok' : 'faltando'}`,
                `Status: ${syncStatus}`,
                bootstrapApplied ? 'Bootstrap: ok' : null,
                role === 'host' ? `Jam control: ${jamConfigLoaded ? (jamControlEnabled ? 'on' : 'off') : 'loading...'}` : null
            ].filter(Boolean).join('\n');
        }
    }

    function bootPanel() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => ensurePanel(), { once: true });
        } else {
            ensurePanel();
        }
    }

    async function apiFetch(path, options = {}) {
        const serverUrl = getServerUrl();
        if (!serverUrl) {
            setSyncStatus('missing-server');
            return null;
        }

        try {
            const response = await new Promise((resolve, reject) => {
                GM_xmlhttpRequest({
                    method: options.method || 'GET',
                    url: `${serverUrl}${path}`,
                    headers: {
                        ...getHeaders(),
                        ...(options.headers || {})
                    },
                    data: options.body || null,
                    onload: resolve,
                    onerror: reject,
                    ontimeout: reject
                });
            });

            if (!response || response.status < 200 || response.status >= 300) {
                const statusCode = response ? response.status : 'error';
                log('falha http', statusCode, path);
                setSyncStatus(`http-${statusCode}`);
                return null;
            }

            const responseHeaders = String(response.responseHeaders || '');
            const contentTypeMatch = responseHeaders.match(/content-type:\s*([^\r\n]+)/i);
            const contentType = contentTypeMatch ? contentTypeMatch[1] : '';
            if (contentType.includes('application/json')) {
                return JSON.parse(response.responseText);
            }

            return response.responseText;
        } catch (error) {
            log('falha de rede', path, error);
            setSyncStatus('network-error');
            return null;
        }
    }

    async function refreshJamControl() {
        const result = await apiFetch('/config');
        if (!result) {
            return;
        }

        jamControlEnabled = !!result.jam_control_enabled;
        jamConfigLoaded = true;
        ensurePanel();
        updatePollingBehavior();
    }

    async function updateJamControl(enabled) {
        if (getRole() !== 'host') {
            return;
        }

        const result = await apiFetch('/config', {
            method: 'POST',
            body: JSON.stringify({
                jam_control_enabled: !!enabled
            })
        });

        if (!result) {
            return;
        }

        jamControlEnabled = !!result.jam_control_enabled;
        jamConfigLoaded = true;
        ensurePanel();
        updatePollingBehavior();
    }

    async function publishState(reason) {
        const currentRole = getRole();
        const canControl = currentRole === 'host' || (currentRole === 'client' && jamControlEnabled);
        if (!canControl) {
            return;
        }

        if (Date.now() < suppressPublishUntil) {
            return;
        }

        const state = buildState();
        if (!state || !state.video_id) {
            return;
        }

        const now = Date.now();
        if (reason === 'PROGRESS' && now - lastPublishedAt < 900) {
            return;
        }
        lastPublishedAt = now;

        await apiFetch('/publish', {
            method: 'POST',
            body: JSON.stringify({
                type: reason,
                sender: TAB_ID,
                sender_role: currentRole,
                timestamp: now,
                state
            })
        });
    }

    function attachHostVideo(video) {
        if (!video || video === attachedVideo) {
            return;
        }

        if (attachedVideo) {
            attachedVideo.removeEventListener('play', onHostPlay);
            attachedVideo.removeEventListener('pause', onHostPause);
            attachedVideo.removeEventListener('seeked', onHostSeeked);
            attachedVideo.removeEventListener('loadedmetadata', onHostLoadedMetadata);
            attachedVideo.removeEventListener('timeupdate', onHostTimeUpdate);
        }

        attachedVideo = video;
        videoEl = video;
        video.addEventListener('play', onHostPlay);
        video.addEventListener('pause', onHostPause);
        video.addEventListener('seeked', onHostSeeked);
        video.addEventListener('loadedmetadata', onHostLoadedMetadata);
        video.addEventListener('timeupdate', onHostTimeUpdate);
        publishState('STATE_SNAPSHOT');
    }

    function onHostPlay() {
        publishState('PLAY');
    }

    function onHostPause() {
        publishState('PAUSE');
    }

    function onHostSeeked() {
        publishState('SEEK');
    }

    function onHostLoadedMetadata() {
        publishState('TRACK_CHANGE');
    }

    function onHostTimeUpdate() {
        publishState('PROGRESS');
    }

    function onControlPlay() {
        publishState('PLAY');
    }

    function onControlPause() {
        publishState('PAUSE');
    }

    function onControlSeeked() {
        publishState('SEEK');
    }

    function onControlLoadedMetadata() {
        publishState('TRACK_CHANGE');
    }

    function onControlTimeUpdate() {
        publishState('PROGRESS');
    }

    function attachControlVideo(video) {
        if (!video || video === attachedControlVideo) {
            return;
        }

        if (attachedControlVideo) {
            attachedControlVideo.removeEventListener('play', onControlPlay);
            attachedControlVideo.removeEventListener('pause', onControlPause);
            attachedControlVideo.removeEventListener('seeked', onControlSeeked);
            attachedControlVideo.removeEventListener('loadedmetadata', onControlLoadedMetadata);
            attachedControlVideo.removeEventListener('timeupdate', onControlTimeUpdate);
        }

        attachedControlVideo = video;
        video.addEventListener('play', onControlPlay);
        video.addEventListener('pause', onControlPause);
        video.addEventListener('seeked', onControlSeeked);
        video.addEventListener('loadedmetadata', onControlLoadedMetadata);
        video.addEventListener('timeupdate', onControlTimeUpdate);
    }

    function clampTime(seconds, durationMs) {
        const durationSeconds = Number.isFinite(durationMs) ? durationMs / 1000 : Infinity;
        return Math.max(0, Math.min(seconds, durationSeconds || Infinity));
    }

    function loadVideo(videoId) {
        if (!videoId) {
            return;
        }

        if (getVideoId() === videoId) {
            return;
        }

        lastRequestedVideoId = videoId;
        lastNavigationAt = Date.now();
        setSyncStatus(`loading-${videoId}`);
        window.location.assign(`https://music.youtube.com/watch?v=${encodeURIComponent(videoId)}`);
    }

    function ensureTargetVideoLoaded(packet) {
        if (!packet || !packet.state || !packet.state.video_id) {
            return;
        }

        const targetVideoId = packet.state.video_id;
        const currentVideoId = getVideoId();

        if (currentVideoId !== targetVideoId) {
            loadVideo(targetVideoId);
            return;
        }

        if (!getVideo() && Date.now() - lastNavigationAt > 2500) {
            loadVideo(targetVideoId);
        }
    }

    async function applyPlaybackState(state) {
        if (!videoEl) {
            return;
        }

        if (state.is_playing && videoEl.paused) {
            const playPromise = videoEl.play();
            if (playPromise && typeof playPromise.catch === 'function') {
                playPromise.catch((error) => {
                    const isBenignAbort = error && (
                        error.name === 'AbortError'
                        || String(error.message || '').includes('aborted by the user agent')
                    );

                    if (!isBenignAbort) {
                        log('falha ao dar play', error);
                    }
                });
            }
        }

        if (!state.is_playing && !videoEl.paused) {
            videoEl.pause();
        }
    }

    async function syncState(packet) {
        if (!packet || !packet.state) {
            return;
        }

        const { state, timestamp = Date.now(), revision = 0 } = packet;
        if (typeof packet.jam_control_enabled === 'boolean') {
            jamControlEnabled = packet.jam_control_enabled;
            jamConfigLoaded = true;
            ensurePanel();
            updatePollingBehavior();
        }
        if (revision && revision <= lastAppliedRevision) {
            return;
        }

        if (getRole() === 'host' && !jamControlEnabled) {
            return;
        }

        if (packet.sender === TAB_ID) {
            lastAppliedRevision = revision || lastAppliedRevision;
            setSyncStatus('control-sent');
            return;
        }

        videoEl = getVideo();
        if (!videoEl || isApplying) {
            pendingState = packet;
            return;
        }

        isApplying = true;
        suppressPublishUntil = Date.now() + 1200;
        try {
            const latencyMs = Math.max(0, Date.now() - timestamp);
            const targetSeconds = clampTime((state.progress_ms + latencyMs) / 1000, state.duration_ms);
            const diffSeconds = targetSeconds - videoEl.currentTime;

            if (Math.abs(diffSeconds) > 1.5) {
                videoEl.currentTime = targetSeconds;
                videoEl.playbackRate = 1;
            } else if (Math.abs(diffSeconds) > 0.25 && state.is_playing) {
                videoEl.playbackRate = diffSeconds > 0 ? 1.04 : 0.96;
            } else {
                videoEl.playbackRate = 1;
            }

            await applyPlaybackState(state);
            lastAppliedRevision = revision || lastAppliedRevision;
            lastRequestedVideoId = state.video_id || lastRequestedVideoId;
            setSyncStatus(`synced-${state.video_id || 'ok'}`);
        } finally {
            window.setTimeout(() => {
                isApplying = false;
                if (pendingState) {
                    const next = pendingState;
                    pendingState = null;
                    syncState(next);
                }
            }, 150);
        }
    }

    function tryApplyPendingTrackState() {
        if (!videoEl || !pendingTrackState || videoEl.readyState < 2) {
            return;
        }

        const next = pendingTrackState;
        pendingTrackState = null;
        syncState(next);
    }

    async function pollState() {
        const currentRole = getRole();
        const canPoll = currentRole === 'client' || (currentRole === 'host' && jamControlEnabled);
        if (!canPoll) {
            return;
        }

        const packet = await apiFetch('/state');
        if (!packet || !packet.state) {
            setSyncStatus('waiting-state');
            return;
        }

        if (typeof packet.jam_control_enabled === 'boolean') {
            jamControlEnabled = packet.jam_control_enabled;
            jamConfigLoaded = true;
            ensurePanel();
            updatePollingBehavior();
        }

        const currentVideoId = getVideoId();
        if (packet.state.video_id && currentVideoId !== packet.state.video_id) {
            pendingTrackState = packet;
            ensureTargetVideoLoaded(packet);
            return;
        }

        if (packet.state.video_id && !getVideo()) {
            pendingTrackState = packet;
            ensureTargetVideoLoaded(packet);
            return;
        }

        syncState(packet);
    }

    function startClientPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
        }
        pollTimer = setInterval(pollState, POLL_INTERVAL_MS);
        refreshJamControl();
        pollState();
    }

    function stopClientPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function updatePollingBehavior() {
        const currentRole = getRole();
        const shouldPoll = currentRole === 'client' || (currentRole === 'host' && jamControlEnabled);

        if (shouldPoll) {
            if (!pollTimer) {
                startClientPolling();
            }
        } else {
            stopClientPolling();
        }
    }

    function startHostMode() {
        setSyncStatus('host-ready');
        const observer = new MutationObserver(() => {
            const nextVideo = getVideo();
            if (nextVideo) {
                attachHostVideo(nextVideo);
            }
        });

        observer.observe(document.body || document.documentElement, { childList: true, subtree: true });
        attachHostVideo(getVideo());
        refreshJamControl();
        log('host ativo na aba', TAB_ID);
    }

    function startClientMode() {
        setSyncStatus('client-starting');
        const observer = new MutationObserver(() => {
            const nextVideo = getVideo();
            if (nextVideo && nextVideo !== videoEl) {
                videoEl = nextVideo;
                videoEl.playbackRate = 1;
                attachControlVideo(videoEl);
                videoEl.addEventListener('loadeddata', tryApplyPendingTrackState, { once: true });
                videoEl.addEventListener('canplay', tryApplyPendingTrackState, { once: true });

                if (pendingTrackState) {
                    tryApplyPendingTrackState();
                } else if (getVideoId()) {
                    setSyncStatus(`video-ready-${getVideoId()}`);
                }
            }
        });

        observer.observe(document.body || document.documentElement, { childList: true, subtree: true });
        videoEl = getVideo();
        attachControlVideo(videoEl);
        startClientPolling();
        log('client ativo na aba', TAB_ID);
    }

    consumeBootstrapConfig();
    tryAutoImportLocalRuntime();
    bootPanel();
    startLocalRuntimeWatcher();

    window.addEventListener('hashchange', consumeBootstrapConfig);
    window.addEventListener('DOMContentLoaded', consumeBootstrapConfig, { once: true });
    window.setTimeout(consumeBootstrapConfig, 250);
    window.setTimeout(consumeBootstrapConfig, 1200);

    if (role === 'host') {
        startHostMode();
    } else if (role === 'client') {
        startClientMode();
    } else {
        log('script em idle na aba', TAB_ID);
    }
})();
