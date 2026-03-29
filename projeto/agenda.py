import json
import re
import sys
import os
from io import BytesIO
from pathlib import Path
from datetime import date, datetime
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup
try:
    from PIL import Image
except Exception:
    Image = None
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
except Exception:
    webdriver = None
    Options = None
    Service = None
    By = None
    ChromeDriverManager = None

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception


VENUE_IMAGE_CACHE_FILE = "venue_images.json"
VENUE_IMAGE_DIR = "img_venue"


def can_use_playwright():
    if sync_playwright is None:
        return False

    if not getattr(sys, "frozen", False):
        return True

    try:
        runtime_root = Path(getattr(sys, "_MEIPASS", "") or "").resolve()
    except Exception:
        return False

    candidates = [
        runtime_root / "playwright" / "driver" / "package" / ".local-browsers",
        runtime_root / "projeto" / "playwright" / "driver" / "package" / ".local-browsers",
    ]
    return any(candidate.exists() for candidate in candidates)

TRAD_DIAS = {
    "Mon": "Seg",
    "Tue": "Ter",
    "Wed": "Qua",
    "Thu": "Qui",
    "Fri": "Sex",
    "Sat": "Sab",
    "Sun": "Dom",
}

TRAD_MESES = {
    "Jan": "Jan",
    "Feb": "Fev",
    "Mar": "Mar",
    "Apr": "Abr",
    "May": "Mai",
    "Jun": "Jun",
    "Jul": "Jul",
    "Aug": "Ago",
    "Sep": "Set",
    "Oct": "Out",
    "Nov": "Nov",
    "Dec": "Dez",
}

SOCIAL_BLACKLIST = [
    "songkick.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "spotify.com",
    "music.apple.com",
    "tiktok.com",
    "wikipedia.org",
    "schema.org",
    "schemas.",
    "toolforge.org",
    "fist.php",
]


def traduzir_data(texto):
    texto = " ".join((texto or "").split())
    for en, pt in TRAD_DIAS.items():
        texto = re.sub(fr"\b{en}\b", pt, texto, flags=re.IGNORECASE)
    for en, pt in TRAD_MESES.items():
        texto = re.sub(fr"\b{en}\b", pt, texto, flags=re.IGNORECASE)
    return texto.strip()


def formatar_data_iso_para_evento(valor):
    if not valor:
        return ""

    bruto = str(valor).strip()
    candidato = bruto.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(candidato)
        return traduzir_data(dt.strftime("%d %b %Y"))
    except Exception:
        pass

    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", bruto)
    if not match:
        return ""

    ano, mes, dia = match.groups()
    try:
        dt = date(int(ano), int(mes), int(dia))
        return traduzir_data(dt.strftime("%d %b %Y"))
    except Exception:
        return ""


def parse_date_like(value):
    if not value:
        return None

    bruto = str(value).strip()
    try:
        return datetime.fromisoformat(bruto.replace("Z", "+00:00")).date()
    except Exception:
        pass

    match = re.match(r"(\d{4})-(\d{2})-(\d{2})", bruto)
    if not match:
        return None

    ano, mes, dia = match.groups()
    try:
        return date(int(ano), int(mes), int(dia))
    except Exception:
        return None


