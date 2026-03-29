export let syncedLyrics = [];
export let lyricCandidates = [];
export let currentCandidateIndex = -1;
const LYRIC_ENTRY_DELAY = 0.06;
const LYRIC_EXIT_GRACE = 0.4;
let translatedMode = false;
let translationLoading = false;
let translationPrefetching = false;
let lyricsLoadToken = 0;
let translationRequestToken = 0;
const PARTIAL_TRANSLATION_LINE_LIMIT = 4;
const PROGRESSIVE_TRANSLATION_LINE_LIMITS = [PARTIAL_TRANSLATION_LINE_LIMIT, 12, 0];

function emitLyricsStateChange() {
    try {
        window.dispatchEvent(new CustomEvent('lyrics-state-change'));
    } catch (_error) {
        // noop
    }
}

function buildApiUrl(path) {
    return path;
}

function buildHostHeaders() {
    const hostToken = new URLSearchParams(window.location.search).get('host') || '';
    return hostToken ? { 'X-Host-Token': hostToken } : {};
}

function normalizeKey(value) {
    return (value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

function getTrackCacheKey(artist, track) {
    return `nonuser35-lyrics:${normalizeKey(artist)}:${normalizeKey(track)}`;
}

export function clearLikedLyrics(artist, track) {
    localStorage.removeItem(getTrackCacheKey(artist, track));
}

export function isCurrentLyricsLiked(artist, track) {
    const current = currentCandidateIndex >= 0 ? lyricCandidates[currentCandidateIndex] : null;
    if (!current) return false;
    return localStorage.getItem(getTrackCacheKey(artist, track)) === current.fingerprint;
}

function getCandidateFingerprint(candidate) {
    if (!candidate) return "";
    return [
        candidate.id || "",
        candidate.trackName || "",
        candidate.artistName || "",
        candidate.albumName || "",
        candidate.source || ""
    ].join("::");
}

function parseLRC(lrcText) {
    const lines = lrcText.split("\n");
    const result = [];
    const timeReg = /\[(\d{2}):(\d{2})\.(\d{2,3})\]/;

    lines.forEach((line) => {
        const match = timeReg.exec(line);
        if (match) {
            const msParse = parseFloat(`0.${match[3]}`);
            const time = parseInt(match[1], 10) * 60 + parseInt(match[2], 10) + msParse;
            const text = line.replace(timeReg, "").trim();
            if (text) result.push({ time, text });
        }
    });

    return result;
}

function estimateLineDuration(line, nextLine) {
    const text = (line?.text || "").trim();
    const words = text ? text.split(/\s+/).length : 0;
    const baseDuration = Math.min(6.2, Math.max(1.8, words * 0.56 + text.length * 0.028));

    if (!nextLine) {
        return baseDuration;
    }

    const gap = Math.max(0, nextLine.time - line.time);
    if (gap <= 0) {
        return baseDuration;
    }

    return Math.min(
        Math.max(baseDuration, gap * 0.88),
        Math.max(1.18, gap + 0.16)
    );
}

function getActiveLineFromCollection(lines, currentTime) {
    if (!Array.isArray(lines) || lines.length === 0) {
        return null;
    }

    for (let i = 0; i < lines.length; i += 1) {
        const line = lines[i];
        const nextLine = lines[i + 1] || null;
        const lineStart = line.time + LYRIC_ENTRY_DELAY;
        const lineEnd = line.time + estimateLineDuration(line, nextLine) + LYRIC_EXIT_GRACE;

        if (currentTime >= lineStart && currentTime <= lineEnd) {
            return line;
        }
    }

    return null;
}

function buildLyricsCandidate(result, index) {
    const hasSyncedLyrics = !!result.syncedLyrics;
    const lyrics = hasSyncedLyrics ? parseLRC(result.syncedLyrics) : [];
    const translatedLyrics = Array.isArray(result.translatedLyrics) && lyrics.length
        ? lyrics.map((line, lineIndex) => ({
            ...line,
            text: String(result.translatedLyrics[lineIndex] ?? line.text).trim() || line.text
        }))
        : [];

    const candidate = {
        id: result.id || `${result.artistName || "artist"}-${result.trackName || "track"}-${index}`,
        source: result.source || "LRCLIB",
        trackName: result.trackName || "",
        artistName: result.artistName || "",
        albumName: result.albumName || "",
        hasSyncedLyrics,
        lyrics,
        translatedLyrics,
        translationState: Array.isArray(translatedLyrics) && translatedLyrics.length ? 'full' : 'idle'
    };

    candidate.fingerprint = getCandidateFingerprint(candidate);
    return candidate;
}

function applyCandidate(index) {
    if (!lyricCandidates.length || index < 0 || index >= lyricCandidates.length) {
        currentCandidateIndex = -1;
        syncedLyrics = [];
        return null;
    }

    currentCandidateIndex = index;
    const candidate = lyricCandidates[index];
    syncedLyrics = translatedMode && Array.isArray(candidate.translatedLyrics) && candidate.translatedLyrics.length
        ? candidate.translatedLyrics
        : candidate.lyrics;
    return candidate;
}

async function requestCandidateTranslation(candidate, requestToken, options = {}) {
    if (!candidate || !Array.isArray(candidate.lyrics) || !candidate.lyrics.length) {
        return null;
    }

    const lineLimit = Number.isFinite(options.lineLimit) ? Math.max(0, Number(options.lineLimit)) : 0;
    const sourceLines = candidate.lyrics.map((line) => line.text);

    const response = await fetch(buildApiUrl('/lyrics/translate'), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...buildHostHeaders()
        },
        body: JSON.stringify({
            lines: sourceLines,
            target: 'pt-BR',
            line_limit: lineLimit || undefined
        })
    });

    if (!response.ok || requestToken !== translationRequestToken) {
        return null;
    }

    const payload = await response.json();
    const translatedLines = Array.isArray(payload?.lines)
        ? payload.lines.map((line) => String(line ?? '').trim())
        : [];

    if (!translatedLines.length || translatedLines.every((line) => !line)) {
        return null;
    }

    const mergedLyrics = candidate.lyrics.map((line, index) => ({
        ...line,
        text: translatedLines[index] || line.text
    }));
    candidate.translatedLyrics = mergedLyrics;
    candidate.translationState = lineLimit > 0 ? 'preview' : 'full';
    return candidate.translatedLyrics;
}

