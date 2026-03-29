// ==UserScript==
// @name         YT Music Pro Sync Tracker (Host)
// @namespace    yt-music-sync
// @version      1.0.0
// @description  Publica o estado atual do YT Music para outras abas/janelas no mesmo navegador/perfil.
// @match        https://music.youtube.com/*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    const CHANNEL_NAME = 'yt-sync';
    const ROLE_KEY = 'yt-sync-role';
    const TAB_ID_KEY = 'yt-sync-tab-id';
    const ROLE = sessionStorage.getItem(ROLE_KEY) || 'client';
    const TAB_ID = sessionStorage.getItem(TAB_ID_KEY) || `tab-${Math.random().toString(36).slice(2)}`;

    sessionStorage.setItem(TAB_ID_KEY, TAB_ID);

    function ensureRolePanel() {
        if (!document.body) {
            return;
        }

        let root = document.getElementById('yt-sync-role-panel');
        const currentRole = sessionStorage.getItem(ROLE_KEY) || 'client';

        if (!root) {
            root = document.createElement('div');
            root.id = 'yt-sync-role-panel';
            root.style.position = 'fixed';
            root.style.top = '12px';
            root.style.right = '12px';
            root.style.zIndex = '999999';
            root.style.minWidth = '180px';
            root.style.padding = '10px';
            root.style.borderRadius = '12px';
            root.style.background = 'rgba(20, 20, 20, 0.94)';
            root.style.color = '#fff';
            root.style.font = '12px/1.3 monospace';
            root.style.boxShadow = '0 8px 24px rgba(0,0,0,0.35)';
            root.style.pointerEvents = 'auto';

            const title = document.createElement('div');
            title.id = 'yt-sync-role-panel-title';
            title.style.marginBottom = '8px';
            title.style.fontWeight = '700';
            root.appendChild(title);

            const buttons = document.createElement('div');
            buttons.style.display = 'flex';
            buttons.style.gap = '6px';
            buttons.style.marginBottom = '6px';

            function makeButton(label, nextRole) {
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = label;
                button.style.flex = '1';
                button.style.border = '0';
                button.style.borderRadius = '8px';
                button.style.padding = '6px 8px';
                button.style.cursor = 'pointer';
                button.style.font = '12px monospace';
                button.onclick = () => {
                    if (nextRole) {
                        sessionStorage.setItem(ROLE_KEY, nextRole);
                    } else {
                        sessionStorage.removeItem(ROLE_KEY);
                    }
                    window.location.reload();
                };
                return button;
            }

            buttons.appendChild(makeButton('Host', 'host'));
            buttons.appendChild(makeButton('Client', 'client'));
            buttons.appendChild(makeButton('Clear', null));
            root.appendChild(buttons);

            const note = document.createElement('div');
            note.textContent = `Tab ${TAB_ID.slice(-6)}`;
            note.style.opacity = '0.75';
            root.appendChild(note);

            document.body.appendChild(root);
        }

        const title = root.querySelector('#yt-sync-role-panel-title');
        if (title) {
            title.textContent = `YT Sync: ${currentRole.toUpperCase()}`;
            root.style.background = currentRole === 'host'
                ? 'rgba(16, 128, 67, 0.94)'
                : 'rgba(0, 102, 204, 0.94)';
        }
    }

    function bootRolePanel() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => ensureRolePanel(), { once: true });
        } else {
            ensureRolePanel();
        }
    }

    if (ROLE !== 'host') {
        bootRolePanel();
        console.log('[yt-sync][host] script desativado. role atual =', ROLE);
        return;
    }

    const channel = new BroadcastChannel(CHANNEL_NAME);
    const INSTANCE_ID = `host-${Math.random().toString(36).slice(2)}`;

    let videoEl = null;
    let attachedVideo = null;
    let lastVideoId = null;
    let lastProgressEmitAt = 0;
    function log(...args) {
        console.log('[yt-sync][host]', ...args);
    }

    function getVideoId() {
        try {
            return new URL(window.location.href).searchParams.get('v');
        } catch (_error) {
            return null;
        }
    }

    function getVideo() {
        return document.querySelector('video');
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

    function emit(type) {
        const state = buildState();
        if (!state || !state.video_id) {
            return;
        }

        channel.postMessage({
            type,
            state,
            timestamp: Date.now(),
            sender: INSTANCE_ID
        });

        log('emit', type, state);
    }

    function onPlay() {
        emit('PLAY');
    }

    function onPause() {
        emit('PAUSE');
    }

    function onSeeked() {
        emit('SEEK');
    }

    function onLoadedMetadata() {
        emit('TRACK_CHANGE');
    }

    function onTimeUpdate() {
        const now = Date.now();
        if (now - lastProgressEmitAt >= 1000) {
            lastProgressEmitAt = now;
            emit('PROGRESS');
        }
    }

    function attachVideo(video) {
        if (!video || video === attachedVideo) {
            return;
        }

        if (attachedVideo) {
            attachedVideo.removeEventListener('play', onPlay);
            attachedVideo.removeEventListener('pause', onPause);
            attachedVideo.removeEventListener('seeked', onSeeked);
            attachedVideo.removeEventListener('loadedmetadata', onLoadedMetadata);
            attachedVideo.removeEventListener('timeupdate', onTimeUpdate);
        }

        videoEl = video;
        attachedVideo = video;
        lastProgressEmitAt = 0;

        video.addEventListener('play', onPlay);
        video.addEventListener('pause', onPause);
        video.addEventListener('seeked', onSeeked);
        video.addEventListener('loadedmetadata', onLoadedMetadata);
        video.addEventListener('timeupdate', onTimeUpdate);

        log('video conectado');
        emit('STATE_SNAPSHOT');
    }

    function detectTrackChange() {
        const id = getVideoId();
        if (id && id !== lastVideoId) {
            lastVideoId = id;
            emit('TRACK_CHANGE');
        }
    }

    channel.onmessage = (event) => {
        const data = event.data || {};
        if (data.sender === INSTANCE_ID) {
            return;
        }

        if (data.type === 'REQUEST_STATE') {
            emit('STATE_SNAPSHOT');
        }
    };

    const observer = new MutationObserver(() => {
        const nextVideo = getVideo();
        if (nextVideo) {
            attachVideo(nextVideo);
        }
    });

    observer.observe(document.body || document.documentElement, { childList: true, subtree: true });

    bootRolePanel();
    attachVideo(getVideo());
    setInterval(detectTrackChange, 1000);
    log('host ativo na aba', TAB_ID);
})();