def limpar_texto_evento(texto):
    texto = traduzir_data(texto or "")
    texto = re.sub(r"\s+\d+\s+RSVPs?\b.*$", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s+interested\b.*$", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s+\|\s+", " | ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip(" -|")


def extrair_query_local_evento(evento):
    texto = limpar_texto_evento(evento or "")
    if not texto:
        return ""

    candidato = texto

    candidato = re.sub(
        r"^(seg|ter|qua|qui|sex|sab|dom|mon|tue|wed|thu|fri|sat|sun)\s+",
        "",
        candidato,
        flags=re.IGNORECASE,
    )
    candidato = re.sub(
        r"^\d{1,2}(?:[-/]\d{1,2})?\s+[A-Za-zÀ-ÿ]{3,}\s+\d{4}\s*[-|,:]*\s*",
        "",
        candidato,
        flags=re.IGNORECASE,
    )
    candidato = re.sub(r"^\d{4}-\d{2}-\d{2}\s*[-|,:]*\s*", "", candidato)
    candidato = candidato.replace("|", " ")
    candidato = re.sub(r"\s+", " ", candidato).strip(" -|,")
    return candidato


def extrair_query_localidade_evento(evento):
    texto = limpar_texto_evento(evento or "")
    if not texto or "|" not in texto:
        return ""

    partes = [parte.strip(" -|,") for parte in texto.split("|") if parte.strip(" -|,")]
    if len(partes) < 2:
        return ""

    localidade = " ".join(partes[1:])
    localidade = re.sub(r"\s+", " ", localidade).strip(" -|,")
    return localidade


def is_valid_venue_image_url(url):
    href = str(url or "").strip()
    if not href.startswith("http"):
        return False

    href_lower = href.lower()
    blocked_parts = (
        "/ip3/",
        ".ico",
        ".svg",
        "favicon",
        "logo",
        "icon",
        "sprite",
    )
    if any(part in href_lower for part in blocked_parts):
        return False
    return True


def normalize_venue_image_url(url):
    href = str(url or "").strip()
    if not href.startswith("http"):
        return ""

    try:
        parsed = urlparse(href)
        if "external-content.duckduckgo.com" in parsed.netloc and parsed.path.startswith("/iu/"):
            params = parse_qs(parsed.query)
            original = (params.get("u") or [""])[0]
            original = unquote(original).strip()
            if original.startswith("http"):
                href = original
    except Exception:
        pass

    return href


def obter_vqd_duckduckgo(sessao, consulta):
    try:
        for url in ("https://duckduckgo.com/", "https://html.duckduckgo.com/html/"):
            resposta = sessao.get(
                url,
                params={
                    "q": consulta,
                    "iax": "images",
                    "ia": "images",
                },
                headers={
                    "Referer": "https://duckduckgo.com/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                timeout=12,
            )
            resposta.raise_for_status()
            match = re.search(r'vqd=["\']([^"\']+)["\']', resposta.text)
            if not match:
                match = re.search(r"vqd=([0-9-]+)", resposta.text)
            if match:
                return match.group(1)
    except Exception:
        return ""
    return ""


def buscar_imagens_duckduckgo_selenium(consulta, limit=4):
    if not all([webdriver, Options, Service, By, ChromeDriverManager]):
        return []

    imagens = []
    vistos = set()
    driver = None
    try:
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1400,1000")
        options.add_argument("user-agent=Mozilla/5.0")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(f"https://duckduckgo.com/?q={requests.utils.quote(consulta)}&iax=images&ia=images")
        driver.implicitly_wait(2)

        for _ in range(3):
            thumbs = driver.find_elements(By.CSS_SELECTOR, "img")
            for thumb in thumbs:
                src = (thumb.get_attribute("src") or "").strip()
                data_src = (thumb.get_attribute("data-src") or "").strip()
                candidate = normalize_venue_image_url(data_src or src)
                if not is_valid_venue_image_url(candidate):
                    continue
                if candidate in vistos:
                    continue
                vistos.add(candidate)
                imagens.append(candidate)
                if len(imagens) >= limit:
                    return imagens

            driver.execute_script("window.scrollBy(0, 1200);")
    except Exception:
        return []
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

    return imagens


def buscar_imagens_duckduckgo(sessao, consulta, limit=4):
    # Para venues, o caminho mais consistente é o mesmo usado nas fotos do artista:
    # abrir o DDG Images e capturar as primeiras imagens reais renderizadas.
    imagens = buscar_imagens_duckduckgo_selenium(consulta, limit=limit)
    if imagens:
        return imagens

    # Fallback leve por JSON apenas se o Selenium não devolver nada.
    try:
        vqd = obter_vqd_duckduckgo(sessao, consulta)
        if not vqd:
            return []

        resposta_img = sessao.get(
            "https://duckduckgo.com/i.js",
            params={
                "l": "us-en",
                "o": "json",
                "q": consulta,
                "vqd": vqd,
                "f": ",,,",
                "p": "1",
            },
            headers={
                "Referer": f"https://duckduckgo.com/?q={requests.utils.quote(consulta)}&iax=images&ia=images",
                "Accept": "application/json,text/javascript,*/*;q=0.8",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=12,
        )
        resposta_img.raise_for_status()
        resultados = (resposta_img.json() or {}).get("results", []) or []
        vistos = set()
        imagens = []
        for item in resultados:
            image_url = normalize_venue_image_url((item.get("image") or item.get("thumbnail") or "").strip())
            if not is_valid_venue_image_url(image_url) or image_url in vistos:
                continue
            vistos.add(image_url)
            imagens.append(image_url)
            if len(imagens) >= limit:
                break
        return imagens
    except Exception:
        return []


def buscar_imagem_venue(sessao, venue_query):
    consulta = (venue_query or "").strip()
    if not consulta:
        return ""

    cache = carregar_cache_venue()
    cache_key = f"v9::{consulta.lower()}"
    if cache_key in cache:
        cached = cache.get(cache_key, "")
        if isinstance(cached, list):
            return cached[0] if cached else ""
        return cached or ""

    image_url = ""
    try:
        imagens = buscar_imagens_duckduckgo(sessao, consulta, limit=4)
        image_url = imagens[0] if imagens else ""
        if not image_url:
            resposta = sessao.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": f'intitle:"{consulta}"',
                    "utf8": 1,
                    "format": "json",
                    "srlimit": 5,
                },
                timeout=12,
            )
            resposta.raise_for_status()
            resultados = (resposta.json() or {}).get("query", {}).get("search", []) or []

            melhor = resultados[0] if resultados else None

            if melhor and melhor.get("pageid"):
                resposta_img = sessao.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "pageids": melhor["pageid"],
                        "prop": "pageimages",
                        "pithumbsize": 1200,
                        "format": "json",
                    },
                    timeout=12,
                )
                resposta_img.raise_for_status()
                pages = (resposta_img.json() or {}).get("query", {}).get("pages", {}) or {}
                page_data = pages.get(str(melhor["pageid"]), {}) or {}
                image_url = ((page_data.get("thumbnail") or {}).get("source") or "").strip()
    except Exception:
        image_url = ""

    if image_url:
        cache[cache_key] = image_url
        salvar_cache_venue(cache)
    return image_url


def buscar_imagens_venue(sessao, venue_query, limit=4):
    consulta = (venue_query or "").strip()
    if not consulta:
        return []

    cache = carregar_cache_venue()
    cache_key = f"v9::{consulta.lower()}"
    cached = cache.get(cache_key)
    if isinstance(cached, list):
        return [img for img in cached if img][:limit]
    if isinstance(cached, str) and cached:
        return [cached]

    imagens = buscar_imagens_duckduckgo(sessao, consulta, limit=limit)
    if not imagens:
        imagem_unica = buscar_imagem_venue(sessao, consulta)
        imagens = [imagem_unica] if imagem_unica else []

    if imagens:
        cache[cache_key] = imagens
        salvar_cache_venue(cache)
    return imagens


def limpar_imagens_venue_locais():
    pasta = Path(VENUE_IMAGE_DIR)
    if not pasta.exists():
        return
    for arquivo in pasta.glob("venue*.jpg"):
        try:
            arquivo.unlink()
        except Exception:
            continue


def baixar_imagens_venue_locais(sessao, image_urls, limit=4):
    pasta = Path(VENUE_IMAGE_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    limpar_imagens_venue_locais()

    salvas = []
    vistos = set()

    for image_url in image_urls or []:
        if len(salvas) >= limit:
            break
        url = str(image_url or "").strip()
        if not url or url in vistos:
            continue
        vistos.add(url)
        try:
            resposta = sessao.get(url, timeout=15, stream=True)
            resposta.raise_for_status()
            content_type = (resposta.headers.get("Content-Type") or "").lower()
            if content_type and not content_type.startswith("image/"):
                continue
            content = resposta.content
            if len(content) < 12 * 1024:
                continue
            if Image is not None:
                try:
                    with Image.open(BytesIO(content)) as img:
                        width, height = img.size
                    if width < 220 or height < 160:
                        continue
                except Exception:
                    continue
            caminho = pasta / f"venue{len(salvas) + 1}.jpg"
            with open(caminho, "wb") as arquivo:
                arquivo.write(content)
            salvas.append(f"{VENUE_IMAGE_DIR}/{caminho.name}")
        except Exception:
            continue

    return salvas


def carregar_dados():
    try:
        with open("dados_artista.js", "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read()
        return json.loads(conteudo.replace("const dadosArtista = ", "").rstrip(";"))
    except Exception:
        return {
            "curiosidades": [],
            "instagram": "",
            "website": "",
            "agenda": "",
            "status": "",
            "proximo_show": "",
            "ultimo_show": "",
            "venue_image_url": "",
            "venue_image_urls": [],
        }


def salvar_dados(dados):
    with open("dados_artista.js", "w", encoding="utf-8") as arquivo:
        arquivo.write(f"const dadosArtista = {json.dumps(dados, ensure_ascii=False)};")


def carregar_cache_venue():
    try:
        with open(VENUE_IMAGE_CACHE_FILE, "r", encoding="utf-8") as arquivo:
            data = json.load(arquivo)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def salvar_cache_venue(cache):
    try:
        with open(VENUE_IMAGE_CACHE_FILE, "w", encoding="utf-8") as arquivo:
            json.dump(cache, arquivo, ensure_ascii=False, indent=2)
    except Exception:
        pass


def criar_sessao():
    sessao = requests.Session()
    sessao.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        }
    )
    return sessao


