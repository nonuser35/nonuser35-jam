// ==UserScript==
// @name         YT Music Sync Client
// @namespace    yt-music-sync
// @version      1.0.0
// @description  Recebe o estado do host e aplica play, pause, seek e troca de faixa no YT Music.
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

    if (ROLE !== 'client') {
        bootRolePanel();
        console.log('[yt-sync][client] script desativado. role atual =', ROLE);
        return;
    }

    const channel = new BroadcastChannel(CHANNEL_NAME);
    const INSTANCE_ID = `client-${Math.random().toString(36).slice(2)}`;

    let videoEl = null;
    let isApplying = false;
    let pendingState = null;
    let pendingTrackState = null;

    function log(...args) {
        console.log('[yt-sync][client]', ...args);
    }

    function getVideo() {
        return document.querySelector('video');
    }

    function getCurrentVideoId() {
        try {
            return new URL(window.location.href).searchParams.get('v');
        } catch (_error) {
            return null;
        }
    }

    function clampTime(seconds, durationMs) {
        const durationSeconds = Number.isFinite(durationMs) ? durationMs / 1000 : Infinity;
        return Math.max(0, Math.min(seconds, durationSeconds || Infinity));
    }

    function requestState() {
        channel.postMessage({
            type: 'REQUEST_STATE',
            timestamp: Date.now(),
            sender: INSTANCE_ID
        });
    }

    function loadVideo(videoId) {
        if (!videoId) {
            return;
        }

        const currentVideoId = getCurrentVideoId();
        if (currentVideoId === videoId) {
            return;
        }

        log('abrindo faixa', videoId);
        window.location.href = `https://music.youtube.com/watch?v=${encodeURIComponent(videoId)}`;
    }

    function tryApplyPendingTrackState() {
        if (!videoEl || !pendingTrackState) {
            return;
        }

        if (videoEl.readyState < 2) {
            return;
        }

        const next = pendingTrackState;
        pendingTrackState = null;
        sync(next.state, next.timestamp);
    }

    async function applyPlaybackState(state) {
        if (!videoEl) {
            return;
        }

        const playPromise = state.is_playing && videoEl.paused ? videoEl.play() : null;
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

        if (!state.is_playing && !videoEl.paused) {
            videoEl.pause();
        }
    }

    async function sync(state, timestamp) {
        if (!videoEl || isApplying) {
            pendingState = { state, timestamp };
            return;
        }

        isApplying = true;

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
        } finally {
            window.setTimeout(() => {
                isApplying = false;

                if (pendingState) {
                    const next = pendingState;
                    pendingState = null;
                    sync(next.state, next.timestamp);
                }
            }, 150);
        }
    }

    function handleIncomingMessage(data) {
        const { type, state, timestamp, sender } = data || {};
        if (!state || sender === INSTANCE_ID) {
            return;
        }

        videoEl = getVideo();
        const currentVideoId = getCurrentVideoId();

        if (type === 'TRACK_CHANGE') {
            pendingTrackState = { state, timestamp };
            loadVideo(state.video_id);

            if (videoEl && getCurrentVideoId() === state.video_id) {
                tryApplyPendingTrackState();
            }
            return;
        }

        if (state.video_id && currentVideoId !== state.video_id) {
            pendingTrackState = { state, timestamp };
            loadVideo(state.video_id);
            return;
        }

        if (!videoEl) {
            pendingState = { state, timestamp };
            return;
        }

        log('recebido', type, state.video_id);
        sync(state, timestamp);
    }

    channel.onmessage = (event) => {
        handleIncomingMessage(event.data);
    };

    const observer = new MutationObserver(() => {
        const nextVideo = getVideo();
        if (nextVideo && nextVideo !== videoEl) {
            videoEl = nextVideo;
            videoEl.playbackRate = 1;
            log('video conectado');

            videoEl.addEventListener('loadeddata', tryApplyPendingTrackState, { once: true });
            videoEl.addEventListener('canplay', tryApplyPendingTrackState, { once: true });

            if (pendingTrackState) {
                tryApplyPendingTrackState();
            } else if (pendingState) {
                const next = pendingState;
                pendingState = null;
                sync(next.state, next.timestamp);
            } else {
                requestState();
            }
        }
    });

    observer.observe(document.body || document.documentElement, { childList: true, subtree: true });

    bootRolePanel();
    videoEl = getVideo();
    requestState();
    log('client ativo na aba', TAB_ID);
})();