async function progressivelyTranslateCandidate(candidate, requestToken, options = {}) {
    if (!candidate) return null;
    const shouldStartFromPreviewOnly = !!options.previewOnly;
    let latestResult = null;
    const limits = shouldStartFromPreviewOnly
        ? [PARTIAL_TRANSLATION_LINE_LIMIT]
        : PROGRESSIVE_TRANSLATION_LINE_LIMITS;

    for (const lineLimit of limits) {
        if (requestToken !== translationRequestToken) {
            break;
        }
        const translated = await requestCandidateTranslation(candidate, requestToken, {
            lineLimit
        });
        if (!translated) {
            if (lineLimit === 0) {
                break;
            }
            continue;
        }
        latestResult = translated;
        if (translatedMode && lyricCandidates[currentCandidateIndex] === candidate) {
            syncedLyrics = candidate.translatedLyrics;
        }
        emitLyricsStateChange();
    }

    return latestResult;
}

export async function preloadTranslationForCurrentCandidate() {
    const candidate = currentCandidateIndex >= 0 ? lyricCandidates[currentCandidateIndex] : null;
    if (!candidate || translationLoading || translationPrefetching) {
        return null;
    }
    if (candidate.translationState === 'full' && Array.isArray(candidate.translatedLyrics) && candidate.translatedLyrics.length) {
        return candidate.translatedLyrics;
    }

    const requestToken = ++translationRequestToken;
    translationPrefetching = true;
    try {
        if (Array.isArray(candidate.translatedLyrics) && candidate.translatedLyrics.length && candidate.translationState !== 'full') {
            return await progressivelyTranslateCandidate(candidate, requestToken);
        }
        return await progressivelyTranslateCandidate(candidate, requestToken);
    } catch (_error) {
        return null;
    } finally {
        translationPrefetching = false;
        emitLyricsStateChange();
    }
}

export async function fetchLyrics(artist, track) {
    const requestToken = ++lyricsLoadToken;
    translationRequestToken += 1;
    lyricCandidates = [];
    currentCandidateIndex = -1;
    translatedMode = false;
    translationLoading = false;

    try {
        const params = new URLSearchParams({
            artist,
            track
        });

        const url = `${buildApiUrl('/lyrics/search')}?${params.toString()}`;
        const response = await fetch(url);
        const payload = await response.json();
        if (requestToken !== lyricsLoadToken) {
            return null;
        }
        const results = Array.isArray(payload?.candidates) ? payload.candidates : [];

        if (Array.isArray(results) && results.length > 0) {
            lyricCandidates = results
                .slice(0, 8)
                .map(buildLyricsCandidate)
                .filter((candidate) => candidate.hasSyncedLyrics && Array.isArray(candidate.lyrics) && candidate.lyrics.length > 0);

            if (lyricCandidates.length > 0) {
                const cacheKey = getTrackCacheKey(artist, track);
                const savedFingerprint = localStorage.getItem(cacheKey);
                const savedIndex = lyricCandidates.findIndex((candidate) => candidate.fingerprint === savedFingerprint);
                const firstSyncedIndex = lyricCandidates.findIndex((candidate) => candidate.hasSyncedLyrics);
                const defaultIndex = savedIndex >= 0
                    ? savedIndex
                    : (firstSyncedIndex >= 0 ? firstSyncedIndex : 0);

                if (requestToken !== lyricsLoadToken) {
                    return null;
                }
                const selectedCandidate = applyCandidate(defaultIndex);
                emitLyricsStateChange();
                preloadTranslationForCurrentCandidate().catch(() => null);
                return selectedCandidate;
            }
        }

        syncedLyrics = [];
        return null;
    } catch (error) {
        syncedLyrics = [];
        return null;
    }
}