def normalizar_artista(texto):
    return re.sub(r"[^a-z0-9]", "", (texto or "").lower())


def slug_artista(texto):
    texto = (texto or "").lower().strip()
    texto = re.sub(r"^[\"'`]+|[\"'`]+$", "", texto)
    texto = re.sub(r"^\bthe\b\s+", "", texto, flags=re.IGNORECASE)
    texto = texto.replace("&", " and ")
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    texto = re.sub(r"-{2,}", "-", texto).strip("-")
    return texto


def buscar_link_artista_songkick(sessao, artista):
    resposta = sessao.get(
        "https://www.songkick.com/search",
        params={"query": artista},
        timeout=20,
    )
    resposta.raise_for_status()
    soup = BeautifulSoup(resposta.text, "html.parser")

    artista_norm = normalizar_artista(artista)
    melhor_href = ""
    melhor_score = -1

    for link in soup.select('a[href*="/artists/"]'):
        href = (link.get("href") or "").strip()
        texto = " ".join(link.get_text(" ", strip=True).split())
        if "/artists/" not in href:
            continue

        href_abs = href if href.startswith("http") else urljoin("https://www.songkick.com", href)
        texto_norm = normalizar_artista(texto)
        href_norm = normalizar_artista(href_abs)

        score = 0
        if texto_norm == artista_norm:
            score += 10
        elif artista_norm and artista_norm in texto_norm:
            score += 6
        if artista_norm and artista_norm in href_norm:
            score += 4

        if score > melhor_score:
            melhor_score = score
            melhor_href = href_abs

    return melhor_href


def buscar_link_artista_bandsintown(sessao, artista):
    slug_base = slug_artista(artista)
    slug_completo = re.sub(r"[^a-z0-9]+", "-", (artista or "").lower()).strip("-")
    if slug_base:
        candidatos_diretos = [
            f"https://www.bandsintown.com/a/{slug_base}",
            f"https://www.bandsintown.com/a/{slug_completo}",
            f"https://www.bandsintown.com/a/{normalizar_artista(artista)}",
        ]
        for candidato in candidatos_diretos:
            try:
                resposta = sessao.get(candidato, timeout=12, allow_redirects=True)
                if resposta.ok and "bandsintown" in resposta.url and "/a/" in resposta.url:
                    texto = resposta.text.lower()
                    if normalizar_artista(artista) in normalizar_artista(texto[:5000]):
                        return resposta.url
            except Exception:
                continue

    consultas = [
        f'site:bandsintown.com/a/ "{artista}" bandsintown',
        f"site:bandsintown.com/a/ {artista} bandsintown",
    ]

    artista_norm = normalizar_artista(artista)
    melhor_href = ""
    melhor_score = -1

    for consulta in consultas:
        try:
            resposta = sessao.get(
                "https://duckduckgo.com/html/",
                params={"q": consulta},
                timeout=20,
            )
            resposta.raise_for_status()
            soup = BeautifulSoup(resposta.text, "html.parser")

            for link in soup.select('a[href]'):
                href = (link.get("href") or "").strip()
                texto = " ".join(link.get_text(" ", strip=True).split())
                href_abs = href if href.startswith("http") else urljoin("https://duckduckgo.com", href)
                href_abs = requests.utils.unquote(href_abs)
                if "bandsintown.com/a/" not in href_abs:
                    continue

                texto_norm = normalizar_artista(texto)
                href_norm = normalizar_artista(href_abs)
                score = 0
                if texto_norm == artista_norm:
                    score += 10
                elif artista_norm and artista_norm in texto_norm:
                    score += 6
                if artista_norm and artista_norm in href_norm:
                    score += 4

                if score > melhor_score:
                    melhor_score = score
                    melhor_href = href_abs.split("&rut=")[0]
        except Exception:
            continue

        if melhor_href:
            break

    return melhor_href


def converter_para_labs(artist_url):
    match = re.search(r"/artists/([^/?#]+)", artist_url)
    if not match:
        return ""
    slug = match.group(1)
    return f"https://labs.songkick.com/artists/{slug}"


def converter_para_labs_calendar(artist_url):
    labs_url = converter_para_labs(artist_url)
    if not labs_url:
        return ""
    return f"{labs_url}/calendar"


def converter_para_regular_calendar(artist_url):
    if not artist_url:
        return ""
    return artist_url.rstrip("/") + "/calendar"


def extrair_site_e_instagram(soup, artista):
    instagram = ""
    website = ""
    artista_limpo = normalizar_artista(artista)

    for link in soup.find_all("a", href=True):
        href = (link.get("href") or "").strip()
        texto = " ".join(link.get_text(" ", strip=True).split()).lower()
        if href.startswith("//"):
            href = "https:" + href
        if not href.startswith("http"):
            continue

        href_lower = href.lower()
        if "instagram.com" in href_lower and not instagram:
            match = re.search(r"instagram\.com/([^/?#\s]+)", href, re.IGNORECASE)
            if match:
                usuario = match.group(1).strip("/")
                if usuario.lower() not in {"p", "reels", "stories", "explore"}:
                    instagram = f"@{usuario}"

        if any(item in href_lower for item in SOCIAL_BLACKLIST):
            continue

        host = urlparse(href_lower).netloc.replace("www.", "")
        host_norm = normalizar_artista(host)
        if "official" not in texto and "website" not in texto and "site" not in texto:
            continue
        if artista_limpo and artista_limpo in host_norm:
            website = href
            break

    return instagram, website


def extrair_status(texto):
    texto_lower = texto.lower()
    if "on tour" in texto_lower or "currently touring" in texto_lower or "em turnê" in texto_lower or "de gira" in texto_lower:
        return "On tour"
    if "off tour" in texto_lower or "no concert dates" in texto_lower or "fora de turnê" in texto_lower or "sin gira" in texto_lower:
        return "Off tour"
    return ""


