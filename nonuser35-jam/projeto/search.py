import json
import random
import re
import sys
import time
import warnings

import requests
import wikipedia
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

warnings.filterwarnings("ignore")


def is_valid_public_website(url):
    href = str(url or "").strip()
    if not href.startswith("http"):
        return False

    href_lower = href.lower()
    blacklist_dominios = [
        "wikipedia.org",
        "wikidata.org",
        "instagram.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "spotify.com",
        "schema.org",
        "schemas.",
        "w3.org",
        "toolforge.org",
        "fist.php",
    ]

    if any(item in href_lower for item in blacklist_dominios):
        return False

    if len(href) > 140:
        return False

    return True


def traduzir_com_protecao(texto, artista):
    try:
        token = "[[ARTIST_NAME]]"
        texto_protegido = re.sub(re.escape(artista), token, texto, flags=re.IGNORECASE)
        time.sleep(random.uniform(0.5, 1.0))
        traducao = GoogleTranslator(source="en", target="pt").translate(texto_protegido)
        return traducao.replace(token, artista).replace(token.lower(), artista)
    except Exception:
        return texto


def limpar_e_ancorar(frase, artista):
    frase_limpa = re.sub(r"\[\d+\]", "", frase)
    frase_limpa = re.sub(r"\([^)]*\)", "", frase_limpa)
    frase_limpa = frase_limpa.strip().strip(' "[]Ã¢â‚¬Å“Ã¢â‚¬ÂÃ¢â‚¬Å¾Ã‚Â«Ã‚Â»')

    substituicoes = {
        r"^(Seu amigo|His friend|A friend)\s": f"Um colaborador de {artista}, ",
        r"^(Ele|He)\s": f"{artista} ",
        r"^(O grupo|The group|The band|A banda)\s": f"{artista} ",
        r"^(Eles|They)\s": f"Os membros de {artista} ",
        r"^(Sua|Her|His)\s": f"A trajetÃ³ria de {artista} ",
    }

    substituido = False
    for erro, correcao in substituicoes.items():
        if re.search(erro, frase_limpa, re.IGNORECASE):
            frase_limpa = re.sub(erro, correcao, frase_limpa, flags=re.IGNORECASE)
            substituido = True
            break

    if not substituido and not frase_limpa.lower().startswith(artista.lower()):
        if frase_limpa and frase_limpa[0].isdigit():
            frase_limpa = f"{artista} acumulou {frase_limpa}"
        else:
            frase_limpa = f"{artista}: {frase_limpa}"

    return frase_limpa[0].upper() + frase_limpa[1:] if frase_limpa else ""


def buscar_links_wikipedia(artista):
    links = {"instagram": "", "website": ""}

    tentativas = [
        f"https://en.wikipedia.org/wiki/{artista.replace(' ', '_')}",
        f"https://pt.wikipedia.org/wiki/{artista.replace(' ', '_')}",
    ]

    for url_wiki in tentativas:
        try:
            res = requests.get(url_wiki, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            infobox = soup.find("table", {"class": "infobox"})
            if not infobox:
                continue

            for a in infobox.find_all("a", href=True):
                href = a["href"].strip()

                if "instagram.com" in href and not links["instagram"]:
                    user = re.search(r"instagram\.com/([^/?#\s]+)", href, re.IGNORECASE)
                    if user:
                        usuario = user.group(1)
                        if usuario.lower() not in {"p", "reels", "explore", "stories", "terms", "directory"}:
                            links["instagram"] = f"@{usuario}"

                if href.startswith("//"):
                    href = "https:" + href

                if is_valid_public_website(href):
                    links["website"] = href
                    break

            if links["website"] or links["instagram"]:
                break
        except Exception:
            continue

    return links


def carregar_dados_existentes():
    try:
        with open("dados_artista.js", "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read()
        return json.loads(conteudo.replace("const dadosArtista = ", "").rstrip(";"))
    except Exception:
        return {}


def buscar_mestre(artista):
    print("\n" + "=" * 50)
    print(f"INVESTIGANDO: {artista.upper()}")
    print("=" * 50)

    wikipedia.set_lang("en")
    tentativas = [f"{artista} (band)", f"{artista} (musician)", f"{artista} (singer)", artista]

    pagina = None
    for termo in tentativas:
        try:
            print(f"Checando Wikipedia: {termo}...")
            pagina_teste = wikipedia.page(termo)
            conteudo_low = pagina_teste.content.lower()
            if any(word in conteudo_low for word in ["album", "song", "band", "music", "vocalist", "genre"]):
                pagina = pagina_teste
                break
        except Exception:
            continue

    curiosidades_pt = []
    redes = buscar_links_wikipedia(artista)

    if pagina:
        blacklist_fatos = ["born", "nascido", "founded", "formada", "nome real", "refer to", "is a city"]
        frases = re.findall(r"[^.!?]*[.!?]", pagina.content)

        print("Processando fatos e buscando curiosidades interessantes...")

        frases_prioritarias = []
        frases_normais = []
        keywords = [
            "award",
            "won",
            "first",
            "million",
            "record",
            "platinum",
            "gold",
            "known",
            "best-selling",
            "collaborate",
            "nominate",
            "billboard",
            "grammy",
            "success",
            "history",
            "debut",
        ]

        for frase in frases:
            if 60 < len(frase) < 250 and not any(item in frase.lower() for item in blacklist_fatos):
                if any(keyword in frase.lower() for keyword in keywords):
                    frases_prioritarias.append(frase)
                else:
                    frases_normais.append(frase)

        for frase in frases_prioritarias + frases_normais:
            preparada = limpar_e_ancorar(frase, artista)
            traduzida = traduzir_com_protecao(preparada, artista)
            traduzida = traduzida.replace('"', "").replace("'", "").strip()

            if traduzida and traduzida not in curiosidades_pt:
                curiosidades_pt.append(traduzida)

            if len(curiosidades_pt) >= 5:
                break

    if len(curiosidades_pt) < 2:
        print("Pouca informaÃ§Ã£o relevante. Limpando letreiro.")
        curiosidades_pt = []

    dados_existentes = carregar_dados_existentes()
    website_existente = dados_existentes.get("website", "")
    if not is_valid_public_website(website_existente):
        website_existente = ""

    dados_finais = {
        "curiosidades": curiosidades_pt,
        "instagram": dados_existentes.get("instagram") or redes["instagram"],
        "website": website_existente or redes["website"],
        "status": dados_existentes.get("status", ""),
        "agenda": dados_existentes.get("agenda", ""),
        "proximo_show": dados_existentes.get("proximo_show", ""),
        "ultimo_show": dados_existentes.get("ultimo_show", ""),
    }

    conteudo_js = f"const dadosArtista = {json.dumps(dados_finais, ensure_ascii=False)};"
    with open("dados_artista.js", "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo_js)

    print(
        f"\nFinalizado! Curiosidades: {len(curiosidades_pt)} | "
        f"Insta: {dados_finais['instagram']} | Site: {dados_finais['website']}"
    )


if __name__ == "__main__":
    nome_input = sys.argv[1] if len(sys.argv) > 1 else "New West"
    buscar_mestre(nome_input)