export function getLyricsUiState() {
    const current = currentCandidateIndex >= 0 ? lyricCandidates[currentCandidateIndex] : null;
    return {
        sourceLabel: current ? `${current.source} ${currentCandidateIndex + 1}/${lyricCandidates.length}` : "Sem letra sincronizada",
        canLike: !!current,
        canDislike: lyricCandidates.length > 1 && currentCandidateIndex < lyricCandidates.length - 1,
        canTranslate: !!current,
        isTranslated: translatedMode,
        isTranslating: translationLoading || translationPrefetching,
        hasCachedTranslation: !!(current && Array.isArray(current.translatedLyrics) && current.translatedLyrics.length),
        hasFullTranslation: !!(current && current.translationState === 'full'),
        totalCandidates: lyricCandidates.length,
        currentCandidate: current
    };
}

export function isTranslationEnabled() {
    return translatedMode;
}

export function likeCurrentLyrics(artist, track) {
    const current = currentCandidateIndex >= 0 ? lyricCandidates[currentCandidateIndex] : null;
    if (!current) return false;

    localStorage.setItem(getTrackCacheKey(artist, track), current.fingerprint);
    return true;
}

export function dislikeCurrentLyrics() {
    translatedMode = false;
    translationLoading = false;
    translationRequestToken += 1;

    if (!lyricCandidates.length) {
        syncedLyrics = [];
        return null;
    }

    const nextIndex = currentCandidateIndex + 1;
    if (nextIndex >= lyricCandidates.length) {
        syncedLyrics = [];
        return null;
    }

    return applyCandidate(nextIndex);
}

export async function toggleTranslation() {
    const current = currentCandidateIndex >= 0 ? lyricCandidates[currentCandidateIndex] : null;
    if (!current) return null;

    if (translatedMode) {
        translatedMode = false;
        syncedLyrics = current.lyrics;
        return current;
    }

    if (translationLoading) return null;

    const requestToken = ++translationRequestToken;
    translationLoading = true;

    try {
        if (!Array.isArray(current.translatedLyrics) || !current.translatedLyrics.length) {
            const translatedLines = await progressivelyTranslateCandidate(current, requestToken, {
                previewOnly: true
            });
            if (
                !translatedLines ||
                requestToken !== translationRequestToken ||
                currentCandidateIndex < 0 ||
                lyricCandidates[currentCandidateIndex] !== current
            ) {
                return null;
            }
        }

        if (
            requestToken !== translationRequestToken ||
            currentCandidateIndex < 0 ||
            lyricCandidates[currentCandidateIndex] !== current
        ) {
            return null;
        }

        translatedMode = true;
        syncedLyrics = current.translatedLyrics;
        emitLyricsStateChange();
        if (current.translationState !== 'full') {
            setTimeout(() => {
                preloadTranslationForCurrentCandidate().catch(() => null);
            }, 180);
        }
        return current;
    } finally {
        translationLoading = false;
        emitLyricsStateChange();
    }
}

export function getActiveLyricAtTime(currentTime) {
    return getActiveLineFromCollection(syncedLyrics, currentTime);
}

export function getActiveOriginalLyricAtTime(currentTime) {
    const current = currentCandidateIndex >= 0 ? lyricCandidates[currentCandidateIndex] : null;
    return getActiveLineFromCollection(current?.lyrics || [], currentTime);
}

export function getActiveTranslatedLyricAtTime(currentTime) {
    const current = currentCandidateIndex >= 0 ? lyricCandidates[currentCandidateIndex] : null;
    return getActiveLineFromCollection(current?.translatedLyrics || [], currentTime);
}

export function resetLyrics() {
    lyricsLoadToken += 1;
    translationRequestToken += 1;
    syncedLyrics = [];
    lyricCandidates = [];
    currentCandidateIndex = -1;
    translatedMode = false;
    translationLoading = false;
    translationPrefetching = false;
    emitLyricsStateChange();
}
