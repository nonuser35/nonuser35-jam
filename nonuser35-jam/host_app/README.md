# Host App

PT/EN:
- o app final do host agora tem alternancia de idioma na propria janela
- o pacote final tambem gera `LEIA-ME PRIMEIRO.txt` e `README FIRST.txt`

Esta pasta prepara o projeto para virar um app Windows do host, sem exigir Python instalado no PC final.

## O que ja foi preparado

- `launcher.py`: entrypoint do app empacotado.
- `nonuser35_host.spec`: build do PyInstaller.
- `setup_build_env.bat`: cria uma venv limpa so para o build.
- `build_host.bat`: script rapido para gerar a versao do host.
- `requirements-build.txt`: dependencias minimas da venv de build.

## Cloudflare

O backend agora procura automaticamente por:

- `cloudflared.exe`
- `cloudflared-windows-amd64.exe`

na pasta:

- [projeto](/C:/Users/Usuario/Documents/scrapping%20dados/projeto)
- ou na raiz do projeto

Entao o arquivo que voce colocou em [projeto/cloudflared-windows-amd64.exe](/C:/Users/Usuario/Documents/scrapping%20dados/projeto/cloudflared-windows-amd64.exe) ja entra na logica do app.

## Como gerar o app

### Fluxo recomendado

1. Rode [host_app/setup_build_env.bat](/C:/Users/Usuario/Documents/scrapping%20dados/host_app/setup_build_env.bat)
2. Depois rode [host_app/build_host.bat](/C:/Users/Usuario/Documents/scrapping%20dados/host_app/build_host.bat)
3. O resultado final sai em:

- `host_app/final/nonuser35-jam-host/`

### Por que isso e melhor

- usa uma venv limpa so para o empacotamento
- evita puxar bibliotecas gigantes e desnecessarias do seu Python principal
- deixa o app final menor, mais estavel e mais previsivel

## Como o app funciona

- a pessoa extrai a pasta pronta
- abre `nonuser35-jam-host.exe`
- o app sobe o backend local na porta `5000`
- abre uma janelinha simples do host, que pode ficar minimizada
- essa janela mostra:
  - status do servidor
  - pessoas na jam
  - estado dos controles
  - status do tunnel
  - link atual
- abre o navegador em `http://localhost:5000`
- usa o `cloudflared` embutido quando o host pedir o link publico
- ao fechar a janela do host, a jam e o `cloudflared` tambem encerram

## Como o site funciona

O site do host existe para transformar a sessao local em uma sala compartilhavel.

Na pratica:

- o host conecta as proprias APIs uma vez
- o player acompanha a musica que esta tocando no Spotify do host
- o site procura uma versao equivalente no YouTube para reproduzir no player da jam
- a letra, o contexto visual do artista e os perfis dos participantes aparecem juntos na mesma interface
- quando o host quiser, ele gera um link publico e envia para os convidados

Os convidados:

- entram pelo navegador
- acompanham a mesma jam
- veem letra, infos e perfis
- e podem ou nao controlar a musica, dependendo da permissao do host

## Para que servem as APIs

### Spotify

As credenciais do Spotify servem para o host:

- ler a musica atual
- saber quando a faixa mudou
- acompanhar tempo, play, pause, proxima e anterior
- manter a jam sincronizada com o que o host esta ouvindo

Sem Spotify, o site nao sabe qual musica esta rodando no host.

### YouTube Data API v3

A chave do YouTube serve para:

- encontrar a faixa correspondente para tocar no player da jam
- buscar um resultado melhor quando o Spotify muda de musica
- ajudar o site a usar uma versao mais parecida com a musica real do host

Sem essa chave, o player da jam nao consegue localizar bem a musica para reproduzir.

### Cloudflare Tunnel

O Cloudflare Tunnel serve para:

- criar um link publico para quem esta fora da rede local
- deixar convidados entrarem na jam pela internet

Ele nao substitui o player. Ele so faz a ponte entre:

- o PC do host
- e os convidados externos

## Fluxo da primeira vez

1. O host abre o app.
2. O navegador abre em `http://localhost:5000`.
3. A tela de configuracao aparece pedindo as APIs.
4. Antes de colar qualquer chave, o host precisa criar:

- um app no Spotify Developer Dashboard
- um projeto no Google Cloud com a `YouTube Data API v3` ativada

5. Depois disso, o host copia as credenciais e cola na tela.
6. A mesma guia continua viva e a jam passa a funcionar ali.
7. Quando quiser compartilhar, o host gera o link publico.

## Observacao

Esta base foi preparada em modo `onedir`, que costuma ser mais estavel para um projeto com:

- backend Flask
- site estatico
- assets locais
- cache/JSON
- executavel externo do Cloudflare

Entao a experiencia final fica assim:

- voce entrega uma pasta pronta
- a pessoa nao instala Python
- a pessoa nao instala bibliotecas
- ela so abre o `.exe` que esta dentro dessa pasta
- a pasta temporaria de build pode ser apagada automaticamente apos a geracao
