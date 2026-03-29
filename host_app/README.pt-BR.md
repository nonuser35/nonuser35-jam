# Host App

Idioma: Português (Brasil) | [English](README.md)

Esta pasta contém a camada de empacotamento do app Windows do host para `nonuser35-jam`.

Ela existe para que o host rode a jam a partir de um `.exe` portátil, sem precisar instalar Python na máquina final.

## O Que Está Incluído

- `launcher.py`: entrypoint do app e painel desktop do host
- `nonuser35_host.spec`: build do PyInstaller
- `setup_build_env.bat`: cria uma venv limpa só para build
- `build_host.bat`: script rápido de build
- `requirements-build.txt`: dependências de build
- `app_icon.png` / `app_icon.ico`: ícones do app

## O Que o Host App Faz

O app do host:

- sobe o backend local na porta `5000`;
- abre a jam do host no navegador quando solicitado;
- mostra um painel desktop de controle do host;
- expõe o link local do host e o link público dos convidados;
- controla o start/stop do Cloudflare Tunnel;
- mantém os arquivos de runtime dentro da estrutura do app empacotado.

## UX Atual do Host

A janela desktop funciona como painel de controle do host.

Hoje ela mostra:

- orientação do fluxo do host;
- status do servidor;
- estado da sala e dos controles;
- resumo da janela de requests do Spotify;
- estado de limite da API do Spotify;
- link local do host;
- link público dos convidados;
- QR do link público dos convidados;
- botões dedicados para:
  - abrir a jam do host;
  - abrir a jam pública;
  - copiar o link dos convidados;
  - iniciar ou encerrar o tunnel.

## Cloudflare

O backend procura automaticamente por:

- `cloudflared.exe`
- `cloudflared-windows-amd64.exe`

em:

- `projeto/`
- ou na raiz do projeto

Então, se `cloudflared-windows-amd64.exe` estiver em `projeto/`, o host app já usa esse executável.

## Fluxo de Build

Fluxo recomendado:

1. rode `host_app/setup_build_env.bat`
2. depois rode `host_app/build_host.bat`
3. o resultado final é gerado em:

```text
host_app/final/NONUSER35 JAM Host/
```

## Por Que Esse Fluxo É Usado

- usa uma venv limpa só para build;
- evita puxar dependências desnecessárias do Python principal;
- deixa o app final menor e mais previsível;
- funciona bem para um projeto com Flask, assets locais, JSON de runtime e executável externo do tunnel.

## Como a Parte do Site Funciona

Quando o host usa o app empacotado:

- o backend continua rodando localmente;
- a UI continua vivendo em `http://localhost:5000`;
- o Spotify fornece o estado da reprodução;
- a jam resolve uma faixa equivalente no YouTube / YT Music;
- letras, contexto visual e presença dos convidados continuam no mesmo site.

Os convidados:

- entram pelo navegador;
- acompanham a mesma jam;
- veem letras, contexto visual e presença na sala;
- podem ou não controlar a música, dependendo da permissão do host.

## Papel das APIs

### Spotify

Usado para:

- ler a faixa atual;
- detectar play / pause;
- detectar troca de faixa;
- acompanhar progresso;
- manter a jam alinhada ao que o host está ouvindo.

Antes de o host autorizar o Spotify, o app do Spotify Developer precisa incluir este Redirect URI:

```text
http://127.0.0.1:5000/spotify/callback
```

Sem esse callback configurado, o fluxo de autorização do Spotify no host app / jam local falha.

### YouTube Data API v3

Usado para:

- localizar a faixa que o player da jam vai tocar;
- melhorar a qualidade do matching quando a música muda.

### Cloudflare Tunnel

Usado para:

- expor a jam publicamente fora do localhost;
- deixar convidados entrarem de fora da rede local.

Ele não substitui o player. Ele só expõe a sessão local do host para convidados remotos.

## Fluxo da Primeira Vez

1. o host abre o app
2. o host inicia o fluxo da jam do host
3. o navegador abre `http://localhost:5000`
4. a tela de setup pede as APIs
5. o host cria:
   - um app no Spotify Developer Dashboard
   - um projeto no Google Cloud com YouTube Data API v3 ativada
6. nas configurações do app do Spotify, o host adiciona:

```text
http://127.0.0.1:5000/spotify/callback
```
7. o host cola as credenciais na tela
8. o mesmo fluxo continua para dentro da jam
9. quando quiser, o host gera e compartilha o link público dos convidados

## Observação

O empacotamento foi mantido em `onedir`, porque isso costuma ser mais estável para um projeto que mistura:

- backend Flask;
- site estático;
- arquivos JSON/runtime locais;
- cache;
- executável externo do tunnel.

Então a experiência final fica assim:

- você entrega uma pasta pronta;
- a pessoa não instala Python;
- a pessoa não instala bibliotecas;
- ela só abre o `.exe` dentro da pasta final.
