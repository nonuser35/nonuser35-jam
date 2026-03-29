import time
import os
import webbrowser
import threading
import subprocess
import sys
import mimetypes
import urllib.request
import urllib.parse
import json
import re
import math
import logging
import warnings
import secrets
import sys
import shutil
import unicodedata
from collections import Counter, deque
from pathlib import Path
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from googleapiclient.discovery import build

try:
    from deep_translator import GoogleTranslator
    from deep_translator import MyMemoryTranslator
except Exception:
    GoogleTranslator = None
    MyMemoryTranslator = None

try:
    import argostranslate.translate as argos_translate
except Exception:
    argos_translate = None

try:
    from transformers import MarianMTModel, MarianTokenizer
    from transformers.utils import logging as transformers_logging
except Exception:
    MarianMTModel = None
    MarianTokenizer = None
    transformers_logging = None

try:
    from ytmusicapi import YTMusic
except Exception:
    YTMusic = None

REDIRECT_URI = "http://127.0.0.1:5000/spotify/callback"
if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
    ROOT_DIR = Path(sys._MEIPASS)
    PROJECT_DIR = ROOT_DIR / "projeto"
    RUNTIME_DIR = Path(sys.executable).resolve().parent
else:
    PROJECT_DIR = Path(__file__).resolve().parent
    ROOT_DIR = PROJECT_DIR.parent
    RUNTIME_DIR = PROJECT_DIR
RUNTIME_DATA_DIR = RUNTIME_DIR / "data"
RUNTIME_LOG_DIR = RUNTIME_DIR / "logs"
CONFIG_FILE = str(RUNTIME_DATA_DIR / "config.json")
YT_CACHE_FILE = str(RUNTIME_DATA_DIR / "yt_cache.json")
PACKAGED_YT_CACHE_FILE = PROJECT_DIR / "yt_cache.json"
ARTIST_WIDGET_FILE = PROJECT_DIR / "artist_widget.html"
ARTIST_DATA_FILE = PROJECT_DIR / "dados_artista.js"
ARTIST_IMAGES_DIR = PROJECT_DIR / "img_artista"
VENV_PYTHON = ROOT_DIR / "venv311" / "Scripts" / "python.exe"
PROFILES_FILE = RUNTIME_DATA_DIR / "profiles.json"
SAVED_PROFILES_FILE = RUNTIME_DATA_DIR / "saved_profiles.json"
PROFILE_TTL_SECONDS = 45
PROFILE_JOINED_RECENTLY_SECONDS = 30

app = Flask(__name__, static_folder=str(PROJECT_DIR), static_url_path="")
VERBOSE_LOGS = False
VERBOSE_TRANSLATION_LOGS = False
VERBOSE_ARTIST_PIPELINE_LOGS = False


def get_runtime_log_path():
    try:
        if getattr(sys, "frozen", False):
            return RUNTIME_LOG_DIR / "host_runtime.log"
    except Exception:
        pass
    return RUNTIME_LOG_DIR / "host_runtime.log"


def runtime_log(message):
    try:
        log_path = get_runtime_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{message}\n")
    except Exception:
        pass


