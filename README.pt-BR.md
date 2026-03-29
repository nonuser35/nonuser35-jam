# nonuser35-jam

Idioma: Português (Brasil) | [English](/C:/Users/Usuario/Documents/scrapping%20dados/README.md)

Projeto experimental de jam musical via navegador, com sync entre Spotify e player web, contexto visual do artista, letras sincronizadas, tradução em PT-BR e host app Windows portátil.

## Resumo Rápido

- o host conecta Spotify e YouTube uma vez;
- a jam acompanha a música atual do Spotify do host;
- o site resolve uma versão equivalente no YouTube / YT Music;
- convidados entram por navegador local ou link público;
- a interface mostra player, letras, tradução, contexto visual e presença na sala.

## O Que Você Encontra Aqui

- sync da faixa atual do Spotify com player web da jam;
- swaps entre players do YouTube para reduzir cortes;
- letras sincronizadas com tradução em PT-BR;
- widget do artista com imagens, curiosidades, site e agenda;
- host app Windows portátil para abrir e controlar a jam com poucos cliques.

## Uso, Privacidade e Escopo

Este projeto existe para:

- estudo;
- prototipagem;
- pesquisa de UX;
- pesquisa de sync audiovisual;
- experimentação técnica local.

Não é apresentado como:

- produto oficial;
- serviço comercial;
- solução com garantia de uptime;
- ferramenta licenciada para exploração comercial;
- software afiliado oficialmente a Spotify, YouTube ou Cloudflare.

O host é responsável por:

- suas próprias credenciais de API;
- links públicos que decidir compartilhar;
- permissões dadas aos convidados;
- ambiente local em que a jam roda.

O projeto salva dados de runtime locais, como:

- configuração;
- perfis;
- cache de vídeo;
- logs;
- imagens baixadas para contexto visual.

Esses dados ficam no ambiente local do host. Para a política completa, veja `docs/PRIVACY_AND_USE.md`.

## Aviso Sobre a API do Spotify

O projeto depende da Spotify Web API para:

- descobrir a faixa atual;
- saber play/pause;
- acompanhar progresso;
- detectar trocas de música;
- consultar a fila;
- enviar play/pause quando aplicável.

Pontos importantes:

- o Spotify trabalha com limite de requests em janela móvel de 30 segundos;
- esse limite não é exposto de forma clara como um painel de “quota restante” igual ao Google Cloud;
- em modo de desenvolvimento, esse limite tende a ser mais sensível;
- se a API entrar em rate limit, o projeto pode temporariamente demorar mais para atualizar a faixa, o estado do player ou a fila.

Quando isso acontece:

- o bloqueio costuma ser temporário;
- pode durar alguns minutos ou algumas horas, dependendo do `Retry-After` retornado;
- isso não afeta o uso normal do aplicativo oficial do Spotify;
- o impacto fica concentrado no app/site da jam, que depende dessas leituras da API.

Hoje o projeto já tenta reduzir esse risco com:

- polling mais econômico;
- bursts curtos só em momentos críticos;
- projeção local do progresso da faixa;
- cache local de vídeo;
- backoff automático quando a API limita requests.

## Como Testar Rápido

### Site local

```bat
cd /d "C:\Users\Usuario\Documents\scrapping dados\projeto"
python yp2.py
```

Depois abra:

```text
http://localhost:5000
```

### Host app Windows

1. rode `host_app/setup_build_env.bat`
2. depois rode `host_app/build_host.bat`
3. use a pasta final em `host_app/final/NONUSER35 JAM Host`

## Visão Geral

O projeto acompanha a faixa tocando no Spotify do host, encontra uma versão equivalente no YouTube para o player da jam e sincroniza a reprodução para convidados.

Além do player, a interface também pode exibir:

- letra sincronizada;
- tradução em PT-BR;
- contexto visual do artista;
- curiosidades;
- site oficial;
- agenda;
- perfis dos participantes;
- link público para compartilhar a sessão.

## Como o App Funciona

Fluxo geral:

1. o host abre o site local ou o host app Windows;
2. conecta Spotify e YouTube na primeira configuração;
3. o backend local lê a faixa atual do Spotify;
4. o sistema resolve uma versão equivalente no YouTube / YT Music;
5. o player web da jam assume essa faixa;
6. o site sincroniza tempo, play/pause e trocas;
7. o host pode gerar um link público para convidados.

Na prática, o projeto é dividido assim:

