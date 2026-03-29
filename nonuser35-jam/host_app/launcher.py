from pathlib import Path
import os
import sys
import threading
import multiprocessing
import runpy
import tempfile
import urllib.parse
import urllib.request
import webbrowser
import tkinter as tk
import subprocess

try:
    import ctypes
except Exception:
    ctypes = None

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


def get_runtime_root():
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


RUNTIME_ROOT = get_runtime_root()
sys.path.insert(0, str(RUNTIME_ROOT))
sys.path.insert(0, str(RUNTIME_ROOT / "projeto"))
yp2 = None


APP_URL = "http://localhost:5000"
browser_opened = False
server_thread = None
app_icon_image = None
qr_image = None
last_qr_url = ""
current_lang = "pt"
single_instance_handle = None


def get_runtime_log_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "logs" / "host_runtime.log"
    return Path(__file__).resolve().parent / "logs" / "host_runtime.log"


def runtime_log(message):
    try:
        log_path = get_runtime_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{message}\n")
    except Exception:
        pass


def cleanup_previous_runtime_processes():
    current_pid = os.getpid()
    host_exe_name = Path(sys.executable).name.replace("'", "''")
    yp2_path = str((RUNTIME_ROOT / "projeto" / "yp2.py").resolve()).replace("'", "''")
    launcher_path = str(Path(__file__).resolve()).replace("'", "''")
    ps_script = rf"""
$ErrorActionPreference = 'SilentlyContinue'
$currentPid = {current_pid}
$hostExeName = '{host_exe_name}'
$yp2Path = '{yp2_path}'
$launcherPath = '{launcher_path}'
Get-CimInstance Win32_Process | Where-Object {{
    $_.ProcessId -ne $currentPid -and (
        ($_.Name -ieq $hostExeName) -or
        ((($_.Name -ieq 'python.exe') -or ($_.Name -ieq 'pythonw.exe')) -and (($_.CommandLine -like "*$yp2Path*") -or ($_.CommandLine -like "*$launcherPath*"))) -or
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
        runtime_log(f"[cleanup] pid={current_pid} startup cleanup attempted")
    except Exception as exc:
        runtime_log(f"[cleanup] pid={current_pid} cleanup failed: {exc!r}")


def detect_worker_script():
    if len(sys.argv) < 2:
        return None
    candidate = Path(sys.argv[1])
    if candidate.suffix.lower() != ".py":
        return None
    if not candidate.exists():
        return None
    return candidate


def run_embedded_worker(script_path):
    runtime_log(f"[worker-mode] pid={os.getpid()} script={script_path} argv={sys.argv}")
    original_argv = sys.argv[:]
    original_cwd = os.getcwd()
    try:
        sys.argv = [str(script_path), *original_argv[2:]]
        os.chdir(str(script_path.parent))
        if str(script_path.parent) not in sys.path:
            sys.path.insert(0, str(script_path.parent))
        try:
            runpy.run_path(str(script_path), run_name="__main__")
            runtime_log(f"[worker-mode] pid={os.getpid()} script={script_path} completed")
            return 0
        except Exception as exc:
            runtime_log(f"[worker-mode] pid={os.getpid()} script={script_path} failed: {exc!r}")
            return 1
    finally:
        sys.argv = original_argv
        try:
            os.chdir(original_cwd)
        except Exception:
            pass


runtime_log(
    f"[launcher-import] pid={os.getpid()} ppid={getattr(os, 'getppid', lambda: 0)()} "
    f"argv={sys.argv} frozen={getattr(sys, 'frozen', False)} exe={getattr(sys, 'executable', '')}"
)

COPY = {
    "pt": {
        "title": "NONUSER35 JAM Host",
        "subtitle": "Painel de controle do host. Use esta janela para abrir a jam, compartilhar o link dos convidados e acompanhar o estado da sala.",
        "server": "Servidor",
        "room": "Sala",
        "controls": "Controles",
        "tunnel": "Tunnel",
        "link": "Link publico dos convidados",
        "spotify_api": "Spotify API",
        "spotify_limit": "Limite Spotify",
        "live_panel_title": "Painel de controle do host",
        "live_panel_desc": "Acompanhe o estado da sala e use as acoes principais sem se perder em detalhes tecnicos.",
        "share_title": "Compartilhe com convidados",
        "share_desc": "Este bloco mostra o link publico dos convidados. Gere o link, confira o QR e copie o acesso para compartilhar a sala.",
        "host_link_title": "Link local do host",
        "host_link_desc": "Este e o endereco local do servidor do host. Use no proprio computador do host.",
        "guest_link_title": "Link publico dos convidados",
        "guest_link_desc": "Este e o link publico que os convidados devem abrir para entrar na jam.",
        "details_show": "Mostrar detalhes tecnicos",
        "details_hide": "Ocultar detalhes tecnicos",
        "hint_default": "Fechar esta janela encerra a jam e o cloudflared. As APIs e perfis salvos continuam guardados.",
        "action_default": "Tudo pronto para iniciar a sala.",
        "open": "Abrir jam",
        "copy": "Copiar link dos convidados",
        "start_tunnel": "Gerar link publico",
        "stop_tunnel": "Encerrar link",
        "close": "Encerrar app/jam",
        "server_active": "Ativo em http://localhost:5000",
        "server_stopped": "Servidor finalizado",
        "room_fmt": "{count} pessoa(s) na jam",
        "controls_open": "Convidados podem controlar",
        "controls_locked": "Somente o host controla",
        "tunnel_active": "Link publico ativo",
        "tunnel_starting": "Gerando link publico...",
        "tunnel_saved": "Link salvo",
        "tunnel_idle": "Link publico inativo",
        "link_wait": "Aguarde alguns segundos",
        "copy_ok": "Link copiado para a area de transferencia.",
        "copy_fail": "Nao foi possivel copiar o link.",
        "qr_placeholder": "QR e link publico dos convidados aparecem aqui",
        "qr_loading": "Gerando QR e link publico dos convidados...",
        "qr_fail": "Nao foi possivel gerar o QR agora",
        "tunnel_started_hint": "Tunnel iniciado. Quando o link estiver pronto, use 'Copiar link'.",
        "tunnel_started_action": "Tunnel iniciado. Aguarde o link publico ficar pronto.",
        "tunnel_stop_hint": "Link publico encerrado.",
        "tunnel_stop_action": "Link publico encerrado com sucesso.",
        "tunnel_start_fail": "Falha ao iniciar o link publico.",
        "about_title": "Como funciona",
        "about_body": "O host conecta Spotify e YouTube uma vez. O site acompanha a musica do host, reproduz a faixa equivalente na jam e mostra letra, contexto visual e perfis dos convidados na mesma interface.",
        "apis_title": "Para que servem as APIs",
        "apis_body": "Spotify informa a faixa atual e o estado da reproducao. YouTube Data API v3 encontra a musica que o player da jam vai tocar. Cloudflare Tunnel cria o link publico para convidados fora da rede local.",
        "policy_title": "Uso, privacidade e responsabilidade",
        "policy_body": "Este projeto existe para pesquisa, estudo e experimentacao tecnica. Nao ha finalidade comercial, venda, endosso oficial ou garantia de funcionamento continuo. Credenciais, links e permissoes ficam sob responsabilidade do host. O uso ocorre por conta e risco de quem hospeda ou acessa a jam.",
        "boot_title": "Iniciando sua jam local",
        "boot_body": "O app esta preparando o painel do host, ligando o servidor local e deixando o navegador pronto para abrir a sala.",
        "boot_step_prepare": "Preparando o painel local do host...",
        "boot_step_engine": "Carregando o motor da jam...",
        "boot_step_server": "Ligando o servidor local na porta 5000...",
        "boot_step_browser": "Quase pronto. O navegador sera aberto em seguida.",
        "spotify_window_idle": "Ultimos 30s: 0 requests",
        "spotify_window_fmt": "Ultimos {seconds}s: {total} requests",
        "spotify_limit_ok": "Sem bloqueio atual",
        "spotify_limit_wait": "Limitada agora. Reset em {remaining}",
    },
    "en": {
        "title": "NONUSER35 JAM Host",
        "subtitle": "Host control panel. Use this window to open the jam, share the guest link, and follow the room status.",
        "server": "Server",
        "room": "Room",
        "controls": "Controls",
        "tunnel": "Tunnel",
        "link": "Guest public link",
        "spotify_api": "Spotify API",
        "spotify_limit": "Spotify limit",
        "live_panel_title": "Host control panel",
        "live_panel_desc": "Follow the room state and use the main actions without getting lost in technical detail.",
        "share_title": "Share with guests",
        "share_desc": "This block shows the guests' public link. Generate it, check the QR, and copy the access to share the room.",
        "host_link_title": "Host local link",
        "host_link_desc": "This is the host's local server address. Use it on the host computer itself.",
        "guest_link_title": "Guest public link",
        "guest_link_desc": "This is the public link guests should open to join the jam.",
        "details_show": "Show technical details",
        "details_hide": "Hide technical details",
        "hint_default": "Closing this window shuts down the jam and cloudflared. Saved APIs and profiles remain stored.",
        "action_default": "Everything is ready to start the room.",
        "open": "Open jam",
        "copy": "Copy guest link",
        "start_tunnel": "Generate public link",
        "stop_tunnel": "Stop link",
        "close": "Close app/jam",
        "server_active": "Active at http://localhost:5000",
        "server_stopped": "Server stopped",
        "room_fmt": "{count} people in the jam",
        "controls_open": "Guests can control playback",
        "controls_locked": "Only the host controls playback",
        "tunnel_active": "Public link active",
        "tunnel_starting": "Generating public link...",
        "tunnel_saved": "Saved link",
        "tunnel_idle": "Public link inactive",
        "link_wait": "Please wait a few seconds",
        "copy_ok": "Link copied to clipboard.",
        "copy_fail": "Could not copy the link.",
        "qr_placeholder": "The guest QR and public link will appear here",
        "qr_loading": "Generating the guest QR and public link...",
        "qr_fail": "Could not generate the QR right now",
        "tunnel_started_hint": "Tunnel started. When the link is ready, use 'Copy link'.",
        "tunnel_started_action": "Tunnel started. Wait for the public link to become ready.",
        "tunnel_stop_hint": "Public link closed.",
        "tunnel_stop_action": "Public link closed successfully.",
        "tunnel_start_fail": "Failed to start the public link.",
        "about_title": "How it works",
        "about_body": "The host connects Spotify and YouTube once. The site follows the host's current music, plays the equivalent track in the jam, and shows lyrics, visual artist context, and guest profiles in the same interface.",
        "apis_title": "What the APIs do",
        "apis_body": "Spotify tells the app which track is playing and its playback state. YouTube Data API v3 finds the music the jam player should play. Cloudflare Tunnel creates the public link for guests outside the local network.",
        "policy_title": "Usage, privacy, and responsibility",
        "policy_body": "This project exists for research, study, and technical experimentation. It is not intended for commercial use, sales, official endorsement, or guaranteed uptime. Credentials, links, and permissions remain the host's responsibility. Use is at your own risk.",
        "boot_title": "Starting your local jam",
        "boot_body": "The app is preparing the host panel, starting the local server, and getting the browser ready to open the room.",
        "boot_step_prepare": "Preparing the local host panel...",
        "boot_step_engine": "Loading the jam engine...",
        "boot_step_server": "Starting the local server on port 5000...",
        "boot_step_browser": "Almost ready. The browser will open next.",
        "spotify_window_idle": "Last 30s: 0 requests",
        "spotify_window_fmt": "Last {seconds}s: {total} requests",
        "spotify_limit_ok": "No active limit",
        "spotify_limit_wait": "Limited now. Reset in {remaining}",
    },
}


def text(key):
    return COPY[current_lang][key]


def load_backend_module():
    global yp2
    if yp2 is not None:
        return yp2
    runtime_log(f"[backend-load] pid={os.getpid()} importing yp2")
    import yp2 as yp2_module  # noqa: E402
    yp2 = yp2_module
    return yp2


def open_jam():
    global browser_opened
    if browser_opened:
        runtime_log(f"[open_jam] pid={os.getpid()} skipped because browser_opened=True")
        return
    try:
        runtime_log(f"[open_jam] pid={os.getpid()} opening={APP_URL} browser_opened={browser_opened}")
        browser_opened = True
        webbrowser.open(APP_URL)
    except Exception:
        browser_opened = False
        pass


def run_server():
    runtime_log(f"[run_server] pid={os.getpid()} starting server thread")
    backend = load_backend_module()
    backend.run_app(open_browser=False)


def acquire_single_instance():
    global single_instance_handle
    if os.name != "nt" or ctypes is None:
        return True
    try:
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "nonuser35-jam-host-single-instance")
        if not mutex:
            return True
        single_instance_handle = mutex
        already_exists = ctypes.windll.kernel32.GetLastError() == 183
        runtime_log(f"[single-instance] pid={os.getpid()} already_exists={already_exists}")
        return not already_exists
    except Exception:
        return True


def shutdown_app(root):
    runtime_log(f"[shutdown_app] pid={os.getpid()} shutting down")
    try:
        backend = load_backend_module()
        backend.shutdown_runtime()
    finally:
        try:
            root.destroy()
        except Exception:
            pass
        os._exit(0)


def build_ui():
    global app_icon_image
    root = tk.Tk()
    root.geometry("840x920")
    root.minsize(760, 820)
    root.configure(bg="#07110d")
    icon_ico_path = RUNTIME_ROOT / "host_app" / "app_icon.ico"
    icon_path = RUNTIME_ROOT / "host_app" / "app_icon.png"
    if icon_ico_path.exists():
        try:
            root.iconbitmap(str(icon_ico_path))
        except Exception:
            pass
    if icon_path.exists():
        try:
            app_icon_image = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, app_icon_image)
        except Exception:
            pass

    title_var = tk.StringVar(value=text("title"))
    subtitle_var = tk.StringVar(value=text("subtitle"))
    status_var = tk.StringVar(value="Iniciando servidor local...")
    room_var = tk.StringVar(value="Jam: aguardando")
    control_var = tk.StringVar(value="Controles: aguardando")
    tunnel_var = tk.StringVar(value="Link publico: inativo")
    link_var = tk.StringVar(value=APP_URL)
    spotify_window_var = tk.StringVar(value=text("spotify_window_idle"))
    spotify_limit_var = tk.StringVar(value=text("spotify_limit_ok"))
    live_panel_title_var = tk.StringVar(value=text("live_panel_title"))
    live_panel_desc_var = tk.StringVar(value=text("live_panel_desc"))
    share_title_var = tk.StringVar(value=text("share_title"))
    share_desc_var = tk.StringVar(value=text("share_desc"))
    host_link_title_var = tk.StringVar(value=text("host_link_title"))
    host_link_desc_var = tk.StringVar(value=text("host_link_desc"))
    guest_link_title_var = tk.StringVar(value=text("guest_link_title"))
    guest_link_desc_var = tk.StringVar(value=text("guest_link_desc"))
    host_local_link_var = tk.StringVar(value=APP_URL)
    details_toggle_var = tk.StringVar(value=text("details_show"))
    hint_var = tk.StringVar(value=text("hint_default"))
    action_var = tk.StringVar(value=text("action_default"))
    about_title_var = tk.StringVar(value=text("about_title"))
    about_body_var = tk.StringVar(value=text("about_body"))
    apis_title_var = tk.StringVar(value=text("apis_title"))
    apis_body_var = tk.StringVar(value=text("apis_body"))
    policy_title_var = tk.StringVar(value=text("policy_title"))
    policy_body_var = tk.StringVar(value=text("policy_body"))
    labels = {}
    responsive_labels = []

    root.title(text("title"))

    main_shell = tk.Frame(root, bg="#07110d")
    main_shell.pack(fill="both", expand=True)

    viewport_canvas = tk.Canvas(
        main_shell,
        bg="#07110d",
        highlightthickness=0,
        bd=0,
        relief="flat"
    )
    viewport_canvas.pack(side="left", fill="both", expand=True)

    viewport_scrollbar = tk.Scrollbar(
        main_shell,
        orient="vertical",
        command=viewport_canvas.yview
    )
    viewport_scrollbar.pack(side="right", fill="y")
    viewport_canvas.configure(yscrollcommand=viewport_scrollbar.set)

    content_frame = tk.Frame(viewport_canvas, bg="#07110d")
    viewport_window = viewport_canvas.create_window((0, 0), window=content_frame, anchor="nw")

    outer = tk.Frame(content_frame, bg="#07110d", padx=20, pady=20)
    outer.pack(fill="both", expand=True)

    hero = tk.Frame(outer, bg="#0d1713", padx=18, pady=18, highlightthickness=1, highlightbackground="#224034")
    hero.pack(fill="x")

    header = tk.Frame(hero, bg="#0d1713")
    header.pack(fill="x")

    left_header = tk.Frame(header, bg="#0d1713")
    left_header.pack(side="left", fill="x", expand=True)

    tk.Label(
        left_header,
        textvariable=title_var,
        fg="#f2fff6",
        bg="#0d1713",
        font=("Segoe UI Semibold", 22)
    ).pack(anchor="w")

    subtitle_label = tk.Label(
        left_header,
        textvariable=subtitle_var,
        fg="#8fb09a",
        bg="#0d1713",
        font=("Segoe UI", 10)
    )
    subtitle_label.pack(anchor="w", pady=(4, 0))
    responsive_labels.append((subtitle_label, 420, 220))

    hero_badge = tk.Label(
        left_header,
        text="HOST CONSOLE",
        fg="#d9ffe7",
        bg="#13211a",
        font=("Segoe UI Semibold", 9),
        padx=10,
        pady=6
    )
    hero_badge.pack(anchor="w", pady=(12, 0))

    lang_bar = tk.Frame(header, bg="#0d1713")
    lang_bar.pack(side="right")

    def switch_lang(lang):
        global current_lang
        current_lang = lang
        root.title(text("title"))
        title_var.set(text("title"))
        subtitle_var.set(text("subtitle"))
        hint_var.set(text("hint_default"))
        action_var.set(text("action_default"))
        about_title_var.set(text("about_title"))
        about_body_var.set(text("about_body"))
        apis_title_var.set(text("apis_title"))
        apis_body_var.set(text("apis_body"))
        policy_title_var.set(text("policy_title"))
        policy_body_var.set(text("policy_body"))
        labels["server"].set(text("server"))
        labels["room"].set(text("room"))
        labels["controls"].set(text("controls"))
        labels["tunnel"].set(text("tunnel"))
        labels["link"].set(text("link"))
        labels["spotify_api"].set(text("spotify_api"))
        labels["spotify_limit"].set(text("spotify_limit"))
        live_panel_title_var.set(text("live_panel_title"))
        live_panel_desc_var.set(text("live_panel_desc"))
        share_title_var.set(text("share_title"))
        share_desc_var.set(text("share_desc"))
        host_link_title_var.set(text("host_link_title"))
        host_link_desc_var.set(text("host_link_desc"))
        guest_link_title_var.set(text("guest_link_title"))
        guest_link_desc_var.set(text("guest_link_desc"))
        details_toggle_var.set(text("details_hide") if details_open.get() else text("details_show"))
        open_btn.config(text=text("open"))
        copy_btn.config(text=text("copy"))
        tunnel_btn.config(text=text("start_tunnel"))
        stop_tunnel_btn.config(text=text("stop_tunnel"))
        exit_btn.config(text=text("close"))

    pt_btn = tk.Button(lang_bar, text="PT", relief="flat", bg="#15211a", fg="#f4fff7", padx=10, pady=6, command=lambda: switch_lang("pt"), cursor="hand2")
    pt_btn.pack(side="left")
    en_btn = tk.Button(lang_bar, text="EN", relief="flat", bg="#15211a", fg="#f4fff7", padx=10, pady=6, command=lambda: switch_lang("en"), cursor="hand2")
    en_btn.pack(side="left", padx=(8, 0))

    top_card = tk.Frame(outer, bg="#0f1915", padx=18, pady=18, highlightthickness=1, highlightbackground="#1f3a2f")
    top_card.pack(fill="x", pady=(14, 0))

    tk.Label(
        top_card,
        textvariable=live_panel_title_var,
        fg="#effff5",
        bg="#0f1915",
        font=("Segoe UI Semibold", 12)
    ).pack(anchor="w")

    tk.Label(
        top_card,
        textvariable=live_panel_desc_var,
        fg="#87a797",
        bg="#0f1915",
        font=("Segoe UI", 9),
        justify="left",
        wraplength=520
    ).pack(anchor="w", pady=(4, 12))

    def info_row(parent, label_key, value_var):
        row = tk.Frame(parent, bg="#13201a", padx=12, pady=10, highlightthickness=1, highlightbackground="#21372d")
        row.pack(fill="x", pady=4)
        label_var = tk.StringVar(value=text(label_key))
        labels[label_key] = label_var
        tk.Label(
            row,
            textvariable=label_var,
            fg="#7f9f8b",
            bg="#13201a",
            font=("Segoe UI Semibold", 9),
            anchor="w"
        ).pack(anchor="w")
        value_label = tk.Label(
            row,
            textvariable=value_var,
            fg="#eefdf3",
            bg="#13201a",
            font=("Segoe UI Semibold", 10),
            anchor="w",
            justify="left",
            wraplength=520
        )
        value_label.pack(anchor="w", fill="x", expand=True, pady=(2, 0))
        responsive_labels.append((value_label, 520, 220))
        return row

    server_row = info_row(top_card, "server", status_var)
    room_row = info_row(top_card, "room", room_var)
    controls_row = info_row(top_card, "controls", control_var)
    tunnel_row = info_row(top_card, "tunnel", tunnel_var)
    link_row = info_row(top_card, "link", link_var)
    spotify_api_row = info_row(top_card, "spotify_api", spotify_window_var)
    spotify_limit_row = info_row(top_card, "spotify_limit", spotify_limit_var)

    def metric_card(parent, label_key, value_var, accent="#eefdf3"):
        card = tk.Frame(parent, bg="#13201a", padx=14, pady=12, highlightthickness=1, highlightbackground="#21372d")
        card.pack(side="left", fill="both", expand=True)
        label_var = tk.StringVar(value=text(label_key))
        labels[label_key] = label_var
        tk.Label(
            card,
            textvariable=label_var,
            fg="#7f9f8b",
            bg="#13201a",
            font=("Segoe UI Semibold", 9),
            anchor="w"
        ).pack(anchor="w")
        value_label = tk.Label(
            card,
            textvariable=value_var,
            fg=accent,
            bg="#13201a",
            font=("Segoe UI Semibold", 11),
            justify="left",
            wraplength=180
        )
        value_label.pack(anchor="w", fill="x", expand=True, pady=(5, 0))
        responsive_labels.append((value_label, 180, 120))

    summary_shell = tk.Frame(top_card, bg="#0f1915")
    summary_shell.pack(fill="x", pady=(0, 12), before=server_row)

    summary_top = tk.Frame(summary_shell, bg="#0f1915")
    summary_top.pack(fill="x")
    metric_card(summary_top, "server", status_var, accent="#f3fff7")
    tk.Frame(summary_top, width=8, bg="#0f1915").pack(side="left")
    metric_card(summary_top, "tunnel", tunnel_var, accent="#d8ffe6")
    tk.Frame(summary_top, width=8, bg="#0f1915").pack(side="left")
    metric_card(summary_top, "spotify_api", spotify_window_var, accent="#c8fff0")
    tk.Frame(summary_top, width=8, bg="#0f1915").pack(side="left")
    metric_card(summary_top, "spotify_limit", spotify_limit_var, accent="#ffe6b8")

    summary_bottom = tk.Frame(summary_shell, bg="#0f1915")
    summary_bottom.pack(fill="x", pady=(8, 0))
    metric_card(summary_bottom, "room", room_var, accent="#f3fff7")
    tk.Frame(summary_bottom, width=8, bg="#0f1915").pack(side="left")
    metric_card(summary_bottom, "controls", control_var, accent="#d8ffe6")

    details_open = tk.BooleanVar(value=False)
    details_toggle_var.set(text("details_show"))
    details_button = tk.Button(
        top_card,
        textvariable=details_toggle_var,
        bg="#13201a",
        fg="#dfffea",
        activebackground="#1d2d25",
        activeforeground="#f4fff7",
        relief="flat",
        padx=12,
        pady=8,
        cursor="hand2",
        bd=0
    )
    details_button.pack(anchor="w", pady=(0, 12), before=server_row)

    detail_rows = [
        server_row,
        room_row,
        controls_row,
        tunnel_row,
        link_row,
        spotify_api_row,
        spotify_limit_row,
    ]

    def set_details_visible(visible):
        details_open.set(bool(visible))
        details_toggle_var.set(text("details_hide") if visible else text("details_show"))
        for row in detail_rows:
            if visible:
                row.pack(fill="x", pady=4, before=hint_label)
            else:
                row.pack_forget()

    details_button.config(command=lambda: set_details_visible(not details_open.get()))
    set_details_visible(False)

    hint_label = tk.Label(
        top_card,
        textvariable=hint_var,
        fg="#85a592",
        bg="#0f1915",
        font=("Segoe UI", 9),
        wraplength=520,
        justify="left"
    )
    hint_label.pack(anchor="w", pady=(12, 8))
    responsive_labels.append((hint_label, 520, 220))

    tk.Label(
        top_card,
        textvariable=action_var,
        fg="#d8ffe3",
        bg="#0f1915",
        font=("Segoe UI Semibold", 9)
    ).pack(anchor="w", pady=(0, 10))

    share_header = tk.Label(
        top_card,
        textvariable=share_title_var,
        fg="#f2fff6",
        bg="#0f1915",
        font=("Segoe UI Semibold", 11)
    )
    share_header.pack(anchor="w", pady=(2, 0))

    share_desc_label = tk.Label(
        top_card,
        textvariable=share_desc_var,
        fg="#8fb09a",
        bg="#0f1915",
        font=("Segoe UI", 9),
        justify="left",
        wraplength=520
    )
    share_desc_label.pack(anchor="w", pady=(6, 10))
    responsive_labels.append((share_desc_label, 520, 220))

    host_link_card = tk.Frame(top_card, bg="#13201a", padx=12, pady=10, highlightthickness=1, highlightbackground="#21372d")
    host_link_card.pack(fill="x", pady=(0, 8))
    tk.Label(
        host_link_card,
        textvariable=host_link_title_var,
        fg="#7f9f8b",
        bg="#13201a",
        font=("Segoe UI Semibold", 9)
    ).pack(anchor="w")
    host_link_desc_label = tk.Label(
        host_link_card,
        textvariable=host_link_desc_var,
        fg="#8fb09a",
        bg="#13201a",
        font=("Segoe UI", 9),
        justify="left",
        wraplength=520
    )
    host_link_desc_label.pack(anchor="w", pady=(4, 6))
    responsive_labels.append((host_link_desc_label, 520, 220))
    host_link_value_label = tk.Label(
        host_link_card,
        textvariable=host_local_link_var,
        fg="#eefdf3",
        bg="#13201a",
        font=("Segoe UI Semibold", 10),
        justify="left",
        wraplength=520
    )
    host_link_value_label.pack(anchor="w", fill="x", expand=True)
    responsive_labels.append((host_link_value_label, 520, 220))

    guest_link_card = tk.Frame(top_card, bg="#13201a", padx=12, pady=10, highlightthickness=1, highlightbackground="#21372d")
    guest_link_card.pack(fill="x", pady=(0, 10))
    tk.Label(
        guest_link_card,
        textvariable=guest_link_title_var,
        fg="#7f9f8b",
        bg="#13201a",
        font=("Segoe UI Semibold", 9)
    ).pack(anchor="w")
    guest_link_desc_label = tk.Label(
        guest_link_card,
        textvariable=guest_link_desc_var,
        fg="#8fb09a",
        bg="#13201a",
        font=("Segoe UI", 9),
        justify="left",
        wraplength=520
    )
    guest_link_desc_label.pack(anchor="w", pady=(4, 6))
    responsive_labels.append((guest_link_desc_label, 520, 220))
    guest_link_value_label = tk.Label(
        guest_link_card,
        textvariable=link_var,
        fg="#eefdf3",
        bg="#13201a",
        font=("Segoe UI Semibold", 10),
        justify="left",
        wraplength=520
    )
    guest_link_value_label.pack(anchor="w", fill="x", expand=True)
    responsive_labels.append((guest_link_value_label, 520, 220))

    qr_shell = tk.Frame(top_card, bg="#0f1915")
    qr_shell.pack(fill="x", pady=(0, 12))

    qr_preview = tk.Label(
        qr_shell,
        text=text("qr_placeholder"),
        fg="#7f9f8b",
        bg="#13201a",
        font=("Segoe UI", 9),
        justify="center",
        relief="flat",
        padx=20,
        pady=20
    )
    qr_preview.pack(anchor="w")

    def make_btn(parent, text_value, command, primary=False):
        return tk.Button(
            parent,
            text=text_value,
            command=command,
            bg="#e4ffec" if primary else "#17231c",
            fg="#07110c" if primary else "#f4fff7",
            activebackground="#f4fff7" if primary else "#22332a",
            activeforeground="#07110c" if primary else "#f4fff7",
            relief="flat",
            padx=14,
            pady=10,
            cursor="hand2",
            bd=0
        )

    buttons_top = tk.Frame(top_card, bg="#101a15")
    buttons_top.pack(fill="x")

    open_btn = make_btn(buttons_top, text("open"), open_jam, primary=True)
    open_btn.pack(side="left")

    copy_btn = make_btn(buttons_top, text("copy"), lambda: copy_link(root, action_var))
    copy_btn.pack(side="left", padx=(8, 0))

    buttons_bottom = tk.Frame(top_card, bg="#101a15")
    buttons_bottom.pack(fill="x", pady=(10, 0))

    tunnel_btn = make_btn(buttons_bottom, text("start_tunnel"), lambda: start_tunnel_ui(hint_var, action_var))
    tunnel_btn.pack(side="left")

    stop_tunnel_btn = make_btn(buttons_bottom, text("stop_tunnel"), lambda: stop_tunnel_ui(hint_var, action_var))
    stop_tunnel_btn.pack(side="left", padx=(8, 0))

    exit_btn = make_btn(buttons_bottom, text("close"), lambda: shutdown_app(root))
    exit_btn.pack(side="right")

    def info_card(parent, title_var, body_var):
        card = tk.Frame(parent, bg="#101a15", padx=16, pady=16, highlightthickness=1, highlightbackground="#1d2a23")
        card.pack(fill="x", pady=(12, 0))
        tk.Label(card, textvariable=title_var, fg="#f2fff6", bg="#101a15", font=("Segoe UI Semibold", 11)).pack(anchor="w")
        body_label = tk.Label(card, textvariable=body_var, fg="#a9c1b1", bg="#101a15", font=("Segoe UI", 9), wraplength=520, justify="left")
        body_label.pack(anchor="w", pady=(7, 0))
        responsive_labels.append((body_label, 520, 220))

    info_card(outer, about_title_var, about_body_var)
    info_card(outer, apis_title_var, apis_body_var)
    info_card(outer, policy_title_var, policy_body_var)

    def refresh_status():
        global browser_opened
        backend = load_backend_module()
        tunnel_payload = backend.get_tunnel_payload()
        spotify_window_payload = backend.get_spotify_window_payload()
        config = backend.ensure_runtime_config()
        profiles = backend.prune_profiles(backend.load_profiles())
        total_online = len(profiles)
        allow_guests = bool(config.get("ALLOW_GUEST_CONTROLS"))
        public_url = (tunnel_payload.get("public_base_url") or config.get("PUBLIC_BASE_URL") or "").strip()

        if server_thread and server_thread.is_alive():
            status_var.set(text("server_active"))
            if not browser_opened:
                runtime_log(f"[refresh_status] pid={os.getpid()} browser not opened yet, calling open_jam")
                open_jam()
        else:
            status_var.set(text("server_stopped"))

        room_var.set(text("room_fmt").format(count=total_online))
        control_var.set(text("controls_open") if allow_guests else text("controls_locked"))

        if tunnel_payload.get("tunnel_state") == "active" and public_url:
            tunnel_var.set(text("tunnel_active"))
            link_var.set(public_url)
            tunnel_btn.config(state="disabled")
            stop_tunnel_btn.config(state="normal")
            update_qr_preview(public_url, qr_preview, action_var)
        elif tunnel_payload.get("tunnel_state") == "starting":
            tunnel_var.set(text("tunnel_starting"))
            link_var.set(text("link_wait"))
            tunnel_btn.config(state="disabled")
            stop_tunnel_btn.config(state="disabled")
            update_qr_preview("", qr_preview, action_var, loading=True)
        elif public_url:
            tunnel_var.set(text("tunnel_saved"))
            link_var.set(public_url)
            tunnel_btn.config(state="normal")
            stop_tunnel_btn.config(state="normal")
            update_qr_preview(public_url, qr_preview, action_var)
        else:
            tunnel_var.set(text("tunnel_idle"))
            link_var.set(APP_URL)
            tunnel_btn.config(state="normal")
            stop_tunnel_btn.config(state="disabled")
            update_qr_preview("", qr_preview, action_var)

        total_requests = int(spotify_window_payload.get("total_requests") or 0)
        window_seconds = int(spotify_window_payload.get("window_seconds") or 30)
        if total_requests > 0:
            spotify_window_var.set(text("spotify_window_fmt").format(seconds=window_seconds, total=total_requests))
        else:
            spotify_window_var.set(text("spotify_window_idle"))

        if spotify_window_payload.get("limited"):
            spotify_limit_var.set(text("spotify_limit_wait").format(remaining=spotify_window_payload.get("retry_after_human") or "0s"))
        else:
            spotify_limit_var.set(text("spotify_limit_ok"))

        root.after(1200, refresh_status)

    def update_wraps(_event=None):
        try:
            current_width = max(viewport_canvas.winfo_width(), 680)
            for label, base, minimum in responsive_labels:
                label.configure(wraplength=max(minimum, current_width - 80 if base >= 500 else current_width - 220))
        except Exception:
            pass

    def sync_scroll_region(_event=None):
        try:
            viewport_canvas.configure(scrollregion=viewport_canvas.bbox("all"))
            viewport_canvas.itemconfigure(viewport_window, width=viewport_canvas.winfo_width())
        except Exception:
            pass

    def handle_mousewheel(event):
        try:
            if event.delta:
                viewport_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif getattr(event, "num", None) == 4:
                viewport_canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                viewport_canvas.yview_scroll(1, "units")
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", lambda: shutdown_app(root))
    root.bind("<Configure>", update_wraps)
    content_frame.bind("<Configure>", sync_scroll_region)
    viewport_canvas.bind("<Configure>", sync_scroll_region)
    viewport_canvas.bind_all("<MouseWheel>", handle_mousewheel)
    viewport_canvas.bind_all("<Button-4>", handle_mousewheel)
    viewport_canvas.bind_all("<Button-5>", handle_mousewheel)
    root.after(120, update_wraps)
    root.after(160, sync_scroll_region)
    root.after(600, refresh_status)
    return root


def copy_link(root, action_var):
    backend = load_backend_module()
    config = backend.ensure_runtime_config()
    payload = backend.get_tunnel_payload()
    public_url = (payload.get("public_base_url") or config.get("PUBLIC_BASE_URL") or APP_URL).strip()
    try:
        root.clipboard_clear()
        root.clipboard_append(public_url)
        root.update()
        action_var.set(text("copy_ok"))
    except Exception:
        action_var.set(text("copy_fail"))


def update_qr_preview(url, qr_preview, action_var, loading=False):
    global qr_image, last_qr_url
    if loading:
        qr_preview.config(image="", text=text("qr_loading"))
        return
    if not url:
        qr_preview.config(image="", text=text("qr_placeholder"))
        last_qr_url = ""
        return
    if url == last_qr_url and qr_image is not None:
        qr_preview.config(image=qr_image, text="")
        return
    try:
        encoded = urllib.parse.quote(url, safe="")
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=170x170&data={encoded}"
        temp_file = Path(tempfile.gettempdir()) / "nonuser35_jam_qr.png"
        urllib.request.urlretrieve(qr_url, temp_file)
        if Image is not None and ImageTk is not None:
            image = Image.open(temp_file).convert("RGBA").resize((170, 170), Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
            qr_image = ImageTk.PhotoImage(image)
        else:
            qr_image = tk.PhotoImage(file=str(temp_file))
        qr_preview.config(image=qr_image, text="")
        last_qr_url = url
    except Exception:
        qr_preview.config(image="", text=text("qr_fail"))
        action_var.set(text("qr_fail"))


def start_tunnel_ui(hint_var, action_var):
    action_var.set(text("tunnel_starting"))
    backend = load_backend_module()
    ok, payload = backend.start_tunnel_process()
    if ok:
        hint_var.set(text("tunnel_started_hint"))
        action_var.set(text("tunnel_started_action"))
    else:
        hint_var.set(payload.get("message") or text("tunnel_start_fail"))
        action_var.set(text("tunnel_start_fail"))


def stop_tunnel_ui(hint_var, action_var):
    backend = load_backend_module()
    backend.stop_tunnel_process()
    hint_var.set(text("tunnel_stop_hint"))
    action_var.set(text("tunnel_stop_action"))


def show_boot_window():
    boot = tk.Tk()
    boot.geometry("560x340")
    boot.minsize(540, 320)
    boot.configure(bg="#07110d")
    boot.title(text("title"))

    icon_ico_path = RUNTIME_ROOT / "host_app" / "app_icon.ico"
    icon_path = RUNTIME_ROOT / "host_app" / "app_icon.png"
    if icon_ico_path.exists():
        try:
            boot.iconbitmap(str(icon_ico_path))
        except Exception:
            pass
    if icon_path.exists():
        try:
            boot_icon = tk.PhotoImage(file=str(icon_path))
            boot.iconphoto(True, boot_icon)
            boot._boot_icon = boot_icon
        except Exception:
            pass

    shell = tk.Frame(boot, bg="#07110d", padx=24, pady=24)
    shell.pack(fill="both", expand=True)

    card = tk.Frame(shell, bg="#0f1915", padx=24, pady=24, highlightthickness=1, highlightbackground="#214033")
    card.pack(fill="both", expand=True)

    tk.Label(
        card,
        text="HOST BOOT",
        fg="#d8ffe6",
        bg="#13211a",
        font=("Segoe UI Semibold", 9),
        padx=10,
        pady=6
    ).pack(anchor="w", pady=(0, 12))

    tk.Label(
        card,
        text=text("boot_title"),
        fg="#f2fff6",
        bg="#0f1915",
        font=("Segoe UI Semibold", 20)
    ).pack(anchor="w")

    body_label = tk.Label(
        card,
        text=text("boot_body"),
        fg="#9fbeaa",
        bg="#0f1915",
        font=("Segoe UI", 10),
        justify="left",
        wraplength=450
    )
    body_label.pack(anchor="w", pady=(10, 16))

    step_var = tk.StringVar(value=text("boot_step_prepare"))
    step_label = tk.Label(
        card,
        textvariable=step_var,
        fg="#dffff0",
        bg="#13201a",
        font=("Segoe UI Semibold", 10),
        padx=14,
        pady=12,
        justify="left",
        anchor="w"
    )
    step_label.pack(fill="x")

    details = tk.Label(
        card,
        text="Spotify + YouTube + Cloudflare + painel local",
        fg="#6f8e7c",
        bg="#0f1915",
        font=("Segoe UI", 9)
    )
    details.pack(anchor="w", pady=(12, 0))

    boot.update_idletasks()
    return boot, step_var


if __name__ == "__main__":
    worker_script = detect_worker_script()
    if worker_script is not None:
        raise SystemExit(run_embedded_worker(worker_script))
    runtime_log(f"[main-entry] pid={os.getpid()} entering main")
    multiprocessing.freeze_support()
    cleanup_previous_runtime_processes()
    if not acquire_single_instance():
        runtime_log(f"[main-entry] pid={os.getpid()} blocked by single-instance mutex")
        sys.exit(0)
    boot, boot_step_var = show_boot_window()
    try:
        boot_step_var.set(text("boot_step_engine"))
        boot.update()
        load_backend_module()
        boot_step_var.set(text("boot_step_server"))
        boot.update()
    except Exception:
        try:
            boot.destroy()
        except Exception:
            pass
        raise
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    boot_step_var.set(text("boot_step_browser"))
    boot.update()
    try:
        boot.destroy()
    except Exception:
        pass
    ui = build_ui()
    ui.mainloop()
