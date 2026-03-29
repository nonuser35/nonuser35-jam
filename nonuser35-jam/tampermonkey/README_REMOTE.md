# YT Music Sync Remote

Esta versao usa:

- um script unico do Tampermonkey
- um servidor HTTP local simples
- Cloudflare Tunnel para publicar o servidor na internet

Arquivos:

- `yt-music-sync-remote.user.js`
- `yt_sync_remote_server.py`
- `start_yt_sync_remote_host.ps1`
- `start_yt_sync_remote_host.bat`
- `INICIAR_YT_SYNC_HOST.bat`
- `INICIAR_YT_SYNC_HOST_FIXO.bat`
- `INICIAR_YT_SYNC_HOST_SEM_ABRIR_NAVEGADOR.bat`
- `ABRIR_YT_SYNC_CLIENT_ATUAL.bat`
- `INICIAR_YT_SYNC_TAILSCALE_HOST.bat`
- `start_yt_sync_tailscale_host.ps1`
- `start_yt_sync_remote_server.bat`
- `start_cloudflared_yt_sync.bat`

## Fluxo

1. Na maquina host, rode o servidor local.
2. Na maquina host, publique `http://localhost:8765` com `cloudflared`.
3. Copie a URL publica do tunnel.
4. Em cada aba do YT Music, instale o script unico.
5. No painel do script, configure:
   - `Server URL`
   - `Token`
   - `Jam Toggle` se quiser permitir que o client tambem controle a reproducao
6. Na aba que controla, clique `Host`.
7. Na aba que segue, clique `Client`.

## Como iniciar no host

### Jeito automatico

Rode:

```bat
"C:\Users\Usuario\Documents\scrapping dados\tampermonkey\INICIAR_YT_SYNC_HOST.bat"
```

Ele:

- sobe o servidor
- sobe o cloudflared
- tenta capturar a URL publica
- mostra no final `Server URL`, `Token`, `URL de setup do host` e `URL de setup do client`
- abre automaticamente a URL de setup do host no navegador
- salva a configuracao atual em `.runtime/yt_sync_runtime.json`

Se preferir um nome mais tecnico, esse `.bat` so chama:

```bat
"C:\Users\Usuario\Documents\scrapping dados\tampermonkey\start_yt_sync_remote_host.bat"
```

### Jeito fixo com cloudflared nomeado

Defina no `cmd`:

```bat
set YT_SYNC_CLOUDFLARED_TUNNEL_TOKEN=SEU_TOKEN_DO_TUNNEL
set YT_SYNC_PUBLIC_URL=https://sync.seudominio.com
```

Depois rode:

```bat
"C:\Users\Usuario\Documents\scrapping dados\tampermonkey\INICIAR_YT_SYNC_HOST_FIXO.bat"
```

Nesse modo, o launcher usa `cloudflared tunnel run --token ...` e a URL publica deixa de depender do `trycloudflare`.

Se quiser escolher seu proprio token:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\Usuario\Documents\scrapping dados\tampermonkey\start_yt_sync_remote_host.ps1" -Token "token123"
```

Depois e so abrir a `URL de setup do host` no navegador. O userscript salva automaticamente:

- `Server URL`
- `Token`
- `Role = host`

Para o client, use a `URL de setup do client`.

Se preferir abrir o client com um clique depois que o host ja estiver rodando:

```bat
"C:\Users\Usuario\Documents\scrapping dados\tampermonkey\ABRIR_YT_SYNC_CLIENT_ATUAL.bat"
```

## Modo Tailscale

Se host e client estiverem na mesma tailnet, esse e o jeito mais simples e estavel.

Rode:

```bat
"C:\Users\Usuario\Documents\scrapping dados\tampermonkey\INICIAR_YT_SYNC_TAILSCALE_HOST.bat"
```

Ele:

- tenta descobrir o IP IPv4 do Tailscale
- sobe o servidor em `0.0.0.0:8765`
- gera `Server URL` no formato `http://100.x.x.x:8765`
- abre o host configurado
- salva a config atual para o client

No outro dispositivo ou aba com Tailscale conectado na mesma conta/rede, abra:

```bat
"C:\Users\Usuario\Documents\scrapping dados\tampermonkey\ABRIR_YT_SYNC_CLIENT_ATUAL.bat"
```

Referencia oficial:

- [Connect to devices](https://tailscale.com/docs/how-to/connect-to-devices)
- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)

### Jeito manual

Defina um token secreto antes de abrir o servidor:

```bat
set YT_SYNC_TOKEN=coloque-um-token-forte-aqui
```

Depois rode:

```bat
tampermonkey\start_yt_sync_remote_server.bat
```

Em outro terminal, rode:

```bat
tampermonkey\start_cloudflared_yt_sync.bat
```

O `cloudflared` vai mostrar uma URL publica `https://...trycloudflare.com`.
Essa e a URL que voce cola no botao `Server URL` do userscript.

## Endpoints

- `GET /health`
- `GET /state`
- `POST /publish`

Todos, exceto `GET /health`, exigem header:

```text
Authorization: Bearer SEU_TOKEN
```

## Observacoes

- O papel `host/client/idle` continua sendo salvo por aba em `sessionStorage`.
- A URL do servidor e o token ficam em `localStorage` para voce nao precisar reconfigurar toda hora.
- Quando `Jam control` estiver ligado, uma aba em `Client` tambem pode publicar play, pause, seek e troca de musica.
- O client usa polling de 1 segundo. E simples, estavel e funciona bem por tunnel HTTP.
- Se quiser, depois a gente pode evoluir isso para WebSocket.