def carregar_json_seguro(texto):
    try:
        return json.loads(texto)
    except Exception:
        return None


def iterar_objetos_json(valor):
    if isinstance(valor, dict):
        yield valor
        for item in valor.values():
            yield from iterar_objetos_json(item)
    elif isinstance(valor, list):
        for item in valor:
            yield from iterar_objetos_json(item)


def tipo_json_e_evento(obj):
    tipos = obj.get("@type") or obj.get("type") or ""
    if isinstance(tipos, list):
        tipos = " ".join(str(item) for item in tipos)
    return bool(re.search(r"\b(?:MusicEvent|Event)\b", str(tipos), re.IGNORECASE))


def extrair_evento_estruturado_obj(obj):
    if not isinstance(obj, dict) or not tipo_json_e_evento(obj):
        return None

    data_bruta = obj.get("startDate") or obj.get("start_date") or obj.get("datetime") or obj.get("date")
    data_evento = parse_date_like(data_bruta)
    data_formatada = formatar_data_iso_para_evento(data_bruta)

    local_nome = ""
    cidade = ""
    estado = ""
    pais = ""

    location = obj.get("location") or obj.get("venue") or {}
    if isinstance(location, dict):
        local_nome = (location.get("name") or "").strip()
        endereco = location.get("address") or location.get("geo") or {}
        if isinstance(endereco, dict):
            cidade = (endereco.get("addressLocality") or endereco.get("city") or "").strip()
            estado = (endereco.get("addressRegion") or endereco.get("region") or "").strip()
            pais = (endereco.get("addressCountry") or endereco.get("country") or "").strip()

    nome_evento = (obj.get("name") or obj.get("title") or "").strip()

    if not local_nome:
        local_nome = nome_evento

    partes_local = [parte for parte in [local_nome, cidade, estado or pais] if parte]
    descricao = limpar_texto_evento(" | ".join(partes_local))
    if not data_formatada and not descricao:
        return None

    texto = limpar_texto_evento(" ".join(parte for parte in [data_formatada, descricao] if parte))
    if not texto:
        return None

    return {
        "text": texto,
        "date": data_evento or extrair_data_evento(texto),
        "title": nome_evento if nome_evento and nome_evento.lower() != local_nome.lower() else "",
    }


def extrair_eventos_estruturados_soup(soup):
    eventos = []
    vistos = set()
    if soup is None:
        return eventos

    for script in soup.select('script[type="application/ld+json"]'):
        conteudo = (script.string or script.get_text() or "").strip()
        if not conteudo:
            continue
        payload = carregar_json_seguro(conteudo)
        if payload is None:
            continue

        for obj in iterar_objetos_json(payload):
            evento = extrair_evento_estruturado_obj(obj)
            if not evento:
                continue
            chave = (evento["text"], evento["date"])
            if chave in vistos:
                continue
            vistos.add(chave)
            eventos.append(evento)

    return eventos


def selecionar_eventos_estruturados(eventos):
    futuros = sorted(
        [evento for evento in eventos if evento.get("date") and evento["date"] >= date.today()],
        key=lambda item: item["date"],
    )
    passados = sorted(
        [evento for evento in eventos if evento.get("date") and evento["date"] <= date.today()],
        key=lambda item: item["date"],
        reverse=True,
    )
    proximo = futuros[0]["text"] if futuros else ""
    ultimo = passados[0]["text"] if passados else ""
    proximo_titulo = futuros[0].get("title", "") if futuros else ""
    ultimo_titulo = passados[0].get("title", "") if passados else ""
    proximo, ultimo = reconciliar_eventos(proximo, ultimo)
    return proximo, ultimo, proximo_titulo, ultimo_titulo


def extrair_secao_eventos(texto, inicio_regex, fim_regex_list):
    texto = (texto or "").replace("\r", "")
    match_inicio = re.search(inicio_regex, texto, re.IGNORECASE | re.DOTALL)
    if not match_inicio:
        return ""

    secao = texto[match_inicio.end():]
    fim_posicoes = []
    for fim_regex in fim_regex_list:
        match_fim = re.search(fim_regex, secao, re.IGNORECASE | re.DOTALL)
        if match_fim:
            fim_posicoes.append(match_fim.start())

    if fim_posicoes:
        secao = secao[:min(fim_posicoes)]

    return " ".join(secao.split()).strip()


def dividir_blocos_evento(secao):
    if not secao:
        return []

    texto = " " + secao
    partes = re.split(r"\s+(?=\d+\.\s)", texto)
    blocos = [parte.strip() for parte in partes if parte.strip()]
    if blocos:
        return blocos

    return [secao]


