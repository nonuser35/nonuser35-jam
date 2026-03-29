import os
import sys
import time
from urllib.parse import quote_plus

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

BLACKLIST_LINKS = [
    "facebook",
    "instagram",
    "twitter",
    "fbcdn",
    "pinterest",
    "fanpop",
]

BLACKLIST_TEMAS = [
    "boys",
    "boyband",
    "kids",
    "anime",
    "meme",
]


def iniciar_driver_visivel():
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1400,1000")
    chrome_options.add_argument("user-agent=Mozilla/5.0")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)


def buscar_links_imagens(driver, artista):
    links = []
    vistos = set()
    artista_limpo = " ".join((artista or "").split())

    queries = [
        f'band "{artista_limpo}" members photo',
        f'artist "{artista_limpo}" portrait photo',
        f'band "{artista_limpo}" press photo'
    ]

    selectors = [
        "img.tile--img__img",
        ".tile img",
        "figure img",
        "img"
    ]

    for query in queries:
        url = f"https://duckduckgo.com/?q={quote_plus(query)}&iax=images&ia=images"
        print(f"Abrindo busca de imagens: {query}")
        driver.get(url)
        time.sleep(1.2)

        thumbs = []
        for selector in selectors:
            encontrados = driver.find_elements(By.CSS_SELECTOR, selector)
            if encontrados:
                thumbs = encontrados
                break

        for thumb in thumbs:
            src = (thumb.get_attribute("src") or "").strip()
            data_src = (thumb.get_attribute("data-src") or "").strip()
            alt = ((thumb.get_attribute("alt") or "") + " " + (thumb.get_attribute("title") or "")).strip().lower()
            link = data_src or src
            if not link.startswith("http"):
                continue
            link_lower = link.lower()
            if any(bloqueado in link_lower for bloqueado in BLACKLIST_LINKS):
                continue
            if any(tema in link_lower or tema in alt for tema in BLACKLIST_TEMAS):
                continue
            if "icon" in alt or "logo" in alt:
                continue
            if link in vistos:
                continue
            vistos.add(link)
            links.append(link)
            if len(links) >= 8:
                return links

        if links:
            return links[:8]

        for _ in range(2):
            driver.execute_script("window.scrollBy(0, 1200);")
            time.sleep(0.9)
            thumbs = []
            for selector in selectors:
                encontrados = driver.find_elements(By.CSS_SELECTOR, selector)
                if encontrados:
                    thumbs = encontrados
                    break
            for thumb in thumbs:
                src = (thumb.get_attribute("src") or "").strip()
                data_src = (thumb.get_attribute("data-src") or "").strip()
                alt = ((thumb.get_attribute("alt") or "") + " " + (thumb.get_attribute("title") or "")).strip().lower()
                link = data_src or src
                if not link.startswith("http"):
                    continue
                link_lower = link.lower()
                if any(bloqueado in link_lower for bloqueado in BLACKLIST_LINKS):
                    continue
                if any(tema in link_lower or tema in alt for tema in BLACKLIST_TEMAS):
                    continue
                if link in vistos:
                    continue
                vistos.add(link)
                links.append(link)
                if len(links) >= 8:
                    return links
            if links:
                return links[:8]

    return links[:8]


def baixar_fotos_inteligentes(artista):
    pasta = "img_artista"
    os.makedirs(pasta, exist_ok=True)

    for nome_existente in os.listdir(pasta):
        caminho_existente = os.path.join(pasta, nome_existente)
        if os.path.isfile(caminho_existente) and nome_existente.lower().startswith("foto"):
            try:
                os.remove(caminho_existente)
            except Exception:
                pass

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    driver = None
    try:
        driver = iniciar_driver_visivel()
        links = buscar_links_imagens(driver, artista)
    except Exception as erro:
        print(f"Erro ao abrir Selenium para imagens: {erro}")
        if driver:
            driver.quit()
        return

    fotos_salvas = 0
    hashes_vistos = set()

    for link in links:
        if fotos_salvas >= 5:
            break

        try:
            print(f"Baixando foto {fotos_salvas + 1}: {link}")
            resposta = requests.get(link, headers=headers, timeout=15)
            if resposta.status_code != 200:
                continue

            content_type = resposta.headers.get("Content-Type", "").lower()
            if not content_type.startswith("image/"):
                continue

            tamanho_kb = len(resposta.content) / 1024
            if tamanho_kb < 20:
                continue

            hash_atual = hash(resposta.content)
            if hash_atual in hashes_vistos:
                continue
            hashes_vistos.add(hash_atual)

            caminho = os.path.join(pasta, f"foto{fotos_salvas + 1}.jpg")
            with open(caminho, "wb") as arquivo:
                arquivo.write(resposta.content)

            print(f"Foto {fotos_salvas + 1} salva! ({tamanho_kb:.1f}kb)")
            fotos_salvas += 1
        except Exception:
            continue

    if driver:
        time.sleep(1)
        driver.quit()

    print(f"\nFinalizado! {fotos_salvas} fotos capturadas.")


if __name__ == "__main__":
    nome_alvo = sys.argv[1] if len(sys.argv) > 1 else "clairo"
    baixar_fotos_inteligentes(nome_alvo)