def cleanup_local_runtime_processes():
    current_pid = os.getpid()
    yp2_path = str((PROJECT_DIR / "yp2.py").resolve()).replace("'", "''")
    ps_script = rf"""
$ErrorActionPreference = 'SilentlyContinue'
$currentPid = {current_pid}
$yp2Path = '{yp2_path}'
Get-CimInstance Win32_Process | Where-Object {{
    $_.ProcessId -ne $currentPid -and (
        ((($_.Name -ieq 'python.exe') -or ($_.Name -ieq 'pythonw.exe')) -and ($_.CommandLine -like "*$yp2Path*")) -or
        ((($_.Name -ieq 'cloudflared.exe') -or ($_.Name -ieq 'cloudflared')) -and ($_.CommandLine -like '*localhost:5000*')) -or
        ($_.CommandLine -like '*cloudflared*tunnel*http://localhost:5000*')
    )
}} | ForEach-Object {{
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}}
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            check=False,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        runtime_log(f"[cleanup] pid={current_pid} stale local runtime cleanup attempted")
    except Exception as exc:
        runtime_log(f"[cleanup] pid={current_pid} cleanup failed: {exc!r}")


def debug_log(message, *, category="general", force=False):
    if force:
        print(message)
        return

    if category == "translation" and VERBOSE_TRANSLATION_LOGS:
        print(message)
    elif category == "artist" and VERBOSE_ARTIST_PIPELINE_LOGS:
        print(message)
    elif category == "general" and VERBOSE_LOGS:
        print(message)

NOISY_GET_ROUTES = {
    "/status",
    "/artist-context",
    "/profiles",
    "/queue-preview",
    "/artist-widget",
    "/dados_artista.js",
}

# ðŸ”¥ CORS OK
app.config['CORS_HEADERS'] = 'Content-Type'
CORS(app, resources={
    r"/*": {
        "origins": "*"
    }
})


@app.after_request
def log_clean_requests(response):
    try:
        global console_first_client_seen
        if not console_first_client_seen:
            console_first_client_seen = True
            stop_console_boot_spinner()
        if should_log_request():
            debug_log(f"[http] {request.method} {request.path} -> {response.status_code}")
    except Exception:
        pass
    return response

# --- PLAYER ---
sp = None
youtube = None
ytmusic = None
config_cache = {}
config_cache_mtime = None
profiles_cache = {}
profiles_cache_mtime = None
saved_profiles_cache = {}
saved_profiles_cache_mtime = None
tunnel_process = None
tunnel_public_url = ""
tunnel_status = "idle"
tunnel_last_log = ""
tunnel_lock = threading.Lock()

def load_config():
    global config_cache, config_cache_mtime
    if not os.path.exists(CONFIG_FILE):
        config_cache = {}
        config_cache_mtime = None
        return {}

    try:
        current_mtime = os.path.getmtime(CONFIG_FILE)
        if config_cache_mtime == current_mtime:
            return dict(config_cache)

        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config_cache = json.load(f)
        config_cache_mtime = current_mtime
        return dict(config_cache)
    except Exception:
        return {}


def save_config(data):
    global config_cache, config_cache_mtime
    safe_data = data if isinstance(data, dict) else {}
    Path(CONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(safe_data, f, ensure_ascii=False, separators=(",", ":"))
    config_cache = dict(safe_data)
    config_cache_mtime = os.path.getmtime(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else None


def ensure_runtime_config():
    config = load_config()
    changed = False

    if not config.get("HOST_ACCESS_TOKEN"):
        config["HOST_ACCESS_TOKEN"] = secrets.token_urlsafe(18)
        changed = True

    # Migration: guest controls should default to enabled unless the host
    # has explicitly chosen otherwise in the new preferences flow.
    if not config.get("GUEST_CONTROL_PREF_SET"):
        config["ALLOW_GUEST_CONTROLS"] = True
        config["GUEST_CONTROL_PREF_SET"] = True
        changed = True

    if "PUBLIC_BASE_URL" not in config:
        config["PUBLIC_BASE_URL"] = ""
        changed = True

    if changed:
        save_config(config)

    return config


def ensure_runtime_support_files():
    try:
        RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
        RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
        runtime_cache = Path(YT_CACHE_FILE)
        if runtime_cache.exists():
            return
        if PACKAGED_YT_CACHE_FILE.exists():
            runtime_cache.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PACKAGED_YT_CACHE_FILE, runtime_cache)
            runtime_log(f"[yp2.runtime] seeded yt cache at {runtime_cache}")
    except Exception as exc:
        runtime_log(f"[yp2.runtime] failed seeding yt cache: {exc!r}")


def load_profiles():
    global profiles_cache, profiles_cache_mtime
    if not PROFILES_FILE.exists():
        profiles_cache = {}
        profiles_cache_mtime = None
        return {}
    try:
        current_mtime = PROFILES_FILE.stat().st_mtime
        if profiles_cache_mtime == current_mtime:
            return dict(profiles_cache)
        with PROFILES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        profiles_cache = data if isinstance(data, dict) else {}
        profiles_cache_mtime = current_mtime
        return dict(profiles_cache)
    except Exception:
        return {}


def save_profiles(data):
    global profiles_cache, profiles_cache_mtime
    try:
        PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with PROFILES_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        profiles_cache = data if isinstance(data, dict) else {}
        profiles_cache_mtime = PROFILES_FILE.stat().st_mtime if PROFILES_FILE.exists() else None
    except Exception as e:
        print("Erro salvando perfis:", e)


def load_saved_profiles():
    global saved_profiles_cache, saved_profiles_cache_mtime
    if not SAVED_PROFILES_FILE.exists():
        saved_profiles_cache = {}
        saved_profiles_cache_mtime = None
        return {}
    try:
        current_mtime = SAVED_PROFILES_FILE.stat().st_mtime
        if saved_profiles_cache_mtime == current_mtime:
            return dict(saved_profiles_cache)
        with SAVED_PROFILES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        saved_profiles_cache = data if isinstance(data, dict) else {}
        saved_profiles_cache_mtime = current_mtime
        return dict(saved_profiles_cache)
    except Exception:
        return {}


def save_saved_profiles(data):
    global saved_profiles_cache, saved_profiles_cache_mtime
    try:
        SAVED_PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SAVED_PROFILES_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        saved_profiles_cache = data if isinstance(data, dict) else {}
        saved_profiles_cache_mtime = SAVED_PROFILES_FILE.stat().st_mtime if SAVED_PROFILES_FILE.exists() else None
    except Exception as e:
        print("Erro salvando perfis persistentes:", e)


def build_guest_token():
    return f"guest_{secrets.token_urlsafe(18)}"


def build_guest_recovery_code():
    raw = secrets.token_hex(4).upper()
    return f"{raw[:4]}-{raw[4:]}"


def find_saved_profile(saved_profiles_map, guest_token="", client_id=""):
    if guest_token:
        for profile in saved_profiles_map.values():
            if (profile.get("guest_token") or "").strip() == guest_token:
                return profile
    if client_id:
        return saved_profiles_map.get(client_id) or {}
    return {}


def should_log_request():
    path = request.path or ""
    if request.method == "GET":
        if path in NOISY_GET_ROUTES:
            return False
        if path.startswith("/img_artista/") or path.startswith("/artist-image/"):
            return False
    return True


def is_local_request():
    remote_addr = (request.headers.get("X-Forwarded-For", request.remote_addr) or "").split(",")[0].strip()
    return remote_addr in {"127.0.0.1", "::1", "localhost", ""}


def request_has_host_access():
    config = ensure_runtime_config()
    if is_local_request():
        return True

    provided_token = (
        (request.args.get("host") or "").strip()
        or (request.headers.get("X-Host-Token") or "").strip()
        or (request.headers.get("Authorization", "").removeprefix("Bearer ").strip())
    )
    expected_token = (config.get("HOST_ACCESS_TOKEN") or "").strip()
    return bool(provided_token and expected_token and secrets.compare_digest(provided_token, expected_token))


def request_can_control_playback():
    config = ensure_runtime_config()
    if request_has_host_access():
        return True
    return bool(config.get("ALLOW_GUEST_CONTROLS"))


def require_host_access():
    if request_has_host_access():
        return None
    return jsonify({"status": "ERROR", "message": "Acesso restrito ao host"}), 403


def set_public_base_url(url):
    config = ensure_runtime_config()
    config["PUBLIC_BASE_URL"] = (url or "").strip().rstrip("/")
    save_config(config)


def get_cloudflared_command():
    candidates = [
        "cloudflared",
        "cloudflared.exe",
        str(PROJECT_DIR / "cloudflared-windows-amd64.exe"),
        str(PROJECT_DIR / "cloudflared.exe"),
        str(ROOT_DIR / "cloudflared-windows-amd64.exe"),
        str(ROOT_DIR / "cloudflared.exe"),
    ]
    for candidate in candidates:
        try:
            process = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=True,
                timeout=4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            if process.returncode == 0:
                return candidate
        except Exception:
            continue
    return None


def monitor_tunnel_output(process):
    global tunnel_public_url, tunnel_status, tunnel_last_log, tunnel_process
    url_pattern = re.compile(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com")
    try:
        for raw_line in iter(process.stdout.readline, ""):
            line = (raw_line or "").strip()
            if not line:
                continue
            tunnel_last_log = line
            match = url_pattern.search(line)
            if match:
                tunnel_public_url = match.group(0).rstrip("/")
                tunnel_status = "active"
                set_public_base_url(tunnel_public_url)
        if tunnel_public_url:
            print(f"[tunnel] url publica: {tunnel_public_url}")
    except Exception as e:
        tunnel_last_log = str(e)
    finally:
        with tunnel_lock:
            if tunnel_process is process:
                process.poll()
                if process.returncode is not None and tunnel_status != "active":
                    tunnel_status = "error"
                elif process.returncode is not None:
                    tunnel_status = "idle"
                tunnel_process = None


def get_tunnel_payload():
    return {
        "tunnel_state": tunnel_status,
        "public_base_url": tunnel_public_url,
        "last_log": tunnel_last_log,
        "active": tunnel_status == "active",
        "starting": tunnel_status == "starting",
    }


def start_tunnel_process():
    global tunnel_process, tunnel_status, tunnel_public_url, tunnel_last_log
    with tunnel_lock:
        if tunnel_process and tunnel_process.poll() is None:
            return True, {"status": "OK", **get_tunnel_payload()}

        command = get_cloudflared_command()
        if not command:
            tunnel_status = "error"
            tunnel_last_log = "cloudflared nao encontrado"
            return False, {
                "status": "ERROR",
                "message": "cloudflared nao foi encontrado. Instale o Cloudflare Tunnel ou use a URL publica manual."
            }

        tunnel_public_url = ""
        tunnel_status = "starting"
        tunnel_last_log = "Iniciando cloudflared..."
        set_public_base_url("")

        try:
            tunnel_process = subprocess.Popen(
                [command, "tunnel", "--url", "http://localhost:5000", "--no-autoupdate"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            threading.Thread(target=monitor_tunnel_output, args=(tunnel_process,), daemon=True).start()
            return True, {"status": "OK", **get_tunnel_payload()}
        except Exception as e:
            tunnel_process = None
            tunnel_status = "error"
            tunnel_last_log = str(e)
            return False, {"status": "ERROR", "message": str(e)}


def stop_tunnel_process():
    global tunnel_process, tunnel_status, tunnel_public_url, tunnel_last_log
    with tunnel_lock:
        if tunnel_process and tunnel_process.poll() is None:
            try:
                tunnel_process.terminate()
                tunnel_process.wait(timeout=4)
            except Exception:
                try:
                    tunnel_process.kill()
                except Exception:
                    pass
        tunnel_process = None
        tunnel_status = "idle"
        tunnel_public_url = ""
        tunnel_last_log = "Tunnel encerrado"
        set_public_base_url("")


def shutdown_runtime():
    try:
        stop_tunnel_process()
    except Exception:
        pass


def prune_profiles(profiles_map):
    now = int(time.time())
    changed = False
    active = {}

    for client_id, profile in profiles_map.items():
        last_seen = int(profile.get("last_seen", profile.get("updated_at", 0)) or 0)
        if now - last_seen <= PROFILE_TTL_SECONDS:
            profile["last_seen"] = last_seen
            active[client_id] = profile
        else:
            changed = True

    if changed:
        save_profiles(active)

    return active

def init_services(open_browser=False):
    global sp, youtube, ytmusic
    runtime_log(f"[yp2.init_services] pid={os.getpid()} open_browser={bool(open_browser)}")
    config = ensure_runtime_config()
    client_id = config.get("CLIENT_ID", "")
    client_secret = config.get("CLIENT_SECRET", "")
    yt_key = config.get("YOUTUBE_API_KEY", "")

    if client_id and client_secret and client_id != "SEU_ID":
        try:
            has_token = has_cached_spotify_token(config)
            if not has_token:
                if open_browser:
                    open_spotify_authorization_browser(config)
                runtime_log(f"[yp2.spotify_oauth] pid={os.getpid()} token ausente; aguardando autorizacao no navegador")
                sp = None
            else:
                runtime_log(f"[yp2.spotify_oauth] pid={os.getpid()} creating SpotifyOAuth open_browser={bool(open_browser)}")
                sp = spotipy.Spotify(
                    auth_manager=create_spotify_oauth(config, open_browser=False),
                    requests_timeout=4,
                    retries=0,
                    status_retries=0,
                    backoff_factor=0.3
                )
        except Exception as e:
            print("Erro ao iniciar Spotify:", e)
    else:
        sp = None

    if yt_key and yt_key != "SUA_KEY":
        try:
            youtube = build("youtube", "v3", developerKey=yt_key)
        except Exception as e:
            print("Erro YouTube API:", e)
            youtube = None
    else:
        youtube = None

    if YTMusic is not None:
        try:
            ytmusic = YTMusic(language="en")
        except Exception as e:
            print("Erro YouTube Music:", e)
            ytmusic = None
    else:
        ytmusic = None


def has_cached_spotify_token(config=None):
    config = config or ensure_runtime_config()
    client_id = config.get("CLIENT_ID", "")
    client_secret = config.get("CLIENT_SECRET", "")
    if not client_id or not client_secret or client_id == "SEU_ID":
        return False
    try:
        auth = create_spotify_oauth(config)
        token_info = auth.cache_handler.get_cached_token() if getattr(auth, "cache_handler", None) else None
        return bool(token_info)
    except Exception:
        return False


def create_spotify_oauth(config=None, *, open_browser=False):
    config = config or ensure_runtime_config()
    return SpotifyOAuth(
        client_id=config.get("CLIENT_ID", ""),
        client_secret=config.get("CLIENT_SECRET", ""),
        redirect_uri=REDIRECT_URI,
        scope="user-read-playback-state user-modify-playback-state",
        open_browser=bool(open_browser)
    )


def open_spotify_authorization_browser(config=None):
    config = config or ensure_runtime_config()
    client_id = config.get("CLIENT_ID", "")
    client_secret = config.get("CLIENT_SECRET", "")
    if not client_id or not client_secret or client_id == "SEU_ID":
        return False
    try:
        auth = create_spotify_oauth(config, open_browser=False)
        auth_url = auth.get_authorize_url()
        if auth_url:
            runtime_log(f"[yp2.spotify_auth] pid={os.getpid()} opening auth url")
            webbrowser.open(auth_url)
            return True
    except Exception as exc:
        runtime_log(f"[yp2.spotify_auth] pid={os.getpid()} failed to open auth url: {exc!r}")
    return False


def get_spotify_authorization_url(config=None):
    config = config or ensure_runtime_config()
    client_id = config.get("CLIENT_ID", "")
    client_secret = config.get("CLIENT_SECRET", "")
    if not client_id or not client_secret or client_id == "SEU_ID":
        return ""
    try:
        auth = create_spotify_oauth(config, open_browser=False)
        return auth.get_authorize_url() or ""
    except Exception as exc:
        runtime_log(f"[yp2.spotify_auth] pid={os.getpid()} failed to build auth url: {exc!r}")
        return ""


def apply_cached_playback_progress(now_ts=None):
    now_ts = now_ts or time.time()
    if not current_data.get("track_id") or not current_data.get("duration_ms"):
        return
    if not current_data.get("is_playing"):
        return
    if not last_spotify_success_at:
        return

    elapsed_ms = max(0, int((now_ts - last_spotify_success_at) * 1000))
    if elapsed_ms <= 0:
        return

    duration_ms = max(0, int(current_data.get("duration_ms") or 0))
    progress_ms = max(0, int(current_data.get("progress_ms") or 0))
    next_progress = min(duration_ms, progress_ms + elapsed_ms)
    current_data["progress_ms"] = next_progress
    current_data["spotify_time"] = next_progress // 1000

current_data = {
    "title": "Aguardando...",
    "artist": "",
    "track_id": "",
    "cover": "",
    "videoId": "",
    "nextVideoId": "",
    "nextTrackId": "",
    "spotify_time": 0,
    "progress_ms": 0,
    "duration_ms": 0,
    "is_playing": False,
    "status": "READY"
}

last_track_id = None
last_request_time = 0
last_queue_request_time = 0
queue_preview_cache = []
video_resolution_track_id = ""
video_resolution_lock = threading.Lock()
video_resolution_queries = set()
spotify_backoff_until = 0
youtube_backoff_until = 0
negative_yt_cache = {}
track_change_cooldown_until = 0
pending_fast_polls = 0
fast_poll_interval_until = 0
current_video_retry_track_id = ""
current_video_retry_attempts = 0
last_spotify_success_at = 0
consecutive_pause_reports = 0
last_artist_enrichment = ""
pending_artist_enrichment = ""
spotify_request_window = deque()
spotify_request_window_lock = threading.Lock()
spotify_request_window_last_log_at = 0.0
SPOTIFY_WINDOW_SECONDS = 30.0
SPOTIFY_WINDOW_LOG_COOLDOWN = 30.0
spotify_window_bucket_started_at = math.floor(time.time() / SPOTIFY_WINDOW_SECONDS) * SPOTIFY_WINDOW_SECONDS
spotify_window_bucket_total = 0
spotify_window_bucket_endpoints = Counter()
spotify_window_bucket_outcomes = Counter()
spotify_call_state_lock = threading.Lock()
spotify_call_active = {}
spotify_window_last_completed_summary = {
    "window_seconds": int(SPOTIFY_WINDOW_SECONDS),
    "total_requests": 0,
    "endpoints": {},
    "outcomes": {},
    "limited": False,
    "retry_after_seconds": 0,
    "retry_after_human": "0s",
}
console_boot_spinner_active = False
console_boot_spinner_done = False
console_first_client_seen = False
artist_context = {
    "artist": "",
    "loading": False,
    "updated_at": 0,
        "data": {
            "curiosidades": [],
            "instagram": "",
            "website": "",
            "agenda": "",
            "status": "",
            "proximo_show": "",
            "ultimo_show": "",
            "image_urls": []
        }
}
artist_context_lock = threading.Lock()
enrichment_thread = None
lyrics_translation_cache = {}
argos_translation_cache = {}
marian_translation_cache = {}
artist_context_revision = 0


def buscar_lrclib_candidatas(artist, track):
    if not artist or not track:
        return []

    try:
        query = urllib.parse.quote(f"{artist} {track}")
        url = f"https://lrclib.net/api/search?q={query}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))

        if not isinstance(data, list):
            return []

        candidates = []
        for item in data[:8]:
            candidates.append({
                "id": item.get("id") or f"lrclib-{len(candidates)}",
                "source": "LRCLIB",
                "trackName": item.get("trackName", ""),
                "artistName": item.get("artistName", ""),
                "albumName": item.get("albumName", ""),
                "syncedLyrics": item.get("syncedLyrics", ""),
                "plainLyrics": item.get("plainLyrics", "")
            })
        return candidates
    except Exception as e:
        debug_log(f"lyrics lrclib erro: {e}", category="translation")
        return []


def _purge_spotify_request_window(now_ts=None):
    now_ts = now_ts or time.time()
    cutoff = now_ts - SPOTIFY_WINDOW_SECONDS
    while spotify_request_window and spotify_request_window[0]["ts"] < cutoff:
        spotify_request_window.popleft()


def _build_spotify_window_summary(total, endpoint_counts, outcome_counts, now_ts):
    retry_after_seconds = max(0.0, float(spotify_backoff_until or 0) - now_ts)
    return {
        "window_seconds": int(SPOTIFY_WINDOW_SECONDS),
        "total_requests": int(total),
        "endpoints": dict(endpoint_counts),
        "outcomes": dict(outcome_counts),
        "limited": retry_after_seconds > 0,
        "retry_after_seconds": int(math.ceil(retry_after_seconds)) if retry_after_seconds > 0 else 0,
        "retry_after_human": format_remaining_clock(retry_after_seconds),
    }


def _roll_spotify_window_bucket(now_ts):
    global spotify_window_bucket_started_at, spotify_window_bucket_total
    global spotify_window_bucket_endpoints, spotify_window_bucket_outcomes
    global spotify_window_last_completed_summary

    bucket_size = float(SPOTIFY_WINDOW_SECONDS)
    while now_ts >= (spotify_window_bucket_started_at + bucket_size):
        spotify_window_last_completed_summary = _build_spotify_window_summary(
            spotify_window_bucket_total,
            spotify_window_bucket_endpoints,
            spotify_window_bucket_outcomes,
            now_ts,
        )
        spotify_window_bucket_started_at += bucket_size
        spotify_window_bucket_total = 0
        spotify_window_bucket_endpoints = Counter()
        spotify_window_bucket_outcomes = Counter()


def register_spotify_request(endpoint):
    global spotify_window_bucket_total
    event = {
        "ts": time.time(),
        "endpoint": str(endpoint or "unknown"),
        "outcome": "pending"
    }
    with spotify_request_window_lock:
        _roll_spotify_window_bucket(event["ts"])
        spotify_request_window.append(event)
        _purge_spotify_request_window(event["ts"])
        spotify_window_bucket_total += 1
        spotify_window_bucket_endpoints[event["endpoint"]] += 1
    return event


def finalize_spotify_request(event, outcome):
    if event:
        event["outcome"] = str(outcome or "unknown")
        with spotify_request_window_lock:
            _roll_spotify_window_bucket(time.time())
            spotify_window_bucket_outcomes[event["outcome"]] += 1


def maybe_log_spotify_request_window(force=False, reason=""):
    global spotify_request_window_last_log_at
    now_ts = time.time()
    with spotify_request_window_lock:
        _roll_spotify_window_bucket(now_ts)
        if not force and (now_ts - spotify_request_window_last_log_at) < SPOTIFY_WINDOW_LOG_COOLDOWN:
            return
        spotify_request_window_last_log_at = now_ts
        summary_payload = dict(spotify_window_last_completed_summary)

    total = int(summary_payload.get("total_requests") or 0)
    endpoint_counts = Counter(summary_payload.get("endpoints") or {})
    outcome_counts = Counter(summary_payload.get("outcomes") or {})
    endpoint_order = [
        "/v1/me/player",
        "/v1/me/player/queue",
        "/v1/me/player/play",
        "/v1/me/player/pause",
        "/v1/me/player/next",
        "/v1/me/player/previous"
    ]
    endpoint_parts = []
    seen = set()
    for endpoint in endpoint_order:
        count = endpoint_counts.get(endpoint, 0)
        if count:
            endpoint_parts.append(f"{endpoint}={count}")
            seen.add(endpoint)
    for endpoint, count in endpoint_counts.items():
        if endpoint not in seen:
            endpoint_parts.append(f"{endpoint}={count}")

    outcome_parts = []
    for outcome in ("ok", "pending", "timeout", "error"):
        count = outcome_counts.get(outcome, 0)
        if count:
            outcome_parts.append(f"{outcome}={count}")

    summary = f"[spotify-window] nos ultimos {int(summary_payload.get('window_seconds') or SPOTIFY_WINDOW_SECONDS)}s foram {total} requests"
    if endpoint_parts:
        summary += f" | endpoints: {', '.join(endpoint_parts)}"
    if outcome_parts:
        summary += f" | resultados: {', '.join(outcome_parts)}"
    debug_log(summary, force=True)


def format_remaining_clock(seconds):
    try:
        total_seconds = max(0, int(math.ceil(float(seconds or 0))))
    except Exception:
        total_seconds = 0

    hours, remainder = divmod(total_seconds, 3600)
    minutes, _seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}min"
    if minutes > 0:
        return f"{minutes}min"
    return f"{total_seconds}s"


def get_spotify_window_payload():
    now_ts = time.time()
    with spotify_request_window_lock:
        _roll_spotify_window_bucket(now_ts)
        payload = dict(spotify_window_last_completed_summary)

    retry_after_seconds = max(0.0, float(spotify_backoff_until or 0) - now_ts)
    payload["limited"] = retry_after_seconds > 0
    payload["retry_after_seconds"] = int(math.ceil(retry_after_seconds)) if retry_after_seconds > 0 else 0
    payload["retry_after_human"] = format_remaining_clock(retry_after_seconds)
    return payload


def start_console_boot_spinner():
    global console_boot_spinner_active, console_boot_spinner_done
    if console_boot_spinner_active:
        return

    console_boot_spinner_active = True
    console_boot_spinner_done = False

    def runner():
        global console_boot_spinner_active, console_boot_spinner_done
        frames = ["|", "/", "-", "\\"]
        frame_idx = 0
        started_at = time.time()
        while console_boot_spinner_active and not console_boot_spinner_done:
            elapsed = int(max(0, time.time() - started_at))
            msg = f"\r[loading] {frames[frame_idx % len(frames)]} preparando a jam local... navegador e primeira carga podem levar alguns segundos ({elapsed}s)"
            try:
                print(msg, end="", flush=True)
            except Exception:
                break
            frame_idx += 1
            time.sleep(0.7)
        try:
            if console_boot_spinner_done:
                print("\r[loading] pronto. A jam local ja pode responder no navegador.                               ")
            else:
                print("\r[loading] carregamento inicial finalizado.                                                ")
        except Exception:
            pass

    threading.Thread(target=runner, daemon=True).start()


def stop_console_boot_spinner():
    global console_boot_spinner_active, console_boot_spinner_done
    console_boot_spinner_done = True
    console_boot_spinner_active = False


def buscar_lyrics_ovh(artist, track):
    if not artist or not track:
        return None

    try:
        artist_encoded = urllib.parse.quote(artist.strip())
        track_encoded = urllib.parse.quote(track.strip())
        url = f"https://api.lyrics.ovh/v1/{artist_encoded}/{track_encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))

        lyrics = (data.get("lyrics") or "").strip()
        if not lyrics:
            return None

        return {
            "id": f"lyrics-ovh-{artist.strip()}-{track.strip()}",
            "source": "lyrics.ovh",
            "trackName": track,
            "artistName": artist,
            "albumName": "",
            "plainLyrics": lyrics
        }
    except Exception as e:
        debug_log(f"lyrics.ovh erro: {e}", category="translation")
        return None


def normalize_pt_br_lyric_line(text):
    line = str(text or "").strip()
    if not line:
        return ""

    replacements = [
        (r"\bautocarro\b", "ônibus"),
        (r"\bcomboio\b", "trem"),
        (r"\btelemóvel\b", "celular"),
        (r"\btelemoveis\b", "celulares"),
        (r"\btelemóveis\b", "celulares"),
        (r"\becrã\b", "tela"),
        (r"\becras\b", "telas"),
        (r"\becrãs\b", "telas"),
        (r"\bfixe\b", "legal"),
        (r"\bmiúdo\b", "garoto"),
        (r"\bmiúda\b", "garota"),
        (r"\brapariga\b", "garota"),
        (r"\brapaz\b", "garoto"),
        (r"\bsumo\b", "suco"),
        (r"\bpequeno-almoço\b", "café da manhã"),
        (r"\bestás\b", "está"),
        (r"\bestais\b", "estão"),
        (r"\bestive a\b", "estive"),
        (r"\btu és\b", "você é"),
        (r"\btu est[áa]s\b", "você está"),
        (r"\btu tens\b", "você tem"),
        (r"\btu vais\b", "você vai"),
        (r"\btu queres\b", "você quer"),
        (r"\btu podes\b", "você pode"),
        (r"\btu sabes\b", "você sabe"),
        (r"\btu foste\b", "você foi"),
        (r"\btu dizes\b", "você diz"),
        (r"\bteu\b", "seu"),
        (r"\bteus\b", "seus"),
        (r"\btua\b", "sua"),
        (r"\btuas\b", "suas"),
        (r"\bcontigo\b", "com você"),
        (r"\bconvosco\b", "com vocês"),
        (r"\bvosso\b", "de vocês"),
        (r"\bvossa\b", "de vocês"),
        (r"\bnum\b", "em um"),
        (r"\bnuma\b", "em uma"),
        (r"\bnuns\b", "em uns"),
        (r"\bnumas\b", "em umas"),
        (r"\bnalgum\b", "em algum"),
        (r"\bnalguma\b", "em alguma"),
        (r"\bnalguns\b", "em alguns"),
        (r"\bnalgumas\b", "em algumas"),
        (r"\bbibendo\b", "bebendo"),
        (r"\bbibida\b", "bebida"),
        (r"\bbibidas\b", "bebidas"),
        (r"\bbiver\b", "beber"),
        (r"\bbive\b", "bebe"),
        (r"\bbivendo\b", "bebendo"),
        (r"\bvoce\b", "você"),
        (r"\bnao\b", "não"),
        (r"\bcoracao\b", "coração"),
        (r"\bsolidao\b", "solidão"),
        (r"\bpaixao\b", "paixão"),
        (r"\bmao\b", "mão"),
    ]

    normalized = line
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    normalized = re.sub(r"\s{2,}", " ", normalized).strip()
    return normalized


def build_translation_cache_key(lines, target):
    normalized_lines = [str(line or "").strip() for line in lines]
    return normalized_lines, f"{target}::" + "||".join(normalized_lines)


def build_translation_blocks(lines, max_lines=3, max_chars=180):
    blocks = []
    current_lines = []
    current_indexes = []
    current_chars = 0

    for index, line in enumerate(lines):
        line = str(line or "").strip()
        if not line:
            continue

        projected_chars = current_chars + len(line) + (1 if current_lines else 0)
        should_flush = (
            current_lines
            and (
                len(current_lines) >= max_lines
                or projected_chars > max_chars
                or bool(re.search(r"[.!?;:]\s*$", current_lines[-1]))
            )
        )

        if should_flush:
            blocks.append({
                "indexes": list(current_indexes),
                "text": "\n".join(current_lines),
            })
            current_lines = []
            current_indexes = []
            current_chars = 0

        current_lines.append(line)
        current_indexes.append(index)
        current_chars += len(line) + (1 if current_chars else 0)

    if current_lines:
        blocks.append({
            "indexes": list(current_indexes),
            "text": "\n".join(current_lines),
        })

    return blocks


def merge_translated_blocks(original_lines, blocks, translated_blocks):
    merged = [str(line or "") for line in original_lines]

    for block, translated_block in zip(blocks, translated_blocks):
        indexes = block.get("indexes") or []
        if not indexes:
            continue

        parts = [part.strip() for part in str(translated_block or "").splitlines()]
        parts = [part for part in parts if part]

        if len(parts) == len(indexes):
            for idx, translated_line in zip(indexes, parts):
                merged[idx] = translated_line or merged[idx]
            continue

        if len(indexes) == 1 and translated_block:
            merged[indexes[0]] = str(translated_block).strip() or merged[indexes[0]]
            continue

        # If the provider returned a whole paragraph instead of the same line count,
        # keep the original lines here and let callers fall back to per-line translation.
        for idx in indexes:
            merged[idx] = original_lines[idx]

    return merged


def line_looks_untranslated(translated_line, original_line):
    translated = re.sub(r"[^a-z0-9]+", "", str(translated_line or "").lower())
    original = re.sub(r"[^a-z0-9]+", "", str(original_line or "").lower())
    if not translated or not original:
        return False
    if translated == original:
        return True
    if len(original) >= 6 and (translated in original or original in translated):
        return True
    return False


def repair_translated_lines_individually(translated, original_lines, translator_target, provider_used):
    repaired = list(translated or [])

    for index, (line, original) in enumerate(zip(repaired, original_lines)):
        if not line_looks_untranslated(line, original):
            continue

        single_result = []
        try:
            if provider_used == "marian":
                single_result = translate_lines_with_marian([original], translator_target)
            elif provider_used == "argos":
                translator = get_argos_translator(translator_target)
                if translator is not None:
                    single_result = [translator.translate(original) if original else ""]
            elif provider_used.startswith("google") and GoogleTranslator is not None:
                translator = GoogleTranslator(source='auto', target=translator_target)
                single_result = [translator.translate(original) if original else ""]
            elif provider_used == "mymemory" and MyMemoryTranslator is not None:
                translator = MyMemoryTranslator(source='auto', target="pt-BR" if str(translator_target).startswith("pt") else translator_target)
                single_result = [translator.translate(original) if original else ""]
        except Exception:
            single_result = []

        replacement = (single_result[0] if single_result else "") or line
        repaired[index] = replacement

    return repaired


def get_argos_translator(translator_target):
    if argos_translate is None:
        return None

    argos_cache_key = f"auto::{translator_target}"
    translator = argos_translation_cache.get(argos_cache_key)
    if translator is not None:
        return translator

    try:
        installed_languages = argos_translate.get_installed_languages()
        from_lang = next((lang for lang in installed_languages if lang.code == "en"), None)
        to_lang = next((lang for lang in installed_languages if lang.code == translator_target), None)
        if from_lang and to_lang:
            translator = from_lang.get_translation(to_lang)
            argos_translation_cache[argos_cache_key] = translator
            debug_log(f"[lyrics-translate] argos pronto: en -> {translator_target}", category="translation")
            return translator
    except Exception:
        return None

    return None


def get_marian_bundle(translator_target):
    if MarianMTModel is None or MarianTokenizer is None:
        return None, None, ""

    lang_prefix = ""
    model_name = ""

    if str(translator_target).lower().startswith("pt"):
        model_name = "Helsinki-NLP/opus-mt-en-ROMANCE"
        lang_prefix = ">>pt_BR<< "
    else:
        return None, None, ""

    cache_key = f"{model_name}::{translator_target}"
    cached = marian_translation_cache.get(cache_key)
    if cached is not None:
        return cached.get("tokenizer"), cached.get("model"), cached.get("prefix", "")

    try:
        tokenizer = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)
        marian_translation_cache[cache_key] = {
            "tokenizer": tokenizer,
            "model": model,
            "prefix": lang_prefix,
        }
        debug_log(f"[lyrics-translate] marian pronto: {model_name}", category="translation")
        return tokenizer, model, lang_prefix
    except Exception as exc:
        debug_log(f"[lyrics-translate] marian indisponivel: {exc}", category="translation")
        return None, None, ""


def translate_lines_with_marian(lines, translator_target):
    tokenizer, model, prefix = get_marian_bundle(translator_target)
    if tokenizer is None or model is None:
        return []

    blocks = build_translation_blocks(lines)
    if not blocks:
        return []

    translated = []
    batch = [f"{prefix}{block['text']}" if block.get("text") else "" for block in blocks]
    non_empty = [line for line in batch if line.strip()]
    if not non_empty:
        return [""] * len(lines)

    try:
        encoded = tokenizer(
            non_empty,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256,
        )
        generated = model.generate(
            **encoded,
            max_length=256,
            num_beams=4,
            early_stopping=True,
        )
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        translated = merge_translated_blocks(lines, blocks, decoded)
    except Exception as exc:
        debug_log(f"[lyrics-translate] marian erro: {exc}", category="translation")
        return []

    return translated


def has_useful_translation(translated, original_lines):
    if not translated:
        return False

    changed_count = 0
    suspicious_count = 0

    for line, original in zip(translated, original_lines):
        if line and line != original:
            changed_count += 1
        if line_looks_untranslated(line, original):
            suspicious_count += 1

    if changed_count == 0:
        return False

    return suspicious_count < max(1, len(original_lines) // 2)


def translate_lyrics_lines(lines, target="pt-BR", prefer_local=False, log_prefix="[lyrics-translate]"):
    if GoogleTranslator is None:
        debug_log(f"{log_prefix} indisponivel: GoogleTranslator ausente", category="translation")
        return [], ""

    if not isinstance(lines, list) or not lines:
        return [], ""

    translator_target = "pt" if str(target).lower().startswith("pt") else str(target)
    normalized_lines, cache_key = build_translation_cache_key(lines, target)
    translation_blocks = build_translation_blocks(normalized_lines)
    block_texts = [block["text"] for block in translation_blocks]

    if cache_key in lyrics_translation_cache:
        debug_log(f"{log_prefix} cache hit: {len(normalized_lines)} linhas -> {target}", category="translation")
        return list(lyrics_translation_cache[cache_key]), "cache"

    translated = []
    provider_used = ""

    try:
        translator = GoogleTranslator(source='auto', target=translator_target)
        batch_result = translator.translate_batch(block_texts) if block_texts else []
        translated = merge_translated_blocks(normalized_lines, translation_blocks, batch_result or [])
        provider_used = "google-batch"
    except Exception as exc:
        debug_log(f"{log_prefix} google-batch falhou: {exc}", category="translation")
        translated = []

    if not has_useful_translation(translated, normalized_lines):
        try:
            translator = GoogleTranslator(source='auto', target=translator_target)
            translated_blocks = []
            for block_text in block_texts:
                if not block_text:
                    translated_blocks.append("")
                    continue
                try:
                    translated_blocks.append(translator.translate(block_text) or block_text)
                except Exception:
                    translated_blocks.append(block_text)
            translated = merge_translated_blocks(normalized_lines, translation_blocks, translated_blocks)
            provider_used = "google-line"
        except Exception as exc:
            debug_log(f"{log_prefix} google-line falhou: {exc}", category="translation")
            translated = []

    if str(target).lower().startswith("pt"):
        translated = [normalize_pt_br_lyric_line(line) for line in translated]

    if has_useful_translation(translated, normalized_lines):
        debug_log(f"{log_prefix} ok via {provider_used or 'unknown'}: {len(normalized_lines)} linhas -> {target}", category="translation")
    else:
        debug_log(f"{log_prefix} sem traducao util: {len(normalized_lines)} linhas -> {target}", category="translation")

    lyrics_translation_cache[cache_key] = list(translated)
    return translated, provider_used


def preload_candidate_translation(candidate, target="pt-BR"):
    synced_lyrics = (candidate or {}).get("syncedLyrics", "")
    if not synced_lyrics:
        return None

    lines = []
    for raw_line in str(synced_lyrics).splitlines():
        cleaned = re.sub(r"\[\d{2}:\d{2}\.\d{2,3}\]", "", raw_line).strip()
        if cleaned:
            lines.append(cleaned)

    if not lines:
        return None

    translated, _provider = translate_lyrics_lines(
        lines,
        target=target,
        prefer_local=True,
        log_prefix="[lyrics-preload]"
    )
    if not has_useful_translation(translated, lines):
        return None
    return translated


# ðŸ”¥ FALLBACK (Invidious)
def score_youtube_candidate(title="", channel_title=""):
    haystack = f"{title or ''} {channel_title or ''}".lower()
    score = 0

    if "official audio" in haystack:
        score += 120
    if "audio" in haystack:
        score += 45
    if "official video" in haystack:
        score += 95
    if "official music video" in haystack:
        score += 105
    if "music video" in haystack or "mv" in haystack:
        score += 38
    if "topic" in haystack:
        score += 26
    if "lyric video" in haystack or "lyrics" in haystack:
        score += 10

    if "snippet" in haystack:
        score -= 180
    if "preview" in haystack:
        score -= 180
    if "teaser" in haystack:
        score -= 170
    if "short version" in haystack:
        score -= 150
    if "radio edit" in haystack:
        score -= 45

    if "live" in haystack:
        score -= 35
    if "cover" in haystack:
        score -= 55
    if "karaoke" in haystack:
        score -= 60
    if "slowed" in haystack or "sped up" in haystack or "nightcore" in haystack:
        score -= 45
    if "remix" in haystack:
        score -= 30

    return score


def is_rejected_short_variant(title="", duration_seconds=None, target_duration_seconds=None):
    haystack = normalize_search_text(title)
    if any(flag in haystack for flag in ("snippet", "preview", "teaser", "short version")):
        return True

    if duration_seconds and target_duration_seconds:
        try:
            duration_seconds = float(duration_seconds)
            target_duration_seconds = float(target_duration_seconds)
            if target_duration_seconds >= 90 and duration_seconds <= max(75, target_duration_seconds * 0.55):
                return True
        except Exception:
            return False

    return False


def normalize_search_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalized_search_tokens(value, min_len=3):
    return [token for token in normalize_search_text(value).split() if len(token) >= min_len]


def count_token_hits(tokens, haystack):
    return sum(1 for token in tokens if token in haystack)


def is_viable_track_candidate(title="", channel_title="", artist_name="", track_name="", duration_seconds=None, target_duration_seconds=None):
    haystack = normalize_search_text(f"{title} {channel_title}")
    artist_tokens = normalized_search_tokens(artist_name)
    track_tokens = normalized_search_tokens(track_name)

    if artist_tokens:
        artist_hits = count_token_hits(artist_tokens, haystack)
        min_artist_hits = 1 if len(artist_tokens) <= 2 else max(1, len(artist_tokens) // 2)
        if artist_hits < min_artist_hits:
            return False

    if track_tokens:
        track_hits = count_token_hits(track_tokens, haystack)
        min_track_hits = 1 if len(track_tokens) <= 2 else max(1, math.ceil(len(track_tokens) * 0.5))
        if track_hits < min_track_hits:
            return False

    if duration_seconds and target_duration_seconds:
        try:
            if abs(float(duration_seconds) - float(target_duration_seconds)) > 40:
                return False
        except Exception:
            pass

    return True


def score_query_match(title="", channel_title="", artist_name="", track_name=""):
    haystack = normalize_search_text(f"{title} {channel_title}")
    artist_norm = normalize_search_text(artist_name)
    track_norm = normalize_search_text(track_name)
    artist_tokens = normalized_search_tokens(artist_name)
    track_tokens = normalized_search_tokens(track_name)
    score = 0

    if artist_norm and artist_norm in haystack:
        score += 55
    elif artist_tokens:
        artist_hits = count_token_hits(artist_tokens, haystack)
        if artist_hits == len(artist_tokens):
            score += 42
        elif artist_hits >= max(1, len(artist_tokens) // 2):
            score += artist_hits * 12
        else:
            score -= 85

    if track_norm:
        if track_norm in haystack:
            score += 95
        else:
            token_hits = count_token_hits(track_tokens, haystack)
            if token_hits:
                score += token_hits * 12
            if track_tokens and token_hits < max(1, math.ceil(len(track_tokens) * 0.6)):
                score -= 65

    return score


def is_strong_track_match(title="", artist_name="", track_name="", duration_seconds=None, target_duration_seconds=None):
    title_norm = normalize_search_text(title)
    artist_norm = normalize_search_text(artist_name)
    track_norm = normalize_search_text(track_name)
    if not title_norm or not artist_norm or not track_norm:
        return False

    if artist_norm not in title_norm:
        return False

    track_tokens = [token for token in track_norm.split() if len(token) >= 3]
    if not track_tokens:
        return False

    token_hits = sum(1 for token in track_tokens if token in title_norm)
    if token_hits < len(track_tokens):
        return False

    if duration_seconds and target_duration_seconds:
        if abs(float(duration_seconds) - float(target_duration_seconds)) > 4:
            return False

    return True


def is_exact_song_result(title="", channel_title="", artist_name="", track_name="", duration_seconds=None, target_duration_seconds=None):
    title_norm = normalize_search_text(title)
    track_norm = normalize_search_text(track_name)
    haystack = normalize_search_text(f"{title} {channel_title}")
    artist_tokens = normalized_search_tokens(artist_name)

    if not title_norm or not track_norm or title_norm != track_norm:
        return False

    if artist_tokens and count_token_hits(artist_tokens, haystack) < max(1, len(artist_tokens) // 2):
        return False

    if duration_seconds and target_duration_seconds:
        try:
            if abs(float(duration_seconds) - float(target_duration_seconds)) > 12:
                return False
        except Exception:
            return False

    return True


def is_good_song_result(title="", channel_title="", artist_name="", track_name="", duration_seconds=None, target_duration_seconds=None):
    haystack = normalize_search_text(f"{title} {channel_title}")
    artist_tokens = normalized_search_tokens(artist_name)
    track_tokens = normalized_search_tokens(track_name)

    if artist_tokens and count_token_hits(artist_tokens, haystack) < max(1, len(artist_tokens) // 2):
        return False

    if track_tokens and count_token_hits(track_tokens, haystack) < 1:
        return False

    if duration_seconds and target_duration_seconds:
        try:
            if abs(float(duration_seconds) - float(target_duration_seconds)) > 18:
                return False
        except Exception:
            return False

    return True


def parse_youtube_duration_seconds(raw_duration):
    if not raw_duration:
        return 0
    match = re.match(
        r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$",
        str(raw_duration).strip(),
        re.IGNORECASE,
    )
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return (hours * 3600) + (minutes * 60) + seconds


def parse_duration_text_seconds(raw_value):
    text = str(raw_value or "").strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)

    parts = [int(part or 0) for part in text.split(":") if part.strip().isdigit()]
    if len(parts) == 2:
        return (parts[0] * 60) + parts[1]
    if len(parts) == 3:
        return (parts[0] * 3600) + (parts[1] * 60) + parts[2]
    return 0


def score_duration_match(duration_seconds, target_duration_seconds):
    if not duration_seconds or not target_duration_seconds:
        return 0

    diff = abs(float(duration_seconds) - float(target_duration_seconds))
    if diff <= 1.5:
        return 42
    if diff <= 3:
        return 30
    if diff <= 6:
        return 18
    if diff <= 10:
        return 8
    if diff <= 15:
        return 2
    return -18


def build_yt_cache_key(query, target_duration_seconds=None):
    cache_version = "v10"
    if not target_duration_seconds:
        return f"{cache_version}::{query}"
    bucket = int(round(float(target_duration_seconds) / 5.0) * 5)
    return f"{cache_version}::{query}::__dur__:{bucket}"


def normalize_query_for_ytmusic(value):
    text = normalize_search_text(value)
    return re.sub(r"\s+", " ", text).strip()


def build_ytmusic_queries(query, artist_name="", track_name=""):
    variants = []

    def add_variant(value):
        cleaned = str(value or "").strip()
        normalized = normalize_query_for_ytmusic(cleaned)
        for candidate in (cleaned, normalized):
            candidate = str(candidate or "").strip()
            if candidate and candidate not in variants:
                variants.append(candidate)

    add_variant(query)
    if artist_name or track_name:
        add_variant(f"{artist_name} {track_name}")
        add_variant(f"{track_name} {artist_name}")

    return variants


def get_legacy_cached_video(cache, artist_name="", track_name=""):
    candidates = []
    if artist_name and track_name:
        candidates.extend([
            f"{artist_name} {track_name} official audio",
            f"{normalize_query_for_ytmusic(artist_name)} {normalize_query_for_ytmusic(track_name)} official audio",
        ])

    for key in candidates:
        value = cache.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def get_historical_cached_video(cache, artist_name="", track_name="", target_duration_seconds=None):
    artist_norm = normalize_search_text(artist_name)
    track_norm = normalize_search_text(track_name)
    if not artist_norm or not track_norm:
        return ""

    candidates = []
    for key, value in (cache or {}).items():
        if not isinstance(value, dict):
            continue
        entry_artist = normalize_search_text(value.get("artist_name", ""))
        entry_track = normalize_search_text(value.get("track_name", ""))
        video_id = (value.get("videoId") or "").strip()
        if not video_id or entry_artist != artist_norm or entry_track != track_norm:
            continue

        entry_target = value.get("target_duration_seconds") or 0
        duration_score = score_duration_match(entry_target, target_duration_seconds)
        version_bonus = 0
        if str(key).startswith("v7::"):
            version_bonus = 35
        elif str(key).startswith("v6::"):
            version_bonus = 24
        elif str(key).startswith("v5::"):
            version_bonus = 14
        elif str(key).startswith("v4::"):
            version_bonus = 8

        candidates.append((duration_score + version_bonus, video_id))

    if not candidates:
        return ""

    return max(candidates, key=lambda item: item[0])[1]


def read_cached_video_entry(cache, cache_key):
    entry = cache.get(cache_key)
    if isinstance(entry, str):
        return {"videoId": entry}
    if isinstance(entry, dict):
        title = entry.get("title", "") or entry.get("track_name", "")
        duration_seconds = entry.get("duration_seconds") or entry.get("target_duration_seconds")
        target_seconds = entry.get("target_duration_seconds")
        if is_rejected_short_variant(title, duration_seconds, target_seconds):
            return {}
        return entry
    return {}


def get_ytmusic_video(query, target_duration_seconds=None, artist_name="", track_name=""):
    if ytmusic is None:
        return ""

    try:
        overall_candidates = []
        for current_query in build_ytmusic_queries(query, artist_name, track_name):
            for search_filter in ("songs", "videos"):
                try:
                    items = ytmusic.search(current_query, filter=search_filter, limit=6) or []
                except Exception:
                    continue

                fallback_candidates = []
                for item in items:
                    video_id = item.get("videoId") or item.get("videoId", "")
                    if not video_id:
                        continue

                    title = item.get("title", "")
                    artists = item.get("artists") or []
                    channel_title = " ".join(
                        artist.get("name", "") if isinstance(artist, dict) else str(artist)
                        for artist in artists
                    )
                    duration_seconds = (
                        item.get("duration_seconds")
                        or parse_duration_text_seconds(item.get("duration"))
                        or parse_duration_text_seconds(item.get("length"))
                    )

                    if is_rejected_short_variant(title, duration_seconds, target_duration_seconds):
                        continue

                    if search_filter == "songs" and is_good_song_result(
                        title,
                        channel_title,
                        artist_name,
                        track_name,
                        duration_seconds,
                        target_duration_seconds
                    ):
                        print("[yt] ytmusic good song")
                        return video_id

                    if not is_viable_track_candidate(
                        title,
                        channel_title,
                        artist_name,
                        track_name,
                        duration_seconds,
                        target_duration_seconds
                    ):
                        continue

                    if search_filter == "songs" and is_exact_song_result(
                        title,
                        channel_title,
                        artist_name,
                        track_name,
                        duration_seconds,
                        target_duration_seconds
                    ):
                        print("[yt] ytmusic exact song")
                        return video_id

                    match_score = score_query_match(title, channel_title, artist_name, track_name)
                    strong_match = is_strong_track_match(
                        title,
                        artist_name,
                        track_name,
                        duration_seconds,
                        target_duration_seconds
                    )

                    if strong_match:
                        print("[yt] ytmusic ok")
                        return video_id

                    if match_score >= 70:
                        print("[yt] ytmusic ok")
                        return video_id

                    text_score = score_youtube_candidate(title, channel_title)
                    duration_score = score_duration_match(duration_seconds, target_duration_seconds)
                    candidate = {
                        "videoId": video_id,
                        "score": text_score + match_score + duration_score + (55 if search_filter == "songs" else 0),
                    }
                    fallback_candidates.append(candidate)
                    overall_candidates.append(candidate)

                if fallback_candidates:
                    best_local = max(fallback_candidates, key=lambda item: item["score"])
                    if best_local["score"] >= 25:
                        print("[yt] ytmusic fallback")
                        return best_local["videoId"]

        if overall_candidates:
            best_overall = max(overall_candidates, key=lambda item: item["score"])
            if best_overall["score"] >= 5:
                print("[yt] ytmusic soft fallback")
                return best_overall["videoId"]

        return ""
    except Exception as e:
        debug_log(f"Erro YouTube Music: {e}")
        return ""


def get_yt_invidious(query):
    instancias = [
        "https://inv.tux.rs",
        "https://invidious.no-logs.com",
        "https://yewtu.be"
    ]

    search_query = urllib.parse.quote(query)

    for base_url in instancias:
        try:
            url = f"{base_url}/api/v1/search?q={search_query}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode())

                best_video_id = ""
                best_score = -10**9

                for item in data:
                    if item.get("type") != "video":
                        continue
                    score = score_youtube_candidate(
                        item.get("title", ""),
                        item.get("author", "")
                    )
                    if score > best_score:
                        best_score = score
                        best_video_id = item.get("videoId", "")

                if best_video_id:
                    return best_video_id

        except:
            continue

    return ""

def scrape_youtube(query):
    try:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode()
            match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            if match:
                return match.group(1)
    except:
        pass
    return ""

# ðŸ”¥ BUSCA PRINCIPAL (YouTube API + fallback)
def get_yt_video(query, target_duration_seconds=None, artist_name="", track_name=""):
    ytmusic_video_id = get_ytmusic_video(
        query,
        target_duration_seconds=target_duration_seconds,
        artist_name=artist_name,
        track_name=track_name
    )
    if ytmusic_video_id:
        return ytmusic_video_id
    return ""


def get_yt_video_cached(query, target_duration_seconds=None, artist_name="", track_name=""):
    now = time.time()
    negative_until = negative_yt_cache.get(query, 0)
    if negative_until and now < negative_until:
        debug_log(f"[video-cache] negativo ativo: {query}")
        return ""

    cache_key = build_yt_cache_key(query, target_duration_seconds)

    # Tenta ler do cache local
    cache = {}
    if os.path.exists(YT_CACHE_FILE):
        try:
            with open(YT_CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except:
            pass

    cached_entry = read_cached_video_entry(cache, cache_key)
    if cached_entry.get("videoId"):
        debug_log(f"âš¡ [CACHE USADO] {query}")
        return cached_entry["videoId"]

    # Se nÃ£o tiver, pesquisa de verdade
    v_id = get_yt_video(
        query,
        target_duration_seconds=target_duration_seconds,
        artist_name=artist_name,
        track_name=track_name
    )

    if not v_id:
        historical_video_id = get_historical_cached_video(
            cache,
            artist_name=artist_name,
            track_name=track_name,
            target_duration_seconds=target_duration_seconds
        )
        if historical_video_id:
            debug_log(f"⚡ [CACHE HISTORICO] {query}")
            v_id = historical_video_id
    
    if v_id:
        cache[cache_key] = {
            "videoId": v_id,
            "created_at": int(now),
            "target_duration_seconds": round(float(target_duration_seconds or 0), 2),
            "artist_name": artist_name,
            "track_name": track_name,
        }
        try:
            with open(YT_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except:
            pass
    else:
        negative_yt_cache[query] = now + 900
             
    return v_id


def persist_video_cache_entry(query, video_id, target_duration_seconds=None, artist_name="", track_name=""):
    if not query or not video_id:
        return
    cache_key = build_yt_cache_key(query, target_duration_seconds)
    cache = {}
    if os.path.exists(YT_CACHE_FILE):
        try:
            with open(YT_CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    cache[cache_key] = {
        "videoId": video_id,
        "created_at": int(time.time()),
        "target_duration_seconds": round(float(target_duration_seconds or 0), 2),
        "artist_name": artist_name,
        "track_name": track_name,
    }
    try:
        with open(YT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def try_resolve_current_video_immediately(query, target_duration_seconds=None, artist_name="", track_name=""):
    try:
        cache = {}
        if os.path.exists(YT_CACHE_FILE):
            try:
                with open(YT_CACHE_FILE, "r", encoding="utf-8") as f:
                    cache = json.load(f)
            except Exception:
                cache = {}

        historical_video_id = get_historical_cached_video(
            cache,
            artist_name=artist_name,
            track_name=track_name,
            target_duration_seconds=target_duration_seconds
        )
        if historical_video_id:
            persist_video_cache_entry(
                query,
                historical_video_id,
                target_duration_seconds=target_duration_seconds,
                artist_name=artist_name,
                track_name=track_name
            )
            return historical_video_id

        legacy_video_id = get_legacy_cached_video(
            cache,
            artist_name=artist_name,
            track_name=track_name
        )
        if legacy_video_id:
            persist_video_cache_entry(
                query,
                legacy_video_id,
                target_duration_seconds=target_duration_seconds,
                artist_name=artist_name,
                track_name=track_name
            )
            return legacy_video_id

        video_id = get_ytmusic_video(
            query,
            target_duration_seconds=target_duration_seconds,
            artist_name=artist_name,
            track_name=track_name
        )
        if video_id:
            persist_video_cache_entry(
                query,
                video_id,
                target_duration_seconds=target_duration_seconds,
                artist_name=artist_name,
                track_name=track_name
            )
        return video_id or ""
    except Exception:
        return ""


def get_cached_yt_video_only(query, target_duration_seconds=None):
    cache_key = build_yt_cache_key(query, target_duration_seconds)
    now = time.time()
    negative_until = negative_yt_cache.get(query, 0)
    if negative_until and now < negative_until:
        return ""

    if not os.path.exists(YT_CACHE_FILE):
        return ""

    try:
        with open(YT_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return read_cached_video_entry(cache, cache_key).get("videoId", "") or ""
    except Exception:
        return ""


def resolver_videos_em_segundo_plano(track_id, artist, track_name, current_duration_ms=0, next_track_data=None):
    global video_resolution_track_id, video_resolution_queries

    query = f"{artist} {track_name}"
    with video_resolution_lock:
        if query in video_resolution_queries:
            debug_log(f"[video-bg] ignorado duplicado: {query}")
            return
        video_resolution_queries.add(query)

    try:
        debug_log(f"[video-bg] resolvendo atual: {query}")
        v_id = get_yt_video_cached(
            query,
            target_duration_seconds=(current_duration_ms or 0) / 1000,
            artist_name=artist,
            track_name=track_name
        )

        with video_resolution_lock:
            if current_data.get("track_id") == track_id:
                current_data["videoId"] = v_id or ""
                debug_log(f"[video-bg] atual pronto: {bool(v_id)}")

        next_video_id = ""
        if next_track_data:
            try:
                next_artist = next_track_data["artists"][0]["name"]
                next_name = next_track_data["name"]
                next_query = f"{next_artist} {next_name}"
                debug_log(f"[video-bg] analisando proximo: {next_query}")

                with video_resolution_lock:
                    next_already_running = next_query in video_resolution_queries
                    if not next_already_running:
                        video_resolution_queries.add(next_query)
                    else:
                        debug_log(f"[video-bg] proximo ja em andamento: {next_query}")

                if not next_already_running:
                    try:
                        debug_log(f"[video-bg] resolvendo proximo: {next_query}")
                        next_video_id = get_yt_video_cached(
                            next_query,
                            target_duration_seconds=(next_track_data.get("duration_ms", 0) or 0) / 1000,
                            artist_name=next_artist,
                            track_name=next_name
                        )
                        debug_log(f"[video-bg] proximo pronto: {bool(next_video_id)}")
                    finally:
                        with video_resolution_lock:
                            video_resolution_queries.discard(next_query)
            except Exception as e:
                debug_log(f"Erro fila: {e}")

        with video_resolution_lock:
            if current_data.get("track_id") == track_id:
                current_data["nextVideoId"] = next_video_id or ""
                current_data["nextTrackId"] = (next_track_data or {}).get("id", "") or ""
            if video_resolution_track_id == track_id:
                video_resolution_track_id = ""
    finally:
        with video_resolution_lock:
            video_resolution_queries.discard(query)
        debug_log(f"[video-bg] finalizado: {query}")


def limpar_contexto_artista(artist_name):
    with artist_context_lock:
        artist_context["artist"] = artist_name
        artist_context["loading"] = True


def carregar_dados_artista():
    if not ARTIST_DATA_FILE.exists():
        return {
            "curiosidades": [],
            "instagram": "",
            "website": "",
            "agenda": "",
            "status": "",
            "proximo_show": "",
            "ultimo_show": "",
            "image_urls": []
        }

    try:
        conteudo = ARTIST_DATA_FILE.read_text(encoding="utf-8")
        dados = json.loads(conteudo.replace("const dadosArtista = ", "").rstrip(";"))
    except Exception:
        dados = {
            "curiosidades": [],
            "instagram": "",
            "website": "",
            "agenda": "",
            "status": "",
            "proximo_show": "",
            "ultimo_show": "",
        }

    image_urls = []
    for indice in range(1, 6):
        caminho = ARTIST_IMAGES_DIR / f"foto{indice}.jpg"
        if caminho.exists():
            image_urls.append(
                f"/artist-image/foto{indice}.jpg?ts={int(caminho.stat().st_mtime)}"
            )

    dados["image_urls"] = image_urls
    return dados


def executar_script_artistico(script_name, artist_name):
    if VENV_PYTHON.exists():
        python_cmd = str(VENV_PYTHON)
    else:
        python_cmd = sys.executable if sys.executable else "py"
    script_path = PROJECT_DIR / script_name
    comando = [python_cmd, str(script_path), artist_name]
    debug_log(f"[artist-pipeline] executando {script_name} para {artist_name}", category="artist")
    resultado = subprocess.run(
        comando,
        cwd=str(PROJECT_DIR),
        check=False,
        capture_output=True,
        text=True
    )
    if resultado.stdout:
        debug_log(f"[artist-pipeline][{script_name}][stdout]\n{resultado.stdout}", category="artist")
    if resultado.stderr:
        debug_log(f"[artist-pipeline][{script_name}][stderr]\n{resultado.stderr}", category="artist")
    if resultado.returncode != 0:
        print(f"[artist-pipeline] {script_name} falhou com cÃ³digo {resultado.returncode}")
    return resultado.returncode == 0


def limpar_midia_artista():
    try:
        if ARTIST_DATA_FILE.exists():
            ARTIST_DATA_FILE.unlink()
    except Exception:
        pass

    try:
        if ARTIST_IMAGES_DIR.exists():
            for arquivo in ARTIST_IMAGES_DIR.glob("foto*.jpg"):
                try:
                    arquivo.unlink()
                except Exception:
                    pass
    except Exception:
        pass


def enriquecer_artista(artist_name):
    global enrichment_thread, pending_artist_enrichment, last_artist_enrichment, artist_context_revision
    try:
        limpar_midia_artista()
        etapas = [
            ("search.py", False),
            ("agenda.py", False),
            ("fotos.py", False),
        ]

        def publicar_contexto_parcial():
            global artist_context_revision
            dados_parciais = carregar_dados_artista()
            with artist_context_lock:
                artist_context_revision += 1
                artist_context["artist"] = artist_name
                artist_context["loading"] = True
                artist_context["updated_at"] = artist_context_revision
                artist_context["data"] = dados_parciais
            debug_log(f"[artist-pipeline] contexto parcial atualizado para {artist_name}", category="artist")

        for idx, (script_name, _) in enumerate(etapas):
            if pending_artist_enrichment and pending_artist_enrichment != artist_name:
                debug_log(f"[artist-pipeline] artista mudou durante {artist_name}; abortando pipeline atual.", category="artist")
                return
            etapas[idx] = (script_name, executar_script_artistico(script_name, artist_name))
            if etapas[idx][1] and script_name in {"search.py", "agenda.py"}:
                publicar_contexto_parcial()

        ok_search = etapas[0][1]
        ok_agenda = etapas[1][1]
        ok_fotos = etapas[2][1]
        dados = carregar_dados_artista()
        debug_log(
            f"[artist-pipeline] resultados search={ok_search} agenda={ok_agenda} "
            f"fotos={ok_fotos}",
            category="artist"
        )
        if pending_artist_enrichment and pending_artist_enrichment != artist_name:
            debug_log(f"[artist-pipeline] descartando resultado de {artist_name}; novo artista pendente.", category="artist")
            return
        with artist_context_lock:
            artist_context_revision += 1
            artist_context["artist"] = artist_name
            artist_context["loading"] = False
            artist_context["updated_at"] = artist_context_revision
            artist_context["data"] = dados
        debug_log(f"[artist-pipeline] contexto atualizado para {artist_name}", category="artist")
    except Exception as e:
        print(f"[artist-pipeline] erro ao enriquecer artista: {e}")
        with artist_context_lock:
            artist_context_revision += 1
            artist_context["artist"] = artist_name
            artist_context["loading"] = False
            artist_context["updated_at"] = artist_context_revision
    finally:
        enrichment_thread = None
        if pending_artist_enrichment and pending_artist_enrichment != artist_name:
            proximo = pending_artist_enrichment
            pending_artist_enrichment = ""
            last_artist_enrichment = ""
            agendar_enriquecimento(proximo)


def agendar_enriquecimento(artist_name):
    global enrichment_thread, last_artist_enrichment, pending_artist_enrichment

    if not artist_name:
        return
    if artist_name == last_artist_enrichment:
        return
    if enrichment_thread and enrichment_thread.is_alive():
        debug_log(f"[artist-pipeline] novo artista pendente: {artist_name}", category="artist")
        pending_artist_enrichment = artist_name
        return

    last_artist_enrichment = artist_name
    pending_artist_enrichment = ""
    limpar_contexto_artista(artist_name)
    enrichment_thread = threading.Thread(target=enriquecer_artista, args=(artist_name,), daemon=True)
    enrichment_thread.start()


def build_queue_preview(items):
    preview = []
    for item in (items or [])[:4]:
        artists = item.get("artists", [])
        preview.append({
            "title": item.get("name", ""),
            "artist": artists[0]["name"] if artists else "",
            "cover": ((item.get("album") or {}).get("images") or [{}])[0].get("url", "")
        })
    return preview


def refresh_queue_preview(force=False):
    global last_queue_request_time, queue_preview_cache, sp

    if not sp:
        return queue_preview_cache

    now = time.time()
    if now < spotify_backoff_until:
        return queue_preview_cache
    if not force and (now - last_queue_request_time) < 20:
        return queue_preview_cache

    request_event = None
    try:
        queue_data, timed_out = call_spotify_with_timeout(
            sp.queue,
            timeout_seconds=3.5,
            label="queue"
        )
        if timed_out:
            debug_log("[spotify] queue preview demorou demais; mantendo fila em cache")
            return queue_preview_cache
        items = queue_data.get("queue", []) if queue_data else []
        queue_preview_cache = build_queue_preview(items)
        last_queue_request_time = now
    except Exception as e:
        apply_spotify_backoff_from_exception(e, label="queue-preview")
        debug_log(f"Erro queue preview: {e}")

    return queue_preview_cache


def call_spotify_with_timeout(fn, timeout_seconds=3.5, label="spotify"):
    global spotify_backoff_until

    result = {"value": None, "error": None}
    endpoint_map = {
        "current_playback": "/v1/me/player",
        "queue": "/v1/me/player/queue"
    }
    now = time.time()
    with spotify_call_state_lock:
        active_started_at = spotify_call_active.get(label)
        if active_started_at:
            if (now - active_started_at) >= max(8.0, timeout_seconds * 2):
                spotify_call_active.pop(label, None)
            else:
                maybe_log_spotify_request_window(reason=f"{label}-busy")
                debug_log(f"[spotify] {label} ainda em andamento; reutilizando estado atual")
                return None, True
        spotify_call_active[label] = now
    request_event = register_spotify_request(endpoint_map.get(label, label))

    def runner():
        try:
            result["value"] = fn()
        except Exception as exc:
            result["error"] = exc
        finally:
            with spotify_call_state_lock:
                spotify_call_active.pop(label, None)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout_seconds)

    if thread.is_alive():
        finalize_spotify_request(request_event, "timeout")
        maybe_log_spotify_request_window(reason=label)
        debug_log(f"[spotify-timeout] {label} excedeu {timeout_seconds:.1f}s")
        if label in {"current_playback", "queue"}:
            spotify_backoff_until = max(spotify_backoff_until, time.time() + 6)
        return None, True

    if result["error"] is not None:
        finalize_spotify_request(request_event, "error")
        maybe_log_spotify_request_window(reason=label)
        raise result["error"]

    finalize_spotify_request(request_event, "ok")
    maybe_log_spotify_request_window(reason=label)
    return result["value"], False


def apply_spotify_backoff_from_exception(error, label="spotify"):
    global spotify_backoff_until

    http_status = getattr(error, "http_status", None) or getattr(error, "status", None)
    headers = getattr(error, "headers", None) or {}
    retry_after = 0
    try:
        retry_after = int(headers.get("Retry-After", 0) or 0)
    except Exception:
        retry_after = 0

    if http_status == 429:
        wait_seconds = max(5, retry_after or 10)
        spotify_backoff_until = max(spotify_backoff_until, time.time() + wait_seconds)
        debug_log(f"[spotify] {label} entrou em rate limit; retry em {wait_seconds}s")
        return True

    return False


def resolver_proxima_faixa_em_segundo_plano(track_id):
    global last_queue_request_time, queue_preview_cache

    if not sp:
        return

    try:
        queue_data, timed_out = call_spotify_with_timeout(
            sp.queue,
            timeout_seconds=3.5,
            label="queue"
        )
        if timed_out:
            debug_log("[spotify] fila em segundo plano demorou demais; mantendo proxima faixa em cache")
            return
        items = queue_data.get("queue", []) if queue_data else []
        queue_preview_cache = build_queue_preview(items)
        last_queue_request_time = time.time()

        next_track = items[0] if items else None
        if not next_track:
            with video_resolution_lock:
                if current_data.get("track_id") == track_id:
                    current_data["nextTrackId"] = ""
                    current_data["nextVideoId"] = ""
            return

        next_track_id = next_track.get("id", "") or ""
        next_artist = next_track["artists"][0]["name"] if next_track.get("artists") else ""
        next_name = next_track.get("name", "")
        next_video_id = get_cached_yt_video_only(
            f"{next_artist} {next_name}",
            target_duration_seconds=(next_track.get("duration_ms", 0) or 0) / 1000
        )

        with video_resolution_lock:
            if current_data.get("track_id") == track_id:
                current_data["nextTrackId"] = next_track_id
                current_data["nextVideoId"] = next_video_id or ""

        if next_track_id and next_artist and next_name and not next_video_id:
            with video_resolution_lock:
                next_query = f"{next_artist} {next_name}"
                next_already_running = next_query in video_resolution_queries
                if not next_already_running:
                    video_resolution_queries.add(next_query)
                else:
                    return
            try:
                next_video_id = get_yt_video_cached(
                    next_query,
                    target_duration_seconds=(next_track.get("duration_ms", 0) or 0) / 1000,
                    artist_name=next_artist,
                    track_name=next_name
                )
                with video_resolution_lock:
                    if current_data.get("track_id") == track_id:
                        current_data["nextTrackId"] = next_track_id
                        current_data["nextVideoId"] = next_video_id or ""
            finally:
                with video_resolution_lock:
                    video_resolution_queries.discard(next_query)
    except Exception as e:
        apply_spotify_backoff_from_exception(e, label="queue-bg")
        debug_log(f"Erro fila bg: {e}")

def update_playback_data():
    global current_data, last_track_id, last_request_time, sp, video_resolution_track_id
    global spotify_backoff_until, track_change_cooldown_until, last_queue_request_time, queue_preview_cache
    global pending_fast_polls, fast_poll_interval_until, current_video_retry_track_id
    global current_video_retry_attempts, last_spotify_success_at, consecutive_pause_reports

    config = load_config()
    if not config.get("CLIENT_ID") or config.get("CLIENT_ID") == "SEU_ID":
        current_data["status"] = "SETUP_REQUIRED"
        return

    if not sp:
        init_services()
        if not sp:
            current_data["status"] = "SETUP_REQUIRED"
            return

    now = time.time()
    if now < spotify_backoff_until:
        debug_log(f"[spotify] em backoff por mais {max(0, spotify_backoff_until - now):.1f}s")
        apply_cached_playback_progress(now)
        return

    poll_interval = 1.6
    if pending_fast_polls > 0 and now < fast_poll_interval_until:
        poll_interval = 0.6

    if current_data.get("track_id") and current_data.get("duration_ms"):
        progress_ms = max(0, int(current_data.get("progress_ms") or 0))
        duration_ms = max(0, int(current_data.get("duration_ms") or 0))
        remaining_ms = max(0, duration_ms - progress_ms)
        if progress_ms > 0 and progress_ms < 3000:
            poll_interval = max(poll_interval, 2.4)
        elif remaining_ms > 0 and remaining_ms <= 4000:
            has_handoff_ready = bool(current_data.get("nextVideoId") or current_data.get("nextTrackId"))
            if has_handoff_ready:
                poll_interval = min(poll_interval, 1.0)
            else:
                poll_interval = max(poll_interval, 2.8)
            
    if now - last_request_time < poll_interval:
        return

    try:
        current, timed_out = call_spotify_with_timeout(
            sp.current_playback,
            timeout_seconds=3.5,
            label="current_playback"
        )
        if timed_out:
            debug_log("[spotify] current_playback demorou demais; mantendo ultimo estado conhecido")
            spotify_backoff_until = time.time() + 6
            apply_cached_playback_progress(now)
            return
        last_request_time = now
        last_spotify_success_at = now

        if current and current["item"]:
            track_id = current["item"]["id"]
            artist = current["item"]["artists"][0]["name"]
            track_name = current["item"]["name"]
            cover = current["item"]["album"]["images"][0]["url"]
            promoted_next_video_id = ""

            if track_id != last_track_id:
                previous_next_track_id = current_data.get("nextTrackId", "") or ""
                previous_next_video_id = current_data.get("nextVideoId", "") or ""
                if previous_next_track_id and previous_next_track_id == track_id and previous_next_video_id:
                    promoted_next_video_id = previous_next_video_id

            if track_id != last_track_id and now < track_change_cooldown_until:
                current_data.update({
                    "title": track_name,
                    "artist": artist,
                    "track_id": track_id,
                    "cover": cover,
                    "status": "OK",
                    "videoId": promoted_next_video_id,
                    "nextVideoId": "",
                    "nextTrackId": "",
                    "is_playing": current["is_playing"],
                    "spotify_time": current["progress_ms"] // 1000,
                    "progress_ms": current["progress_ms"],
                    "duration_ms": current["item"]["duration_ms"]
                })
                if not current_data.get("videoId"):
                    pending_fast_polls = max(pending_fast_polls, 3)
                    fast_poll_interval_until = now + 1.8
                return

            if track_id != last_track_id:
                current_data.update({
                    "title": track_name,
                    "artist": artist,
                    "track_id": track_id,
                    "cover": cover,
                    "status": "OK",
                    "videoId": promoted_next_video_id,
                    "nextVideoId": "",
                    "nextTrackId": ""
                })
                agendar_enriquecimento(artist)
                last_track_id = track_id
                track_change_cooldown_until = now + 0.45
                pending_fast_polls = 0
                fast_poll_interval_until = 0

                debug_log(f"Buscando video: {artist} - {track_name}")
                if promoted_next_video_id:
                    debug_log(f"[video-cache] promovido do pre-cache: {artist} - {track_name}")

                # ðŸ”¥ BUSCA CACHEADA
                current_query = f"{artist} {track_name}"
                if not current_data["videoId"]:
                    cached_video_id = get_cached_yt_video_only(
                        current_query,
                        target_duration_seconds=current["item"]["duration_ms"] / 1000
                    )
                    if cached_video_id:
                        current_data["videoId"] = cached_video_id
                        debug_log(f"[video-cache] atual hit: {artist} - {track_name}")
                    else:
                        debug_log(f"[video-cache] atual miss: {artist} - {track_name}")
                        immediate_video_id = try_resolve_current_video_immediately(
                            current_query,
                            target_duration_seconds=current["item"]["duration_ms"] / 1000,
                            artist_name=artist,
                            track_name=track_name
                        )
                        if immediate_video_id:
                            current_data["videoId"] = immediate_video_id
                            debug_log(f"[video-cache] atual resolvido na troca: {artist} - {track_name}")
                
                # PRE-CACHE DA PRÓXIMA MÚSICA EM SEGUNDO PLANO
                next_track = None
                current_data["nextTrackId"] = ""
                current_data["nextVideoId"] = ""
                threading.Thread(
                    target=resolver_proxima_faixa_em_segundo_plano,
                    args=(track_id,),
                    daemon=True,
                ).start()

                if not current_data["videoId"] or not current_data["nextVideoId"]:
                    debug_log(f"[video-cache] fallback background: atual={bool(current_data['videoId'])} proximo={bool(current_data['nextVideoId'])}")
                    with video_resolution_lock:
                        if video_resolution_track_id != track_id:
                            video_resolution_track_id = track_id
                            threading.Thread(
                                target=resolver_videos_em_segundo_plano,
                                args=(track_id, artist, track_name, current["item"]["duration_ms"], next_track),
                                daemon=True,
                            ).start()

                if not current_data["videoId"]:
                    pending_fast_polls = 3
                    fast_poll_interval_until = now + 1.8
                    current_video_retry_track_id = track_id
                    current_video_retry_attempts = 0

            reported_is_playing = bool(current["is_playing"])
            previous_track_id = current_data.get("track_id", "") or ""
            previous_is_playing = bool(current_data.get("is_playing"))
            if reported_is_playing:
                consecutive_pause_reports = 0
            else:
                same_track = previous_track_id == track_id
                if same_track and previous_is_playing:
                    consecutive_pause_reports += 1
                    debug_log(f"[spotify] pause aguardando confirmacao ({consecutive_pause_reports}/2) para {artist} - {track_name}")
                else:
                    consecutive_pause_reports = max(consecutive_pause_reports, 1)

            effective_is_playing = reported_is_playing
            if not reported_is_playing and previous_track_id == track_id and previous_is_playing and consecutive_pause_reports < 2:
                effective_is_playing = True

            current_data["spotify_time"] = current["progress_ms"] // 1000
            current_data["progress_ms"] = current["progress_ms"]
            current_data["duration_ms"] = current["item"]["duration_ms"]
            current_data["is_playing"] = effective_is_playing

            if current_data.get("track_id") == track_id and not current_data.get("videoId") and pending_fast_polls > 0:
                if current_video_retry_track_id != track_id:
                    current_video_retry_track_id = track_id
                    current_video_retry_attempts = 0
                if current_video_retry_attempts < 2:
                    current_video_retry_attempts += 1
                    retry_video_id = try_resolve_current_video_immediately(
                        f"{artist} {track_name}",
                        target_duration_seconds=current["item"]["duration_ms"] / 1000,
                        artist_name=artist,
                        track_name=track_name
                    )
                    if retry_video_id:
                        current_data["videoId"] = retry_video_id
                        debug_log(f"[video-cache] atual resolvido em retry rapido: {artist} - {track_name}")

            if current_data.get("track_id") == track_id and current_data.get("videoId"):
                pending_fast_polls = 0
                fast_poll_interval_until = 0
                current_video_retry_track_id = ""
                current_video_retry_attempts = 0
            elif current_data.get("track_id") == track_id and pending_fast_polls > 0 and now < fast_poll_interval_until:
                pending_fast_polls -= 1

        else:
            debug_log("[spotify] current_playback retornou vazio")
            if current_data.get("track_id") and last_spotify_success_at and (now - last_spotify_success_at) <= 20:
                debug_log("[spotify] mantendo ultimo playback conhecido apesar de resposta vazia")
                apply_cached_playback_progress(now)
            else:
                current_data["status"] = "IDLE"
                current_data["title"] = ""
                current_data["artist"] = ""
                current_data["cover"] = ""
                current_data["videoId"] = ""
                current_data["nextVideoId"] = ""
                current_data["nextTrackId"] = ""
                current_data["spotify_time"] = 0
                current_data["progress_ms"] = 0
                current_data["duration_ms"] = 0
                current_data["is_playing"] = False
                current_data["track_id"] = ""
                last_track_id = None
                pending_fast_polls = 0
                fast_poll_interval_until = 0
                current_video_retry_track_id = ""
                current_video_retry_attempts = 0
                consecutive_pause_reports = 0
                queue_preview_cache.clear()

    except Exception as e:
        print("Erro playback:", e)
        debug_log(f"[spotify] erro playback: {type(e).__name__}: {e}")
        apply_spotify_backoff_from_exception(e, label="current_playback")


def force_fast_spotify_refresh():
    global last_request_time, track_change_cooldown_until
    last_request_time = 0
    track_change_cooldown_until = 0


@app.route('/status')
def get_status():
    update_playback_data()
    return jsonify(current_data)


@app.route('/session')
def get_session():
    config = ensure_runtime_config()
    has_host_access = request_has_host_access()
    has_api_credentials = bool(config.get("CLIENT_ID")) and bool(config.get("CLIENT_SECRET")) and bool(config.get("YOUTUBE_API_KEY"))
    return jsonify({
        "is_host": has_host_access,
        "can_control": request_can_control_playback(),
        "allow_guest_controls": bool(config.get("ALLOW_GUEST_CONTROLS")),
        "has_api_credentials": has_api_credentials,
        "setup_required": not has_api_credentials,
        "is_local_request": is_local_request(),
        "host_token": config.get("HOST_ACCESS_TOKEN", "") if has_host_access else "",
        "public_base_url": (config.get("PUBLIC_BASE_URL") or "").strip(),
        "tunnel_status": tunnel_status,
        "tunnel_active": tunnel_status == "active"
    })


@app.route('/config')
def get_config():
    denied = require_host_access()
    if denied:
        return denied
    config = ensure_runtime_config()
    return jsonify({
        "CLIENT_ID": config.get("CLIENT_ID", ""),
        "CLIENT_SECRET": config.get("CLIENT_SECRET", ""),
        "YOUTUBE_API_KEY": config.get("YOUTUBE_API_KEY", ""),
        "ALLOW_GUEST_CONTROLS": bool(config.get("ALLOW_GUEST_CONTROLS")),
        "PUBLIC_BASE_URL": (config.get("PUBLIC_BASE_URL") or "").strip()
    })


@app.route('/profiles', methods=['GET'])
def get_profiles():
    profiles_map = prune_profiles(load_profiles())
    now_ts = int(time.time())
    profiles = sorted(
        profiles_map.values(),
        key=lambda item: item.get("created_at", item.get("updated_at", 0)),
    )
    host_client_id = profiles[0]["client_id"] if profiles else ""

    profiles = sorted(
        profiles,
        key=lambda item: item.get("last_seen", item.get("updated_at", 0)),
        reverse=True
    )
    return jsonify({
        "profiles": profiles,
        "total_online": len(profiles),
        "host_client_id": host_client_id,
        "joined_recently_window": PROFILE_JOINED_RECENTLY_SECONDS,
        "server_time": now_ts
    })


@app.route('/profiles', methods=['POST'])
def save_profile():
    try:
        data = request.json or {}
        client_id = (data.get("client_id") or "").strip()
        guest_token = (data.get("guest_token") or "").strip()
        name = (data.get("name") or "").strip()
        avatar = (data.get("avatar") or "").strip()
        now_ts = int(time.time())

        if not client_id or not name:
            return jsonify({"status": "ERROR", "message": "client_id e name sao obrigatorios"}), 400

        profiles_map = prune_profiles(load_profiles())
        existing_profile = profiles_map.get(client_id, {})
        saved_profiles_map = load_saved_profiles()
        saved_profile = find_saved_profile(saved_profiles_map, guest_token=guest_token, client_id=client_id)
        if not guest_token:
            guest_token = (saved_profile.get("guest_token") or "").strip()
        if not guest_token:
            guest_token = build_guest_token()
        recovery_code = (saved_profile.get("recovery_code") or "").strip() or build_guest_recovery_code()
        profile_changed = (
            existing_profile.get("name", "") != name[:80]
            or existing_profile.get("avatar", "") != avatar
        )
        profiles_map[client_id] = {
            "client_id": client_id,
            "guest_token": guest_token,
            "name": name[:80],
            "avatar": avatar,
            "created_at": existing_profile.get("created_at", now_ts),
            "updated_at": now_ts if profile_changed or not existing_profile else existing_profile.get("updated_at", now_ts),
            "last_seen": now_ts
        }
        save_profiles(profiles_map)
        saved_profiles_map[client_id] = {
            "client_id": client_id,
            "guest_token": guest_token,
            "recovery_code": recovery_code,
            "name": name[:80],
            "avatar": avatar,
            "updated_at": now_ts
        }
        save_saved_profiles(saved_profiles_map)
        return jsonify({
            "status": "OK",
            "guest_token": guest_token,
            "recovery_code": recovery_code
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400


@app.route('/profiles/restore')
def restore_profile():
    client_id = (request.args.get("client_id") or "").strip()
    guest_token = (request.args.get("guest_token") or "").strip()
    recovery_code = (request.args.get("recovery_code") or "").strip().upper()
    if not client_id and not guest_token and not recovery_code:
        return jsonify({"status": "ERROR", "message": "client_id, guest_token ou recovery_code e obrigatorio"}), 400

    saved_profiles_map = load_saved_profiles()
    profile = find_saved_profile(saved_profiles_map, guest_token=guest_token, client_id=client_id)
    if not profile and recovery_code:
        for candidate in saved_profiles_map.values():
            if ((candidate.get("recovery_code") or "").strip().upper() == recovery_code):
                profile = candidate
                break
    if not profile:
        return jsonify({"status": "OK", "profile": None})

    return jsonify({
        "status": "OK",
        "profile": {
            "client_id": profile.get("client_id", client_id),
            "guest_token": (profile.get("guest_token") or "").strip(),
            "recovery_code": (profile.get("recovery_code") or "").strip(),
            "name": (profile.get("name") or "").strip(),
            "avatar": (profile.get("avatar") or "").strip(),
            "updated_at": int(profile.get("updated_at", 0) or 0)
        }
    })


@app.route('/lyrics/search')
def search_lyrics():
    artist = (request.args.get("artist") or "").strip()
    track = (request.args.get("track") or "").strip()

    candidates = buscar_lrclib_candidatas(artist, track)

    if not candidates:
        lyrics_ovh_candidate = buscar_lyrics_ovh(artist, track)
        if lyrics_ovh_candidate:
            candidates.append(lyrics_ovh_candidate)

    return jsonify({
        "artist": artist,
        "track": track,
        "candidates": candidates
    })


@app.route('/lyrics/translate', methods=['POST'])
def translate_lyrics():
    try:
        payload = request.json or {}
        lines = payload.get("lines") or []
        target = (payload.get("target") or "pt-BR").strip() or "pt-BR"
        line_limit = int(payload.get("line_limit") or 0)

        if not isinstance(lines, list) or not lines:
            return jsonify({"lines": []})

        if line_limit > 0:
            subset = lines[:line_limit]
            translated_subset, _provider = translate_lyrics_lines(subset, target=target, prefer_local=False)
            merged = [str(line or "") for line in lines]
            for idx, translated_line in enumerate(translated_subset or []):
                if idx < len(merged):
                    merged[idx] = translated_line or merged[idx]
            return jsonify({"lines": merged, "partial": True})

        translated, _provider = translate_lyrics_lines(lines, target=target, prefer_local=False)
        return jsonify({"lines": translated, "partial": False})
    except Exception as e:
        print("[lyrics-translate] erro:", e)
        return jsonify({"lines": []})


@app.route('/artist-context')
def get_artist_context():
    with artist_context_lock:
        payload = {
            "artist": artist_context["artist"],
            "loading": artist_context["loading"],
            "updated_at": artist_context["updated_at"],
            **artist_context["data"]
        }
    return jsonify(payload)


@app.route('/queue-preview')
def get_queue_preview():
    return jsonify({
        "items": refresh_queue_preview(),
        "updated_at": int(time.time())
    })


@app.route('/artist-image/<path:filename>')
def get_artist_image(filename):
    if not ARTIST_IMAGES_DIR.exists():
        return ("", 404)
    return send_from_directory(ARTIST_IMAGES_DIR, filename)


@app.route('/artist-widget')
def get_artist_widget():
    if not ARTIST_WIDGET_FILE.exists():
        return ("", 404)
    try:
        html = ARTIST_WIDGET_FILE.read_text(encoding="utf-8")
    except Exception:
        html = ARTIST_WIDGET_FILE.read_text(encoding="latin-1")
    if "<head>" in html:
        html = html.replace("<head>", '<head><base href="/">', 1)
    return Response(html, mimetype="text/html; charset=utf-8")


@app.route('/dados_artista.js')
def get_artist_data_js():
    if not ARTIST_DATA_FILE.exists():
        return ("const dadosArtista = {};", 200, {"Content-Type": "application/javascript; charset=utf-8"})
    return send_from_directory(PROJECT_DIR, "dados_artista.js")


@app.route('/spotify/callback')
def spotify_callback():
    error = (request.args.get("error") or "").strip()
    code = (request.args.get("code") or "").strip()
    if error:
        runtime_log(f"[yp2.spotify_callback] error={error}")
        return Response(
            "<script>window.location='/?spotify_auth=error';</script>Spotify auth error.",
            mimetype="text/html; charset=utf-8"
        )
    if not code:
        runtime_log("[yp2.spotify_callback] missing code")
        return Response(
            "<script>window.location='/?spotify_auth=missing_code';</script>Spotify auth missing code.",
            mimetype="text/html; charset=utf-8"
        )

    try:
        auth = create_spotify_oauth(open_browser=False)
        auth.get_access_token(code=code, check_cache=False)
        init_services(open_browser=False)
        runtime_log("[yp2.spotify_callback] token captured successfully")
        return Response(
            "<script>window.location='/?spotify_auth=ok';</script>Spotify connected.",
            mimetype="text/html; charset=utf-8"
        )
    except Exception as exc:
        runtime_log(f"[yp2.spotify_callback] token exchange failed: {exc!r}")
        return Response(
            "<script>window.location='/?spotify_auth=exchange_error';</script>Spotify token exchange failed.",
            mimetype="text/html; charset=utf-8"
        )


@app.route('/spotify/auth-url')
def spotify_auth_url():
    denied = require_host_access()
    if denied:
        return denied
    auth_url = get_spotify_authorization_url()
    if not auth_url:
        return jsonify({"status": "ERROR", "message": "Spotify authorization URL unavailable"}), 400
    return jsonify({"status": "OK", "url": auth_url})


@app.route('/')
def serve_app_index():
    return send_from_directory(PROJECT_DIR, "index.html")


@app.route('/img_artista/<path:filename>')
def get_widget_image(filename):
    if not ARTIST_IMAGES_DIR.exists():
        return ("", 404)
    return send_from_directory(ARTIST_IMAGES_DIR, filename)

@app.route('/setup', methods=['POST'])
def setup_keys():
    runtime_log(f"[yp2.setup] pid={os.getpid()} /setup called")
    denied = require_host_access()
    if denied:
        return denied
    try:
        data = request.json or {}
        config = ensure_runtime_config()
        config.update({
            "CLIENT_ID": (data.get("CLIENT_ID") or "").strip(),
            "CLIENT_SECRET": (data.get("CLIENT_SECRET") or "").strip(),
            "YOUTUBE_API_KEY": (data.get("YOUTUBE_API_KEY") or "").strip(),
            "ALLOW_GUEST_CONTROLS": bool(data.get("ALLOW_GUEST_CONTROLS")),
            "GUEST_CONTROL_PREF_SET": True,
            "PUBLIC_BASE_URL": (data.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
        })
        save_config(config)

        needs_spotify_browser = not has_cached_spotify_token(config)
        runtime_log(f"[yp2.setup] pid={os.getpid()} needs_spotify_browser={needs_spotify_browser}")
        auth_url = ""
        if needs_spotify_browser:
            auth_url = get_spotify_authorization_url(config)
            if not auth_url:
                return jsonify({"status": "ERROR", "message": "Nao foi possivel preparar a autorizacao do Spotify"}), 400
        init_services(open_browser=False)
        if needs_spotify_browser:
            return jsonify({
                "status": "OK",
                "spotify_auth_required": True,
                "spotify_auth_url": auth_url
            })
        if sp:
            return jsonify({"status": "OK"})
        else:
            return jsonify({"status": "ERROR", "message": "Credenciais Spotify invÃ¡lidas"}), 400
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400


@app.route('/host/preferences', methods=['POST'])
def update_host_preferences():
    denied = require_host_access()
    if denied:
        return denied
    try:
        payload = request.json or {}
        config = ensure_runtime_config()
        config["ALLOW_GUEST_CONTROLS"] = bool(payload.get("ALLOW_GUEST_CONTROLS"))
        config["GUEST_CONTROL_PREF_SET"] = True
        if "PUBLIC_BASE_URL" in payload:
            config["PUBLIC_BASE_URL"] = (payload.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
        save_config(config)
        return jsonify({
            "status": "OK",
            "allow_guest_controls": bool(config.get("ALLOW_GUEST_CONTROLS")),
            "public_base_url": (config.get("PUBLIC_BASE_URL") or "").strip()
        })
    except Exception as e:
        return jsonify({"status": "ERROR", "message": str(e)}), 400


@app.route('/tunnel/status')
def get_tunnel_status():
    denied = require_host_access()
    if denied:
        return denied
    return jsonify(get_tunnel_payload())


@app.route('/tunnel/start', methods=['POST'])
def start_tunnel():
    denied = require_host_access()
    if denied:
        return denied
    ok, payload = start_tunnel_process()
    return jsonify(payload), (200 if ok else 400)


@app.route('/tunnel/stop', methods=['POST'])
def stop_tunnel():
    global tunnel_process, tunnel_status, tunnel_public_url, tunnel_last_log
    denied = require_host_access()
    if denied:
        return denied

    stop_tunnel_process()
    return jsonify({"status": "OK", **get_tunnel_payload()})

@app.route('/play', methods=['POST'])
def play_command():
    global last_spotify_success_at, consecutive_pause_reports
    if not request_can_control_playback():
        return jsonify({"status": "ERROR", "message": "Controle indisponivel para convidados"}), 403
    request_event = None
    try:
        if sp:
            request_event = register_spotify_request("/v1/me/player/play")
            sp.start_playback()
            finalize_spotify_request(request_event, "ok")
            maybe_log_spotify_request_window(reason="play")
            current_data["is_playing"] = True
            current_data["status"] = "OK"
            last_spotify_success_at = time.time()
            consecutive_pause_reports = 0
            force_fast_spotify_refresh()
        return jsonify({"status": "OK"})
    except Exception as e:
        try:
            finalize_spotify_request(request_event, "error")
            maybe_log_spotify_request_window(reason="play-error")
        except Exception:
            pass
        return jsonify({"status": "ERROR", "message": str(e)}), 400

@app.route('/pause', methods=['POST'])
def pause_command():
    global consecutive_pause_reports, last_spotify_success_at
    if not request_can_control_playback():
        return jsonify({"status": "ERROR", "message": "Controle indisponivel para convidados"}), 403
    request_event = None
    try:
        if sp:
            request_event = register_spotify_request("/v1/me/player/pause")
            sp.pause_playback()
            finalize_spotify_request(request_event, "ok")
            maybe_log_spotify_request_window(reason="pause")
            current_data["is_playing"] = False
            current_data["status"] = "OK"
            consecutive_pause_reports = 2
            last_spotify_success_at = time.time()
            force_fast_spotify_refresh()
        return jsonify({"status": "OK"})
    except Exception as e:
        try:
            finalize_spotify_request(request_event, "error")
            maybe_log_spotify_request_window(reason="pause-error")
        except Exception:
            pass
        return jsonify({"status": "ERROR", "message": str(e)}), 400


@app.route('/next', methods=['POST'])
def next_command():
    if not request_can_control_playback():
        return jsonify({"status": "ERROR", "message": "Controle indisponivel para convidados"}), 403
    request_event = None
    try:
        if sp:
            request_event = register_spotify_request("/v1/me/player/next")
            sp.next_track()
            finalize_spotify_request(request_event, "ok")
            maybe_log_spotify_request_window(reason="next")
            force_fast_spotify_refresh()
        return jsonify({"status": "OK"})
    except Exception as e:
        try:
            finalize_spotify_request(request_event, "error")
            maybe_log_spotify_request_window(reason="next-error")
        except Exception:
            pass
        return jsonify({"status": "ERROR", "message": str(e)}), 400

@app.route('/prev', methods=['POST'])
def prev_command():
    if not request_can_control_playback():
        return jsonify({"status": "ERROR", "message": "Controle indisponivel para convidados"}), 403
    request_event = None
    try:
        if sp:
            request_event = register_spotify_request("/v1/me/player/previous")
            sp.previous_track()
            finalize_spotify_request(request_event, "ok")
            maybe_log_spotify_request_window(reason="previous")
            force_fast_spotify_refresh()
        return jsonify({"status": "OK"})
    except Exception as e:
        try:
            finalize_spotify_request(request_event, "error")
            maybe_log_spotify_request_window(reason="previous-error")
        except Exception:
            pass
        return jsonify({"status": "ERROR", "message": str(e)}), 400

def run_app(open_browser=True):
    global console_first_client_seen
    runtime_log(f"[yp2.run_app] pid={os.getpid()} open_browser={bool(open_browser)}")
    ensure_runtime_support_files()
    console_first_client_seen = False
    mimetypes.add_type('application/javascript', '.js')
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    logging.getLogger("stanza").setLevel(logging.ERROR)
    logging.getLogger("stanza.pipeline").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("transformers").setLevel(logging.ERROR)
    if transformers_logging is not None:
        try:
            transformers_logging.set_verbosity_error()
        except Exception:
            pass
    warnings.filterwarnings(
        "ignore",
        message=r".*expects mwt.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=r".*You are sending unauthenticated requests to the HF Hub.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=r".*tie model\.shared\.weight.*",
    )

    print("-" * 35)
    print(" NONUSER35 SYNC ENGINE v5.1 ")
    print("-" * 35)
    print("[server] jam local: http://localhost:5000")
    print("[server] convidado: use o link publico do tunnel apontando para :5000")
    print("[server] preparando navegador e primeira carga da jam...")
    start_console_boot_spinner()

    try:
        config = ensure_runtime_config()
        if config.get("CLIENT_ID") and config.get("CLIENT_SECRET") and not has_cached_spotify_token(config):
            runtime_log(f"[yp2.run_app] pid={os.getpid()} missing spotify token; opening auth browser")
            open_spotify_authorization_browser(config)
    except Exception as exc:
        runtime_log(f"[yp2.run_app] pid={os.getpid()} spotify auth startup check failed: {exc!r}")

    try:
        init_services(open_browser=False)
    except Exception as exc:
        runtime_log(f"[yp2.run_app] pid={os.getpid()} init_services startup failed: {exc!r}")

    if open_browser:
        runtime_log(f"[yp2.run_app] pid={os.getpid()} opening browser for localhost")
        webbrowser.open("http://localhost:5000")
    app.run(port=5000, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    cleanup_local_runtime_processes()
    run_app()