def extrair_cabecalho_bloco_evento(bloco):
    bloco = " ".join((bloco or "").split())
    if not bloco:
        return ""

    match = re.search(
        r"^(.*?)(?=(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|\d{1,2}-\d{1,2}|\d{1,2})\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))",
        bloco,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    return bloco


def bloco_parece_do_artista(bloco, artista):
    artista_norm = normalizar_artista(artista)
    if not artista_norm:
        return True

    bloco_norm = normalizar_artista(bloco)
    if artista_norm in bloco_norm:
        return True

    cabecalho = extrair_cabecalho_bloco_evento(bloco)
    cabecalho_norm = normalizar_artista(cabecalho)
    if artista_norm in cabecalho_norm:
        return True

    tokens = [token for token in re.split(r"[^a-z0-9]+", (artista or "").lower()) if len(token) >= 4]
    if tokens:
        hits = sum(1 for token in tokens if token in cabecalho.lower())
        if hits >= max(1, len(tokens) - 1):
            return True

    if re.search(r"\bwith\b", cabecalho, re.IGNORECASE) and artista_norm not in cabecalho_norm:
        return False

    if re.search(r"\bconcert tickets\b|\btour dates\b|\bline-up\b|\bheadliner\b", cabecalho, re.IGNORECASE):
        return False

    return not bool(cabecalho_norm)


def extrair_evento_da_secao(secao, artista="", apenas_passado=False, apenas_futuro=False):
    for bloco in dividir_blocos_evento(secao):
        if artista and not bloco_parece_do_artista(bloco, artista):
            continue
        evento = extrair_primeiro_evento_texto(bloco)
        if not evento:
            continue

        data_evento = extrair_data_evento(evento)
        if (apenas_passado or apenas_futuro) and not data_evento:
            continue
        if apenas_passado and data_evento and data_evento > date.today():
            continue
        if apenas_futuro and data_evento and data_evento < date.today():
            continue

        return evento

    return ""


def extrair_proximo_show_requests(texto, artista=""):
    texto = (texto or "").replace("\r", "")
    if (
        re.search(r"Coming up\s*0\b", texto, re.IGNORECASE)
        or re.search(r"No upcoming concerts", texto, re.IGNORECASE)
        or re.search(r"No upcoming events", texto, re.IGNORECASE)
        or re.search(r"No upcoming tour dates", texto, re.IGNORECASE)
        or re.search(r"Em breve\s*0\b", texto, re.IGNORECASE)
        or re.search(r"Próximamente\s*0\b", texto, re.IGNORECASE)
        or re.search(r"Sem shows futuros", texto, re.IGNORECASE)
    ):
        return ""
    secao = extrair_secao_eventos(
        texto,
        r"(?:Upcoming concerts\s*\(\d+\)|On tour\s+\d+\s+upcoming events|Coming up\s*\d+|Upcoming events|Tour dates\s+\d{4}|Em breve\s*\d+|Próximamente\s*\d+|Eventos futuros)",
        [
            r"Currently touring across",
            r"Their next tour date is at",
            r"See all your opportunities",
            r"Past events",
            r"Past concerts",
            r"Eventos passados",
            r"Eventos pasados",
            r"Show all past events",
            r"Touring history",
            r"Stats",
            r"Live reviews",
        ],
    )
    return extrair_evento_da_secao(secao, artista=artista, apenas_futuro=True)


def extrair_ultimo_show_requests(texto, artista=""):
    texto = (texto or "").replace("\r", "")
    secao = extrair_secao_eventos(
        texto,
        r"(?:Past events|Past concerts|Eventos passados|Eventos pasados)",
        [
            r"Show all past events",
            r"Mostrar todos os eventos passados",
            r"Mostrar todos los eventos pasados",
            r"Touring history",
            r"Stats",
            r"Live reviews",
            r"Appears most with",
        ],
    )
    evento = extrair_evento_da_secao(secao, artista=artista, apenas_passado=True)
    if evento:
        return evento

    fallback_secao = extrair_secao_eventos(
        texto,
        r"(?:Show all past events\s*\d+|Mostrar todos os eventos passados\s*\d+|Mostrar todos los eventos pasados\s*\d+)",
        [
            r"Touring history",
            r"Histórico de shows",
            r"Historial de conciertos",
            r"Stats",
            r"Estatísticas",
            r"Estadísticas",
            r"Live reviews",
            r"Appears most with",
        ],
    )
    return extrair_evento_da_secao(fallback_secao, artista=artista, apenas_passado=True)


def extrair_data_evento(texto):
    padroes = [
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b",
        r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b",
        r"\b([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})\b",
        r"\b(\d{1,2})-(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b",
        r"\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})\b",
        r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b",
        r"\b(\d{1,2})-(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b",
        r"\b(\d{4})-(\d{2})-(\d{2})\b",
    ]
    meses = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "fev": 2, "abr": 4, "ago": 8, "set": 9, "out": 10, "dez": 12,
        "ene": 1, "dic": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5,
        "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    }

    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if not match:
            continue

        grupos = match.groups()
        if len(grupos) == 3 and len(grupos[0]) == 4 and grupos[0].isdigit():
            ano_txt, mes_txt, dia_txt = grupos
        elif len(grupos) == 4 and grupos[0].isdigit() and grupos[1].isdigit():
            _, dia_txt, mes_txt, ano_txt = grupos
        elif len(grupos) == 3 and grupos[0].isdigit():
            dia_txt, mes_txt, ano_txt = grupos
        elif grupos[0].isalpha():
            mes_txt, dia_txt, ano_txt = grupos
        else:
            dia_txt, mes_txt, ano_txt = grupos

        chave_mes = mes_txt.lower()
        mes = meses.get(chave_mes) or meses.get(chave_mes[:3])
        if not mes:
            continue

        try:
            return date(int(ano_txt), mes, int(dia_txt))
        except ValueError:
            continue

    return None


def normalizar_evento_para_comparacao(texto):
    texto = limpar_texto_evento(texto).lower()
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def reconciliar_eventos(proximo_show, ultimo_show):
    proximo = (proximo_show or "").strip()
    ultimo = (ultimo_show or "").strip()

    if not proximo or not ultimo:
        return proximo, ultimo

    proximo_norm = normalizar_evento_para_comparacao(proximo)
    ultimo_norm = normalizar_evento_para_comparacao(ultimo)
    data_proximo = extrair_data_evento(proximo)
    data_ultimo = extrair_data_evento(ultimo)

    if proximo_norm and proximo_norm == ultimo_norm:
        if data_ultimo and data_ultimo <= date.today():
            return proximo, ""
        return proximo, ""

    if data_proximo and data_ultimo and data_proximo == data_ultimo:
        local_proximo = re.sub(r"^.*?\d{4}\s*", "", proximo_norm)
        local_ultimo = re.sub(r"^.*?\d{4}\s*", "", ultimo_norm)
        if local_proximo and local_proximo == local_ultimo:
            return proximo, ""

    if data_ultimo and data_ultimo > date.today():
        return proximo, ""

    return proximo, ultimo


def extrair_primeiro_evento_texto(texto):
    linhas = [linha.strip() for linha in (texto or "").splitlines() if linha.strip()]
    if not linhas:
        return ""

    linhas_filtradas = []
    for linha in linhas:
        linha_lower = linha.lower()
        if linha_lower.startswith("[{") or linha_lower.startswith('{"@context"') or "schema.org" in linha_lower:
            continue
        if linha_lower.startswith("interested"):
            continue
        linhas_filtradas.append(linha)
    linhas = linhas_filtradas
    if not linhas:
        return ""

    data_idx = -1
    for idx, linha in enumerate(linhas):
        if re.search(
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|\d{1,2}-\d{1,2})\s+.*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
            linha,
            re.IGNORECASE,
        ):
            data_idx = idx
            break

    if data_idx == -1:
        texto_unico = " ".join(linhas)
        match = re.search(
            r"((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:\s+\d{4})?|"
            r"\d{1,2}-\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s+(.*)",
            texto_unico,
            re.IGNORECASE,
        )
        return limpar_texto_evento(" ".join(match.groups())) if match else ""

    partes = [linhas[data_idx]]
    for linha in linhas[data_idx + 1:data_idx + 3]:
        linha_lower = linha.lower()
        if "rsvp" in linha_lower or linha_lower.startswith("interested") or linha_lower.startswith("tickets"):
            continue
        if linha_lower.startswith("[{") or linha_lower.startswith('{"@context"') or "schema.org" in linha_lower:
            continue
        partes.append(linha)
    texto_final = " ".join(partes)
    return limpar_texto_evento(texto_final)