- `Spotify`: diz o que está tocando agora e qual o estado da reprodução;
- `backend local`: decide o estado da jam, resolve vídeos, mantém cache e expõe as rotas locais;
- `frontend web`: toca a faixa, faz swaps de player, mostra letras, tradução e contexto visual;
- `Cloudflare Tunnel`: opcional, só para compartilhar a jam fora do localhost;
- `host app`: empacota a experiência do host num `.exe` portátil.

## Lógica de Sync

O sync da jam não depende só de “dar play num vídeo”.

Hoje ele trabalha com:

- leitura da faixa atual do Spotify;
- comparação de `track_id` para detectar mudança real;
- resolução do `videoId` da nova faixa;
- swap entre dois players do YouTube para reduzir cortes;
- correção de drift;
- pré-cache da próxima faixa quando possível;
- bursts curtos de polling em momentos críticos.

Na maior parte do tempo:

- o site roda de forma mais livre;
- o backend confirma o estado do Spotify em intervalos controlados;
- a correção fica mais forte quando há troca de faixa, sync inicial, play/pause ou handoff.

Isso existe para equilibrar:

- responsividade;
- estabilidade;
- e consumo da Spotify API.

## Troca de Música

O projeto trata dois cenários principais:

### 1. Troca natural

Quando a música termina e a próxima entra normalmente:

- a fila ajuda a preparar a próxima faixa;
- o player inativo pode ser pré-carregado;
- a transição tende a ser mais suave.

### 2. Troca manual fora da fila

Quando o host clica em outra música direto no Spotify:

- o backend detecta a mudança pela faixa atual, não pela fila;
- tenta resolver o vídeo da nova faixa imediatamente;
- abre uma janela curta de polling mais rápido;
- o frontend segura um pequeno intervalo antes de matar o player antigo, para evitar silêncio seco ou repeat estranho.

Esse é o cenário mais difícil e onde o projeto mais depende de:

- cache local;
- resolução rápida do vídeo;
- e boa resposta da API do Spotify.

## Letras e Tradução

O sistema de letras tenta:

- buscar letra sincronizada;
- mostrar a linha atual no tempo certo;
- permitir tradução em PT-BR;
- antecipar o começo da tradução para não perder o início da música.

A tradução pode entrar em etapas:

- primeiro um começo útil;
- depois o restante;
- e por fim a letra completa.

## Contexto Visual do Artista

O widget do artista pode reunir:

- fotos do artista;
- curiosidades;
- site;
- status;
- próximo show;
- último show;
- fundo contextual com imagens do local do show.

Esses dados são coletados e cacheados localmente para o site ficar mais estável durante o uso.

## APIs e Serviços Necessários

### Spotify

Usado para:

- identificar a faixa atual;
- ler play/pause;
- ler progresso;
- detectar troca de música;
- consultar fila;
- enviar comandos quando o host usa os controles.

### YouTube Data API v3

Usado para localizar a faixa equivalente que será reproduzida no player da jam.

### Cloudflare Tunnel

Usado para criar um link público quando o host quiser compartilhar a sessão fora da rede local.

## Estrutura do Repositório

- `projeto`: backend Flask, frontend da jam e arquivos de runtime.
- `host_app`: build, launcher, ícones e empacotamento do app Windows.
- `docs/QUICKSTART.md`: tutorial de uso e configuração.
- `docs/PRIVACY_AND_USE.md`: privacidade, escopo, responsabilidade e uso.

## Requisitos Para Desenvolvimento

- Python 3.11
- conta Spotify Developer com app criado
- projeto Google Cloud com YouTube Data API v3 ativada
- `cloudflared` disponível para links públicos

## Estrutura Técnica da Jam

### Backend local

- roda em Flask;
- consulta Spotify;
- resolve vídeos;
- mantém cache e estado da sessão;
- entrega rotas locais para frontend e host app.

### Frontend web

- toca a faixa da jam;
- gerencia sync, swaps e drift;
- mostra letras, tradução e widget do artista;
- roda tanto no navegador normal quanto dentro do host app.

### Host app

- sobe o backend local;
- abre a jam;
- mostra status da sala, link público e janela de requests recentes;
- organiza a experiência do host em um `.exe` portátil.

## Limitações Técnicas Naturais

Mesmo com o app estável, ainda existem limites naturais do projeto:

- diferenças de catálogo entre Spotify e YouTube;
- versões ao vivo, remaster, lyric video ou upload alternativo;
- delays pontuais na resolução de vídeo;
- limites temporários da Spotify API;
- variações de tempo entre plataformas;
- comportamento de autoplay do navegador, especialmente após fluxos de autenticação.

Essas limitações não significam necessariamente bug crítico; muitas vêm das próprias plataformas envolvidas.
