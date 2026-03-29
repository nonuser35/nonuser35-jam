# YT Music Sync via Tampermonkey

Arquivos:

- `yt-music-sync-host.user.js`
- `yt-music-sync-client.user.js`

Como usar:

1. Instale cada script no Tampermonkey.
2. Use o painel `YT Sync` no canto superior direito de cada aba.
3. Na aba que vai comandar, clique em `Host`.
4. Na aba que vai seguir, clique em `Client`.
5. A propria aba recarrega e assume o papel escolhido.

Observacoes importantes:

- Isso funciona apenas entre abas/janelas no mesmo navegador e no mesmo perfil, porque usa `BroadcastChannel`.
- O papel de cada aba agora e salvo em `sessionStorage`, entao host e client ficam separados por aba.
- Se no console aparecer `script desativado. role atual = client` no arquivo do host, isso significa apenas que aquela aba esta configurada como client. O painel visual passa a ser a forma mais segura de conferir.
- Se quiser sincronizar outro computador, outro navegador ou outra maquina, o proximo passo e trocar a comunicacao para WebSocket.
- O client faz ajuste fino de tempo por `playbackRate`, mas ainda pode haver pequenas variacoes dependendo do buffering do YT Music.