def extrair_eventos_playwright(artist_url, artista=""):
    if not can_use_playwright():
        print("Playwright indisponível. Pulando coleta de eventos passados.")
        return "", ""

    with sync_playwright() as p:
        print("Playwright: iniciando navegador em segundo plano...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            print(f"Playwright: abrindo página do artista: {artist_url}")
            page.goto(artist_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

            for selector in [
                "#onetrust-accept-btn-handler",
                "button:has-text('Accept')",
                "button:has-text('I agree')",
                "button:has-text('OK')",
            ]:
                try:
                    if page.locator(selector).count() > 0:
                        print(f"Playwright: fechando popup de cookies com seletor {selector}")
                        page.locator(selector).first.click(timeout=1500)
                        page.wait_for_timeout(1000)
                        break
                except Exception:
                    pass

            possiveis_cards_coming = [
                "[role='tabpanel'] li",
                "[role='tabpanel'] article",
                "[role='tabpanel'] [class*='event']",
                "main li",
                "main article",
            ]

            proximo = ""
            print("Playwright: lendo evento visível da aba Coming up...")
            body_text = page.locator("body").inner_text(timeout=2000)
            if re.search(r"Coming up\s*0\b", body_text, re.IGNORECASE) or re.search(r"No upcoming concerts", body_text, re.IGNORECASE):
                print("Playwright: aba Coming up sem eventos futuros.")
            else:
                for seletor in possiveis_cards_coming:
                    loc = page.locator(seletor)
                    total = min(loc.count(), 8)
                    for idx in range(total):
                        texto = loc.nth(idx).inner_text(timeout=1500).strip()
                        if artista and not bloco_parece_do_artista(texto, artista):
                            continue
                        evento = extrair_primeiro_evento_texto(texto)
                        if evento:
                            proximo = evento
                            print(f"Playwright: próximo show detectado: {proximo}")
                            break
                    if proximo:
                        break

            print("Playwright: clicando na aba Past events...")
            aba = page.get_by_role("tab", name=re.compile(r"Past events|Past concerts|Eventos passados|Eventos pasados", re.I))
            if aba.count() == 0:
                aba = page.get_by_text(re.compile(r"Past events|Past concerts|Eventos passados|Eventos pasados", re.I))
            aba.first.click(timeout=5000)
            page.wait_for_timeout(2000)

            painel_passado = page.locator("[role='tabpanel']").filter(has_text=re.compile(r"RSVP|Image:|Concert Tickets", re.I))
            ultimo = ""
            possiveis_cards_past = [
                "[role='tabpanel'] li",
                "[role='tabpanel'] article",
                "[role='tabpanel'] [class*='event']",
            ]
            for seletor in possiveis_cards_past:
                loc = page.locator(seletor)
                total = min(loc.count(), 8)
                for idx in range(total):
                    texto = loc.nth(idx).inner_text(timeout=1500).strip()
                    if artista and not bloco_parece_do_artista(texto, artista):
                        continue
                    if texto.strip() == proximo.strip():
                        continue
                    evento = extrair_primeiro_evento_texto(texto)
                    data_evento = extrair_data_evento(evento) if evento else None
                    if evento and evento != proximo and data_evento and data_evento <= date.today():
                        ultimo = evento
                        print(f"Playwright: último show detectado: {ultimo}")
                        break
                if ultimo:
                    break

            if not ultimo and painel_passado.count() > 0:
                print("Playwright: tentando fallback no painel de eventos passados...")
                texto_painel = painel_passado.first.inner_text(timeout=2000).strip()
                blocos = re.split(r"\n\s*\d+\.\s*Image:", "\n" + texto_painel)
                for bloco in blocos:
                    if artista and not bloco_parece_do_artista(bloco, artista):
                        continue
                    evento = extrair_primeiro_evento_texto(bloco)
                    data_evento = extrair_data_evento(evento) if evento else None
                    if evento and evento != proximo and data_evento and data_evento <= date.today():
                        ultimo = evento
                        print(f"Playwright: último show detectado no fallback: {ultimo}")
                        break

            return proximo, ultimo
        except PlaywrightTimeoutError:
            print("Playwright: tempo esgotado durante a leitura dos eventos.")
            return "", ""
        except Exception:
            print("Playwright: erro inesperado ao coletar os eventos.")
            return "", ""
        finally:
            print("Playwright: encerrando navegador.")
            browser.close()
    return "", ""


def parse_bandsintown_event_lines(lines):
    meses = {
        "january", "jan", "february", "feb", "march", "mar", "april", "apr",
        "may", "june", "jun", "july", "jul", "august", "aug", "september", "sep",
        "october", "oct", "november", "nov", "december", "dec"
    }
    filtradas = [
        linha.strip() for linha in (lines or [])
        if linha and linha.strip() and linha.strip().lower() not in {
            "tickets", "get tickets", "get reminder", "follow", "request a show",
            "view all", "all events and livestreams", "upcoming", "past"
        }
    ]

    for idx, linha in enumerate(filtradas):
        if not extrair_data_evento(linha):
            continue
        venue = filtradas[idx + 1].strip() if idx + 1 < len(filtradas) else ""
        local = filtradas[idx + 2].strip() if idx + 2 < len(filtradas) else ""
        evento = limpar_texto_evento(" | ".join(parte for parte in [linha, venue, local] if parte))
        if extrair_data_evento(evento):
            return evento

    for idx, linha in enumerate(filtradas):
        linha_norm = linha.strip().lower()
        if linha_norm not in meses:
            continue

        dia = filtradas[idx + 1].strip() if idx + 1 < len(filtradas) else ""
        venue = filtradas[idx + 2].strip() if idx + 2 < len(filtradas) else ""
        local = filtradas[idx + 3].strip() if idx + 3 < len(filtradas) else ""

        if not dia.isdigit() or not venue:
            continue

        evento = limpar_texto_evento(f"{dia} {linha} {venue} {local}".strip())
        if extrair_data_evento(evento):
            return evento

    return ""


def buscar_bandsintown_playwright(artista):
    if not can_use_playwright():
        return {"status": "", "proximo_show": "", "ultimo_show": ""}

    sessao = criar_sessao()
    artist_url = buscar_link_artista_bandsintown(sessao, artista)
    if not artist_url:
        return {"status": "", "proximo_show": "", "ultimo_show": ""}

    proximo_seed = ""
    ultimo_seed = ""
    proximo_titulo_seed = ""
    ultimo_titulo_seed = ""
    status_seed = ""
    try:
        resposta_inicial = sessao.get(artist_url, timeout=20)
        if resposta_inicial.ok:
            soup_inicial = BeautifulSoup(resposta_inicial.text, "html.parser")
            eventos_estruturados = extrair_eventos_estruturados_soup(soup_inicial)
            proximo_json, ultimo_json, proximo_titulo_json, ultimo_titulo_json = selecionar_eventos_estruturados(eventos_estruturados)
            proximo_seed = proximo_json or ""
            ultimo_seed = ultimo_json or ""
            proximo_titulo_seed = proximo_titulo_json or ""
            ultimo_titulo_seed = ultimo_titulo_json or ""
            status_seed = "On tour" if proximo_seed else ("Off tour" if ultimo_seed else "")
    except Exception:
        pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="en-US")
        try:
            page.goto(artist_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)

            proximo = proximo_seed
            ultimo = ultimo_seed
            proximo_titulo = proximo_titulo_seed if proximo_seed else ""
            ultimo_titulo = ultimo_titulo_seed if ultimo_seed else ""

            body_text = page.locator("body").inner_text(timeout=3000)
            status = status_seed or ("On tour" if re.search(r"\b\d+\s+upcoming events\b", body_text, re.IGNORECASE) else "")

            try:
                soup_page = BeautifulSoup(page.content(), "html.parser")
                eventos_estruturados = extrair_eventos_estruturados_soup(soup_page)
                proximo_json, ultimo_json, proximo_titulo_json, ultimo_titulo_json = selecionar_eventos_estruturados(eventos_estruturados)
                proximo = proximo or proximo_json
                ultimo = ultimo or ultimo_json
                if not proximo_titulo and proximo_json:
                    proximo_titulo = proximo_titulo_json or ""
                if not ultimo_titulo and ultimo_json:
                    ultimo_titulo = ultimo_titulo_json or ""
                if not status and proximo_json:
                    status = "On tour"
                elif not status and ultimo_json:
                    status = "Off tour"
            except Exception:
                pass

            upcoming_tab = page.get_by_role("tab", name=re.compile(r"Upcoming", re.I))
            if upcoming_tab.count() > 0:
                upcoming_tab.first.click(timeout=3000)
                page.wait_for_timeout(1200)
            if not proximo:
                upcoming_text = page.locator("body").inner_text(timeout=3000)
                proximo = parse_bandsintown_event_lines(upcoming_text.splitlines())

            past_tab = page.get_by_role("tab", name=re.compile(r"Past", re.I))
            if past_tab.count() == 0:
                past_tab = page.get_by_text(re.compile(r"Past", re.I))
            if past_tab.count() > 0:
                past_tab.first.click(timeout=3000)
                page.wait_for_timeout(1400)
                if not ultimo:
                    past_text = page.locator("body").inner_text(timeout=3000)
                    ultimo = parse_bandsintown_event_lines(past_text.splitlines())

            if not status and not proximo and ultimo:
                status = "Off tour"

            proximo, ultimo = reconciliar_eventos(proximo, ultimo)
            return {
                "status": status,
                "proximo_show": proximo,
                "ultimo_show": ultimo,
                "proximo_show_titulo": proximo_titulo if proximo else "",
                "ultimo_show_titulo": ultimo_titulo if ultimo else "",
            }
        except Exception:
            return {"status": "", "proximo_show": "", "ultimo_show": "", "proximo_show_titulo": "", "ultimo_show_titulo": ""}
        finally:
            browser.close()


def buscar_songkick(artista):
    sessao = criar_sessao()
    resultado = {
        "website": "",
        "instagram": "",
        "status": "",
        "proximo_show": "",
        "ultimo_show": "",
        "proximo_show_titulo": "",
        "ultimo_show_titulo": "",
    }

    artist_url = buscar_link_artista_songkick(sessao, artista)
    if not artist_url:
        return resultado

    labs_url = converter_para_labs(artist_url)
    labs_calendar_url = converter_para_labs_calendar(artist_url)
    regular_calendar_url = converter_para_regular_calendar(artist_url)
    resposta_regular = sessao.get(artist_url, timeout=20)
    resposta_regular.raise_for_status()
    soup_regular = BeautifulSoup(resposta_regular.text, "html.parser")
    texto_regular = soup_regular.get_text("\n", strip=True)

    texto_labs = ""
    soup_labs = None
    if labs_url:
        try:
            resposta_labs = sessao.get(labs_url, timeout=20)
            resposta_labs.raise_for_status()
            soup_labs = BeautifulSoup(resposta_labs.text, "html.parser")
            texto_labs = soup_labs.get_text("\n", strip=True)
        except Exception:
            texto_labs = ""

    texto_labs_calendar = ""
    soup_labs_calendar = None
    if labs_calendar_url:
        try:
            resposta_labs_calendar = sessao.get(labs_calendar_url, timeout=20)
            resposta_labs_calendar.raise_for_status()
            soup_labs_calendar = BeautifulSoup(resposta_labs_calendar.text, "html.parser")
            texto_labs_calendar = soup_labs_calendar.get_text("\n", strip=True)
        except Exception:
            texto_labs_calendar = ""

    texto_regular_calendar = ""
    soup_regular_calendar = None
    if regular_calendar_url:
        try:
            resposta_regular_calendar = sessao.get(regular_calendar_url, timeout=20)
            resposta_regular_calendar.raise_for_status()
            soup_regular_calendar = BeautifulSoup(resposta_regular_calendar.text, "html.parser")
            texto_regular_calendar = soup_regular_calendar.get_text("\n", strip=True)
        except Exception:
            texto_regular_calendar = ""

    resultado["status"] = (
        extrair_status(texto_regular)
        or extrair_status(texto_regular_calendar)
        or extrair_status(texto_labs)
        or extrair_status(texto_labs_calendar)
    )
    eventos_estruturados = []
    for soup_base in [soup_regular, soup_labs, soup_labs_calendar, soup_regular_calendar]:
        eventos_estruturados.extend(extrair_eventos_estruturados_soup(soup_base))
    proximo_json, ultimo_json, proximo_titulo_json, ultimo_titulo_json = selecionar_eventos_estruturados(eventos_estruturados)

    proximo_pw, ultimo_pw = extrair_eventos_playwright(artist_url, artista)
    resultado["proximo_show"] = (
        proximo_json
        or proximo_pw
        or extrair_proximo_show_requests(texto_regular, artista)
        or extrair_proximo_show_requests(texto_regular_calendar, artista)
        or extrair_proximo_show_requests(texto_labs, artista)
        or extrair_proximo_show_requests(texto_labs_calendar, artista)
    )
    resultado["ultimo_show"] = (
        ultimo_json
        or ultimo_pw
        or extrair_ultimo_show_requests(texto_regular, artista)
        or extrair_ultimo_show_requests(texto_regular_calendar, artista)
        or extrair_ultimo_show_requests(texto_labs, artista)
        or extrair_ultimo_show_requests(texto_labs_calendar, artista)
    )
    resultado["proximo_show_titulo"] = proximo_titulo_json if resultado["proximo_show"] == proximo_json else ""
    resultado["ultimo_show_titulo"] = ultimo_titulo_json if resultado["ultimo_show"] == ultimo_json else ""
    if not resultado["status"] and resultado["proximo_show"]:
        resultado["status"] = "On tour"
    elif not resultado["status"] and resultado["ultimo_show"]:
        resultado["status"] = "Off tour"
    resultado["proximo_show"], resultado["ultimo_show"] = reconciliar_eventos(
        resultado["proximo_show"],
        resultado["ultimo_show"],
    )

    instagram, website = extrair_site_e_instagram(soup_regular, artista)
    if not instagram and soup_labs is not None:
        instagram, website_labs = extrair_site_e_instagram(soup_labs, artista)
        website = website or website_labs
    resultado["instagram"] = instagram
    resultado["website"] = website

    return resultado


def buscar_agenda_final(artista):
    print("\n" + "=" * 60)
    print(f"PROCESSANDO SONGKICK: {artista.upper()}")
    print("=" * 60)

    dados = carregar_dados()

    try:
        info_bandsintown = buscar_bandsintown_playwright(artista)
    except Exception as erro:
        print(f"Erro ao buscar Bandsintown: {erro}")
        info_bandsintown = {"status": "", "proximo_show": "", "ultimo_show": "", "proximo_show_titulo": "", "ultimo_show_titulo": ""}

    try:
        info = buscar_songkick(artista)
    except Exception as erro:
        print(f"Erro ao buscar Songkick: {erro}")
        info = {"website": "", "instagram": "", "status": "", "proximo_show": "", "ultimo_show": "", "proximo_show_titulo": "", "ultimo_show_titulo": ""}

    info["status"] = info_bandsintown.get("status") or info.get("status", "")

    proximo_show = info_bandsintown.get("proximo_show") or info.get("proximo_show", "")
    ultimo_show = info_bandsintown.get("ultimo_show") or info.get("ultimo_show", "")
    proximo_show_titulo = info_bandsintown.get("proximo_show_titulo") or info.get("proximo_show_titulo", "")
    ultimo_show_titulo = info_bandsintown.get("ultimo_show_titulo") or info.get("ultimo_show_titulo", "")

    hoje = date.today()
    data_proximo = extrair_data_evento(proximo_show)
    data_ultimo = extrair_data_evento(ultimo_show)

    if data_proximo and data_proximo < hoje:
        if not data_ultimo or data_proximo > data_ultimo:
            ultimo_show = proximo_show
        proximo_show = ""

    if data_ultimo and data_ultimo > hoje:
        ultimo_show = ""

    proximo_show, ultimo_show = reconciliar_eventos(proximo_show, ultimo_show)

    info["proximo_show"] = proximo_show
    info["ultimo_show"] = ultimo_show
    info["proximo_show_titulo"] = proximo_show_titulo if info["proximo_show"] else ""
    info["ultimo_show_titulo"] = ultimo_show_titulo if info["ultimo_show"] else ""

    if info["proximo_show"]:
        info["status"] = "On tour"
    elif info["ultimo_show"]:
        info["status"] = "Off tour"
    else:
        info["status"] = ""

    evento_futuro = info.get("proximo_show") or ""
    evento_passado = info.get("ultimo_show") or ""
    evento_base = evento_futuro if evento_futuro else evento_passado
    venue_query = extrair_query_local_evento(evento_base)
    venue_image_url = ""
    venue_image_urls = []
    venue_local_images = []
    sessao_venue = criar_sessao()
    try:
        venue_image_urls = buscar_imagens_venue(sessao_venue, venue_query, limit=4)
        venue_image_url = venue_image_urls[0] if venue_image_urls else ""
    except Exception:
        venue_image_url = ""
        venue_image_urls = []

    if venue_image_urls:
        try:
            venue_local_images = baixar_imagens_venue_locais(sessao_venue, venue_image_urls, limit=4)
        except Exception:
            venue_local_images = []
    else:
        limpar_imagens_venue_locais()

    dados["website"] = info["website"] or dados.get("website", "") or ""
    if info["instagram"]:
        dados["instagram"] = info["instagram"]
    dados["status"] = info["status"]
    dados["proximo_show"] = info["proximo_show"]
    dados["ultimo_show"] = info["ultimo_show"]
    dados["proximo_show_titulo"] = info.get("proximo_show_titulo", "") or ""
    dados["ultimo_show_titulo"] = info.get("ultimo_show_titulo", "") or ""
    dados["venue_image_url"] = venue_image_url or ""
    dados["venue_image_urls"] = venue_image_urls or ([] if not venue_image_url else [venue_image_url])
    dados["venue_local_images"] = venue_local_images or []

    partes_agenda = []
    if info["proximo_show"]:
        partes_agenda.append(f"Proximo: {info['proximo_show']}")
    if info["ultimo_show"]:
        partes_agenda.append(f"Ultimo: {info['ultimo_show']}")
    dados["agenda"] = " | ".join(partes_agenda)

    salvar_dados(dados)

    print(f"Site: {dados.get('website', '')}")
    print(f"Instagram: {dados.get('instagram', '')}")
    print(f"Status: {dados.get('status', '')}")
    print(f"Proximo show: {dados.get('proximo_show', '')}")
    print(f"Ultimo show: {dados.get('ultimo_show', '')}")
    print(f"Venue image: {dados.get('venue_image_url', '')}")


if __name__ == "__main__":
    nome = sys.argv[1] if len(sys.argv) > 1 else "vacations"
    buscar_agenda_final(nome)
