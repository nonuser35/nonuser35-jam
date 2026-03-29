# Tutorial de Uso

## O Que Você Precisa Antes de Começar

Para usar a jam como host, você precisa preparar três coisas:

- um app no Spotify Developer Dashboard;
- um projeto no Google Cloud com a YouTube Data API v3 ativada;
- o `cloudflared` disponível junto do projeto, caso queira gerar link público.

Sem as credenciais de Spotify e YouTube, a jam não consegue ler a faixa do host nem localizar a música equivalente para o player web.

## Primeira Configuração do Host

1. Abra o projeto localmente ou use o host app.
2. O site vai abrir a área de configuração.
3. Entre na aba `API`.
4. Cole:
   - `Spotify Client ID`
   - `Spotify Client Secret`
   - `YouTube API Key`
5. Salve as conexões.

Depois dessa etapa inicial, as credenciais ficam salvas localmente no host e você não precisa repetir esse processo toda vez.

## Para Que Serve Cada Chave

### Spotify Client ID e Spotify Client Secret

Permitem que o projeto descubra:

- qual faixa está tocando;
- se o host pausou ou retomou;
- quando a música mudou;
- em que ponto da faixa a reprodução está.

### YouTube API Key

Permite que o projeto encontre uma versão equivalente da música para tocar no player da jam.

### Cloudflare Tunnel

Permite gerar um link público para que pessoas fora da sua rede local consigam entrar na jam.

## Fluxo Normal de Uso

1. O host abre a jam.
2. O projeto identifica a música atual do Spotify.
3. O player da jam encontra e sincroniza a faixa correspondente.
4. O host gera o link público, se quiser convidar outras pessoas.
5. Os convidados entram pelo navegador e acompanham a mesma sessão.

## Como Funciona Para os Convidados

Os convidados não precisam configurar APIs.

Eles entram pelo link da jam e podem:

- ouvir a sessão;
- ver letras e tradução;
- acompanhar o contexto visual do artista;
- aparecer com perfil, nome e foto opcional;
- controlar ou não a música, dependendo da permissão definida pelo host.

## Perfil e Persistência

O site pode salvar dados mínimos do perfil do convidado, como nome e foto opcional, para evitar que a pessoa precise preencher tudo novamente em sessões futuras.

Quando não houver foto, o projeto usa um avatar visual simples em vez de deixar o perfil vazio.

## Host App Windows

Se você quiser uma experiência mais plug and play no Windows:

1. abra o app do host;
2. espere a janela do app iniciar;
3. o navegador abrirá a jam local;
4. faça a configuração das APIs na primeira vez;
5. gere o link público quando quiser compartilhar.

## Dicas Para um Uso Melhor

- deixe a conta do Spotify do host tocando normalmente;
- prefira músicas com versão completa no YouTube ou YT Music;
- gere o link público apenas quando a jam já estiver estável;
- teste uma música antes de compartilhar com convidados.

## Problemas Comuns

### O site abriu, mas não toca nada

Normalmente isso significa que as APIs ainda não foram configuradas ou que a autorização do Spotify ainda não foi concluída.

### A música não bate exatamente com a do Spotify

O projeto tenta encontrar a melhor equivalência possível no YouTube, mas versões alternativas, vídeos curtos, snippets ou uploads diferentes podem causar incompatibilidades.

### O convidado entrou sem perfil

Isso é permitido. O perfil é opcional, mas o site pode convidar a pessoa a entrar com nome e foto depois.

