# nonuser35-jam

Projeto experimental de sincronização musical para sessões compartilhadas via navegador, com foco em estudo, prototipagem e pesquisa de UX, sync audiovisual e presença em tempo real.

## Visão Geral

O projeto acompanha a faixa tocando no Spotify do host, encontra uma versão equivalente no YouTube para o player da jam, sincroniza a reprodução para os convidados e exibe:

- letra sincronizada;
- tradução em PT-BR;
- contexto visual do artista;
- perfis dos participantes;
- convites públicos para compartilhar a sessão.

## Principais Recursos

- sincronização da faixa atual do Spotify com o player web da jam;
- troca de música com preload entre dois players do YouTube;
- letras sincronizadas com tradução em PT-BR;
- widget do artista com imagens, curiosidades e agenda;
- perfis persistentes com nome e foto opcional;
- link público via Cloudflare Tunnel;
- host app Windows portátil para abrir a jam com poucos cliques.

## Como Funciona

1. O host abre o site local ou o app do host.
2. Conecta as credenciais de Spotify e YouTube apenas na primeira configuração.
3. O projeto lê a faixa atual do Spotify.
4. O backend localiza uma versão equivalente no YouTube.
5. O player da jam sincroniza a reprodução para convidados.
6. O host pode gerar um link público e compartilhar a sessão.

## APIs e Serviços Necessários

### Spotify
Usado para identificar a faixa atual do host, progresso, play, pause e troca de música.

### YouTube Data API v3
Usado para localizar a faixa equivalente que será reproduzida no player da jam.

### Cloudflare Tunnel
Usado para criar um link público quando o host quiser compartilhar a sessão fora da rede local.

## Estrutura do Repositório

- `projeto`: backend Flask, frontend da jam e arquivos de runtime.
- `host_app`: scripts e recursos para empacotar o host app Windows.
- `docs/QUICKSTART.md`: tutorial completo de uso e configuração.
- `docs/PRIVACY_AND_USE.md`: privacidade, uso, responsabilidade e desassociação.

## Rodando Localmente

```bat
cd /d "C:\Users\Usuario\Documents\scrapping dados\projeto"
python yp2.py
