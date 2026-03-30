import * as Lyrics from './lyrics.js';
import * as Player from './player.js';

let currentVideoId = "";
let pendingVideoId = "";
let activeSwapVideoId = "";
let isWaitingForSync = false;
let currentTrackKey = "";
let latestServerTrackKey = "";
let audioUnlocked = false;
let isSetupMode = false;
let preCachedVideoId = "";
let isSwapping = false;
let pauseDetectionCount = 0;
let driftCorrectionTimer = null;
let syncAssistUntil = 0;
let localPausePendingUntil = 0;
let setupSyncRetryUntil = 0;
let lastHardSeekAt = 0;
let lastArtistContextArtist = "";
let lastArtistContextTs = 0;
let mountedArtistWidgetArtist = "";
let lyricsFeedbackTimeout = null;
let statusPollTimer = null;
let statusRequestInFlight = false;
let profileBurstClientId = '';
let profileBurstUntil = 0;
let lastRenderedProfileMap = new Map();
let leavingProfiles = [];
let queueRotateTimer = null;
let currentQueueItems = [];
let currentQueueIndex = 0;
let latestJamPresenceCount = 0;
let unresolvedTrackGraceKey = "";
let unresolvedTrackGraceUntil = 0;
const DRIFT_IGNORE_ZONE = 0.35;
const DRIFT_RATE_SOFT_LIMIT = 1.15;
const DRIFT_RATE_HARD_LIMIT = 2.4;
const DRIFT_EMERGENCY_SEEK = 5;
const SYNC_COMPENSATION_DELAY = 0.75;
let latestSpotifyTime = 0;
let latestSpotifyDuration = 0;
let latestSpotifyIsPlaying = false;
let latestSpotifyStatusAt = 0;
let lastAudibleVolume = 80;
let hydrationDebugLogged = false;
let hydrationSyncBurstRemaining = 0;
const PROFILE_NAME_KEY = 'nonuser35-profile-name';
const PROFILE_PHOTO_KEY = 'nonuser35-profile-photo';
const PROFILE_CLIENT_ID_KEY = 'nonuser35-profile-client-id';
const PROFILE_GUEST_TOKEN_KEY = 'nonuser35-profile-guest-token';
const PROFILE_RECOVERY_CODE_KEY = 'nonuser35-profile-recovery-code';
const THEME_MODE_KEY = 'nonuser35-theme-mode';
const PRIVACY_BANNER_ACCEPTED_KEY = 'nonuser35-privacy-banner-accepted';
const SETUP_LANGUAGE_KEY = 'nonuser35-setup-language';
const SAMPLE_AVATAR_1 = "data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 120'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop stop-color='%2325ff72'/%3E%3Cstop offset='1' stop-color='%2300b7ff'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='120' height='120' rx='30' fill='url(%23g)'/%3E%3Ccircle cx='60' cy='46' r='22' fill='rgba(255,255,255,0.88)'/%3E%3Cpath d='M26 100c7-18 22-28 34-28s27 10 34 28' fill='rgba(7,21,13,0.28)'/%3E%3C/svg%3E";
const SAMPLE_AVATAR_2 = "data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 120'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop stop-color='%23ff9f43'/%3E%3Cstop offset='1' stop-color='%23ff4d94'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='120' height='120' rx='30' fill='url(%23g)'/%3E%3Ccircle cx='60' cy='43' r='20' fill='rgba(255,255,255,0.9)'/%3E%3Cpath d='M24 101c8-20 22-31 36-31s28 11 36 31' fill='rgba(18,10,14,0.3)'/%3E%3C/svg%3E";
const SAMPLE_AVATAR_3 = "data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 120'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop stop-color='%238e7dff'/%3E%3Cstop offset='1' stop-color='%2342f5d7'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='120' height='120' rx='30' fill='url(%23g)'/%3E%3Ccircle cx='60' cy='44' r='21' fill='rgba(255,255,255,0.9)'/%3E%3Cpath d='M22 101c9-19 23-30 38-30s29 11 38 30' fill='rgba(10,14,22,0.28)'/%3E%3C/svg%3E";
const SAMPLE_JAM_PROFILES = [
    { client_id: 'sample-1', name: 'Luna Costa', avatar: SAMPLE_AVATAR_1 },
    { client_id: 'sample-2', name: 'Theo Vale', avatar: SAMPLE_AVATAR_2 },
    { client_id: 'sample-3', name: 'Maya Bloom', avatar: SAMPLE_AVATAR_3 }
];
const MAX_VISIBLE_PROFILES = 6;
const PAGE_PARAMS = new URLSearchParams(window.location.search);
const HOST_ACCESS_TOKEN = (PAGE_PARAMS.get('host') || '').trim();
const SPOTIFY_AUTH_STATE = (PAGE_PARAMS.get('spotify_auth') || '').trim();
const sessionState = {
    isHost: false,
    canControl: false,
    allowGuestControls: false,
    setupRequired: false,
    hasApiCredentials: false,
    hostToken: "",
    publicBaseUrl: "",
    isLocalRequest: false,
    tunnelStatus: "idle",
    tunnelActive: false
};
let tunnelAutoStartAttempted = false;
let jamInviteToastTimer = null;
let jamInviteToastVisible = false;
let setupApiLockActive = false;
const setupTranslations = {
    pt: {
        header: {
            eyebrow: 'Configurações',
            title: 'Perfil local e conexões',
            desc: 'Personalize o player, ajuste a sala e conecte as APIs sem sair desta tela.'
        },
        nav: [
            { small: 'Local', strong: 'Perfil' },
            { small: 'Visual', strong: 'Temas' },
            { small: 'Conexão', strong: 'API' },
            { small: 'Sala', strong: 'Convites' },
            { small: 'Projeto', strong: 'Privacidade' }
        ],
        profile: {
            titleSmall: 'Perfil do usuário',
            titleStrong: 'Nome e foto locais',
            onboardingSmall: 'Antes de entrar na jam',
            onboardingStrong: 'Escolha como você aparece',
            onboardingP1: 'No primeiro acesso, a jam pede um nome para <u>mostrar sua presença</u> na sala e sincronizar você com o host e com os outros convidados.',
            onboardingP2: 'A foto é opcional. Se você não enviar nenhuma, o site cria um <u>avatar automático</u> com iniciais para não deixar seu perfil vazio.',
            guideSmall: 'Como a jam funciona',
            guideStrong: 'Entenda o fluxo antes de compartilhar',
            guideP1: 'O host roda o projeto localmente com as próprias credenciais, gera um link público e compartilha esse acesso com quem quiser entrar na sala. Os convidados abrem a interface da jam no navegador, acompanham a música, veem a letra, o contexto visual e a presença dos outros usuários, enquanto a reprodução principal e a lógica central continuam ligadas ao ambiente do host.',
            guideP2: 'Em outras palavras, esta área explica <u>como usar</u> o projeto; a aba de privacidade explica <u>os limites, responsabilidades e condições de uso</u>.',
            nameLabel: 'Nome exibido',
            namePlaceholder: 'Ex.: nonuser35, Lucas...',
            nameHelp: 'Fica salvo <u>somente neste navegador</u>.',
            photoLabel: 'Foto local',
            photoHelp: 'Escolha uma imagem do seu computador para usar como avatar local.',
            saveProfile: 'Salvar perfil',
            guestSmall: 'Permissões da jam',
            guestStrong: 'Controle dos convidados',
            guestLabel: 'Liberar controles para convidados',
            guestStatusOn: 'Convidados podem usar play, pause, próxima e anterior.',
            guestStatusOff: 'Somente o host pode controlar a música.',
            saveGuest: 'Salvar permissões'
        },
        invites: {
            linksSmall: 'Acesso externo',
            linksStrong: 'Gerar e compartilhar a jam',
            shareGuides: [
                {
                    b: 'Como usar',
                    p: '1. Gere o link público. 2. Copie o link dos convidados. 3. Envie para quem vai entrar na jam.'
                },
                {
                    b: 'Quando usar o link do host',
                    p: 'Use apenas se você mesmo precisar abrir a jam fora do localhost mantendo permissão de host.'
                }
            ],
            baseLabel: 'Link base da jam',
            baseHelp: 'Normalmente ele aparece sozinho. Cole manualmente <u>só se</u> o tunnel automático falhar.',
            generateLink: 'Gerar link',
            stopLink: 'Encerrar',
            saveUrl: 'Salvar URL',
            viewerLabel: 'Link para convidados',
            viewerHelp: 'Este é o link normal da sala para enviar aos amigos.',
            copyViewer: 'Copiar link da sala',
            qrCaption: 'QR Code para abrir a sala',
            hostLabel: 'Link privado do host',
            hostHelp: 'Guarde este link para você. Ele preserva seu acesso administrativo fora do localhost.',
            copyHost: 'Copiar link do host'
        },
        api: {
            titleSmall: 'APIs do player',
            titleStrong: 'Spotify e YouTube Data API v3',
            tutorialEyebrow: 'INFO / TUTORIAL',
            tutorialTitle: 'Este é o passo inicial mais importante para usar a jam.',
            tutorialBody: 'Crie o app no Spotify e o projeto no Google Cloud antes de buscar as chaves. Essas credenciais <u>não aparecem prontas</u>: primeiro você cria o app e o projeto nas plataformas e só depois copia os dados para esta tela.',
            tutorialFooter: 'Muito importante: no app do Spotify, cadastre o <u>Redirect URI / callback</u> exatamente como <strong>http://127.0.0.1:5000/spotify/callback</strong>. Sem isso, a autorização do Spotify falha. Normalmente, você faz isso uma única vez.',
            guides: [
                {
                    b: 'Spotify Client ID',
                    p: 'No <strong>Spotify Developer Dashboard</strong>, crie um app e copie o campo <strong>Client ID</strong>.'
                },
                {
                    b: 'Spotify Client Secret',
                    p: 'No mesmo app, clique em <strong>View client secret</strong> para revelar a chave secreta.'
                },
                {
                    b: 'Spotify Redirect URI / Callback',
                    p: 'No mesmo app do Spotify, em <strong>Edit settings</strong>, adicione exatamente <strong>http://127.0.0.1:5000/spotify/callback</strong> em Redirect URIs.'
                },
                {
                    b: 'YouTube Data API v3 Key',
                    p: 'No Google Cloud, ative <strong>YouTube Data API v3</strong> e depois crie uma API key em credenciais.'
                }
            ],
            links: [
                'Abrir Spotify Developer Dashboard',
                'Ativar YouTube Data API v3',
                'Abrir credenciais do Google Cloud'
            ],
            clientIdLabel: 'Spotify Client ID',
            clientIdPlaceholder: 'Cole o Client ID do Spotify',
            clientIdHelp: 'Procure exatamente pelo campo chamado <u>Client ID</u>.',
            clientSecretLabel: 'Spotify Client Secret',
            clientSecretPlaceholder: 'Cole o Client Secret do Spotify',
            clientSecretHelp: 'Use o botão <u>View client secret</u> no painel do app. E confirme também o callback: <strong>http://127.0.0.1:5000/spotify/callback</strong>.',
            ytLabel: 'YouTube Data API v3 Key',
            ytPlaceholder: 'Cole a chave da YouTube Data API v3',
            ytHelp: 'Ative a API antes de gerar a chave.',
            saveHint: 'Depois que as chaves estiverem salvas, basta gerar o link público da jam e enviar para seus amigos. Eles vão ouvir a mesma faixa que você estiver ouvindo no host.',
            save: 'Salvar conexões'
        },
        themes: {
            titleSmall: 'Temas do site',
            titleStrong: 'Escolha a atmosfera da jam',
            guides: [
                {
                    b: 'Fundo por capa do álbum',
                    p: 'Usa automaticamente a capa atual da música como base visual do site.'
                },
                {
                    b: 'Gradiente dinâmico',
                    p: 'Transforma a faixa atual em um fundo mais abstrato, leve e menos literal.'
                }
            ],
            cards: [
                {
                    strong: 'Álbum em tela cheia',
                    span: 'Modo mais imersivo, conectado diretamente à faixa que está tocando.'
                },
                {
                    strong: 'Gradiente dinâmico',
                    span: 'Visual mais minimalista, usando as cores principais da música.'
                }
            ],
            save: 'Salvar tema visual'
        },
        privacy: {
            titleSmall: 'Privacidade e política de uso',
            titleStrong: 'Transparência, pesquisa e responsabilidade',
            guides: [
                {
                    b: 'Natureza do projeto',
                    p: 'Este player foi desenvolvido como um projeto experimental de pesquisa, estudo e exploração técnica. A proposta aqui é observar fluxos de sincronização, interface, integração e experiência de uso em um contexto estritamente educacional, sem finalidade comercial, promessa de prestação de serviço ou compromisso de continuidade operacional.'
                },
                {
                    b: 'Dados e privacidade',
                    p: 'Para entrar na sala, o navegador pode armazenar localmente informações básicas como nome, foto opcional e um identificador de sessão. Esses dados existem apenas para apresentar a presença de cada participante, organizar a experiência visual da jam e manter a sincronização entre convidados e host. O envio de foto não é obrigatório e, quando nenhuma imagem é fornecida, o sistema utiliza um avatar automático com iniciais.'
                },
                {
                    b: 'Credenciais, acesso e responsabilidade',
                    p: 'As credenciais de Spotify, YouTube e demais integrações pertencem exclusivamente ao host da jam e permanecem sob sua responsabilidade. O compartilhamento de links, a abertura da sala para convidados e a administração das permissões são decisões tomadas pelo próprio host, que assume integralmente o uso das credenciais, dos acessos concedidos e da forma como o projeto é empregado durante os testes.'
                },
                {
                    b: 'Limites, desassociação e isenção',
                    p: 'Este projeto é disponibilizado <i>as is</i>, sem garantia expressa ou implícita de disponibilidade contínua, compatibilidade permanente, estabilidade pública ou adequação a qualquer objetivo específico. Não há vinculação oficial, afiliação, patrocínio, homologação ou endosso por Spotify, YouTube, Bandsintown, Songkick ou por qualquer outra plataforma mencionada. Todas as marcas, serviços e referências pertencem aos respectivos titulares, e o uso desta experiência ocorre por conta e risco de quem a hospeda ou acessa, inclusive diante de falhas, limitações, alterações de terceiros, quotas, indisponibilidades ou bloqueios externos.'
                }
            ]
        },
        banner: {
            small: 'Privacidade e política de uso',
            strong: 'Esta jam é um projeto de estudo',
            p: 'Para entrar na sala, o navegador pode salvar localmente seu nome, foto opcional e um identificador de sessão. O projeto é experimental, voltado a pesquisa e estudos, sem finalidade comercial e com uso por conta e risco de quem participa.',
            details: 'Ver política',
            accept: 'Concordar e entrar'
        },
        tunnel: {
            active: 'Link público pronto: {url}',
            activeWaiting: 'Link público ativo. Aguardando URL final...',
            starting: 'Gerando link público automaticamente...',
            error: 'Não deu para gerar sozinho. Se precisar, cole a URL pública manualmente.',
            idleLocal: 'Ainda sem link público. Clique em gerar link para abrir a sala para convidados.',
            idleRemote: 'Nenhum link público ativo.'
        },
        lockTitle: 'Somente o host pode controlar a jam'
    },
    en: {
        header: {
            eyebrow: 'Settings',
            title: 'Local profile and connections',
            desc: 'Personalize the player, tune the room, and connect the APIs without leaving this screen.'
        },
        nav: [
            { small: 'Local', strong: 'Profile' },
            { small: 'Visual', strong: 'Themes' },
            { small: 'Connection', strong: 'API' },
            { small: 'Room', strong: 'Invites' },
            { small: 'Project', strong: 'Privacy' }
        ],
        profile: {
            titleSmall: 'User profile',
            titleStrong: 'Local name and photo',
            onboardingSmall: 'Before joining the jam',
            onboardingStrong: 'Choose how you appear',
            onboardingP1: 'On first access, the jam asks for a name to <u>show your presence</u> in the room and sync you with the host and other guests.',
            onboardingP2: 'The photo is optional. If you do not upload one, the site creates an <u>automatic avatar</u> with initials so your profile never looks empty.',
            guideSmall: 'How the jam works',
            guideStrong: 'Understand the flow before sharing',
            guideP1: 'The host runs the project locally with their own credentials, generates a public link, and shares that access with anyone invited to the room. Guests open the jam interface in the browser, follow the music, see the lyrics, visual context, and presence of other users, while the main playback and core logic remain tied to the host environment.',
            guideP2: 'In short, this area explains <u>how to use</u> the project; the privacy tab explains <u>its limits, responsibilities, and usage conditions</u>.',
            nameLabel: 'Display name',
            namePlaceholder: 'Example: nonuser35, Lucas...',
            nameHelp: 'Saved <u>only in this browser</u>.',
            photoLabel: 'Local photo',
            photoHelp: 'Choose an image from your computer to use as your local avatar.',
            saveProfile: 'Save profile',
            guestSmall: 'Jam permissions',
            guestStrong: 'Guest controls',
            guestLabel: 'Allow guest controls',
            guestStatusOn: 'Guests can use play, pause, next, and previous.',
            guestStatusOff: 'Only the host can control playback.',
            saveGuest: 'Save permissions'
        },
        invites: {
            linksSmall: 'External access',
            linksStrong: 'Generate and share the jam',
            shareGuides: [
                {
                    b: 'How to use it',
                    p: '1. Generate the public link. 2. Copy the guest link. 3. Send it to whoever should join the jam.'
                },
                {
                    b: 'When to use the host link',
                    p: 'Use it only if you need to open the jam yourself outside localhost while keeping host permissions.'
                }
            ],
            baseLabel: 'Jam base link',
            baseHelp: 'It usually appears automatically. Paste it manually <u>only if</u> the automatic tunnel fails.',
            generateLink: 'Generate link',
            stopLink: 'Stop',
            saveUrl: 'Save URL',
            viewerLabel: 'Guest link',
            viewerHelp: 'This is the normal room link you send to your friends.',
            copyViewer: 'Copy room link',
            qrCaption: 'QR code to open the room',
            hostLabel: 'Private host link',
            hostHelp: 'Keep this link for yourself. It preserves administrative access outside localhost.',
            copyHost: 'Copy host link'
        },
        api: {
            titleSmall: 'Player APIs',
            titleStrong: 'Spotify and YouTube Data API v3',
            tutorialEyebrow: 'INFO / TUTORIAL',
            tutorialTitle: 'This is the most important first step to use the jam',
            tutorialBody: 'Create the Spotify app and the Google Cloud project before looking for the keys. Those credentials do <u>not appear ready-made</u>: first you create the app/project on each platform, then you copy the values into this screen.',
            tutorialFooter: 'Very important: in the Spotify app settings, register the <u>Redirect URI / callback</u> exactly as <strong>http://127.0.0.1:5000/spotify/callback</strong>. Without this, Spotify authorization will fail. In most cases you only do this once.',
            guides: [
                {
                    b: 'Spotify Client ID',
                    p: 'In the <strong>Spotify Developer Dashboard</strong>, create an app and copy the <strong>Client ID</strong> field.'
                },
                {
                    b: 'Spotify Client Secret',
                    p: 'In the same app, click <strong>View client secret</strong> to reveal the secret key.'
                },
                {
                    b: 'Spotify Redirect URI / Callback',
                    p: 'In the same Spotify app, open <strong>Edit settings</strong> and add exactly <strong>http://127.0.0.1:5000/spotify/callback</strong> under Redirect URIs.'
                },
                {
                    b: 'YouTube Data API v3 Key',
                    p: 'In Google Cloud, enable <strong>YouTube Data API v3</strong> and then create an API key in credentials.'
                }
            ],
            links: [
                'Open Spotify Developer Dashboard',
                'Enable YouTube Data API v3',
                'Open Google Cloud credentials'
            ],
            clientIdLabel: 'Spotify Client ID',
            clientIdPlaceholder: 'Paste the Spotify Client ID',
            clientIdHelp: 'Look for the field named <u>Client ID</u>.',
            clientSecretLabel: 'Spotify Client Secret',
            clientSecretPlaceholder: 'Paste the Spotify Client Secret',
            clientSecretHelp: 'Use the <u>View client secret</u> button in the app dashboard. Also confirm the callback: <strong>http://127.0.0.1:5000/spotify/callback</strong>.',
            ytLabel: 'YouTube Data API v3 Key',
            ytPlaceholder: 'Paste the YouTube Data API v3 key',
            ytHelp: 'Enable the API before generating the key.',
            saveHint: 'Once the keys are saved, just generate the public jam link and send it to your friends. They will hear the same track you are hearing on the host.',
            save: 'Save connections'
        },
        themes: {
            titleSmall: 'Site themes',
            titleStrong: 'Choose the jam atmosphere',
            guides: [
                {
                    b: 'Album-cover background',
                    p: 'Automatically uses the current track cover as the visual base of the site.'
                },
                {
                    b: 'Dynamic gradient',
                    p: 'Turns the current track into a more abstract, lighter, and less literal background.'
                }
            ],
            cards: [
                {
                    strong: 'Full-screen album',
                    span: 'More immersive mode, directly connected to the track currently playing.'
                },
                {
                    strong: 'Dynamic gradient',
                    span: 'A more minimal visual style based on the track main colors.'
                }
            ],
            save: 'Save visual theme'
        },
        privacy: {
            titleSmall: 'Privacy and usage policy',
            titleStrong: 'Transparency, research, and responsibility',
            guides: [
                {
                    b: 'Project nature',
                    p: 'This player was developed as an experimental project focused on research, study, and technical exploration. Its purpose is to observe synchronization, interface, integration, and user-experience flows in a strictly educational context, without commercial intent, service commitments, or any promise of operational continuity.'
                },
                {
                    b: 'Data and privacy',
                    p: 'To enter the room, the browser may store basic local information such as name, optional photo, and a session identifier. These details exist only to show participant presence, organize the visual jam experience, and preserve synchronization between guests and host. Uploading a photo is optional, and when no image is provided the system uses an automatic initials-based avatar.'
                },
                {
                    b: 'Credentials, access, and responsibility',
                    p: 'Spotify, YouTube, and other integration credentials belong exclusively to the jam host and remain under the host responsibility. Sharing links, exposing the room to guests, and managing permissions are all decisions made by the host, who fully assumes responsibility for credential usage, granted access, and the way the project is employed during testing.'
                },
                {
                    b: 'Limits, non-affiliation, and disclaimer',
                    p: 'This project is provided <i>as is</i>, without any express or implied warranty of continuous availability, permanent compatibility, public stability, or fitness for any specific purpose. It does not constitute an official service, commercial platform, approved product, sponsored integration, or endorsed solution. No official affiliation, partnership, sponsorship, approval, or endorsement exists with Spotify, YouTube, Bandsintown, Songkick, or any other platform mentioned. All trademarks, services, and references belong to their respective owners, and use of this experience occurs entirely at the risk of those hosting or accessing it, including in the event of failures, limitations, third-party policy changes, quotas, outages, or external blocks.'
                }
            ]
        },
        banner: {
            small: 'Privacy and usage policy',
            strong: 'This jam is a study project',
            p: 'To enter the room, the browser may store your name, optional photo, and a local session identifier. The project is experimental, research-oriented, non-commercial, and used at your own risk.',
            details: 'View policy',
            accept: 'Agree and enter'
        },
        tunnel: {
            active: 'Public link ready: {url}',
            activeWaiting: 'Public link active. Waiting for final URL...',
            starting: 'Generating public link automatically...',
            error: 'Could not generate it automatically. If needed, paste the public URL manually.',
            idleLocal: 'No public link yet. Click generate link to open the room for guests.',
            idleRemote: 'No active public link.'
        },
        lockTitle: 'Only the host can control the jam'
    }
};

const setupContextContent = {
    pt: {
        profile: {
            eyebrow: 'Perfil local',
            title: 'Entre na jam com uma identidade simples',
            body: 'Seu nome ajuda a mostrar sua presença na sala. A foto é opcional e, quando ela não existe, o site cria um avatar automático para não deixar seu perfil vazio. O fluxo da jam fica explicado aqui fora para manter o centro da configuração mais limpo.',
            pills: [
                { title: 'O que aparece para os outros', body: 'Seu nome e avatar entram na faixa lateral da jam e ajudam o host a ver quem está acompanhando a sala.' },
                { title: 'Como a jam funciona', body: 'O host escuta localmente, gera o link da sala e os convidados acompanham player, letra e contexto visual pela mesma interface.' },
                { title: 'O que continua salvo', body: 'Nome, foto opcional e identificador local podem voltar automaticamente nos próximos acessos.' }
            ]
        },
        api: {
            eyebrow: 'Conectar APIs',
            title: 'Primeiro crie o app, depois copie as chaves',
            body: 'Este é o tutorial inicial da jam para o host. Você cria as credenciais uma vez, salva nesta tela e depois a rotina fica simples: gerar o link público da sala e enviar para os amigos.',
            pills: [
                { title: 'Preciso fazer isso sempre?', body: 'Não. Em geral, você configura tudo uma única vez, porque as chaves ficam salvas no host para os próximos usos.' },
                { title: 'Depois de salvar', body: 'Com as chaves prontas, você só gera o link público da jam e manda para os amigos. Eles passam a ouvir a mesma faixa que estiver tocando no host.' },
                { title: 'Onde pegar as chaves', body: 'Spotify: crie um app no Developer Dashboard. Google Cloud: crie um projeto, ative YouTube Data API v3 e gere a API key nas credenciais.' }
            ]
        },
        themes: {
            eyebrow: 'Visual da sala',
            title: 'Troque a atmosfera sem mexer na sync',
            body: 'Os temas mudam a apresentação visual da jam, mas não alteram a lógica de playback, letras ou compartilhamento.',
            pills: [
                { title: 'Álbum', body: 'Usa a capa atual como protagonista e deixa a sala mais conectada à faixa.' },
                { title: 'Gradient', body: 'Entrega um fundo mais leve e abstrato, bom para uma leitura mais limpa.' }
            ]
        },
        invites: {
            eyebrow: 'Convites da sala',
            title: 'Gere o link e compartilhe a jam com calma',
            body: 'Este espaço reúne o link público, o link dos convidados e o link privado do host para deixar o compartilhamento mais direto e mais fácil de entender.',
            pills: [
                { title: 'Link dos convidados', body: 'Este é o link normal da sala para qualquer pessoa entrar e acompanhar a jam.' },
                { title: 'Link do host', body: 'Guarde este link privado para você caso precise abrir a sala fora do localhost mantendo acesso de host.' }
            ]
        },
        privacy: {
            eyebrow: 'Uso e limites',
            title: 'Projeto de estudo, sem carinha de pegadinha',
            body: 'Aqui ficam os limites de uso, a desassociação das plataformas e a responsabilidade do host ao compartilhar links, credenciais e permissões.',
            pills: [
                { title: 'Sem uso comercial', body: 'A proposta é pesquisa, estudo e experimentação técnica, não venda nem serviço oficial.' },
                { title: 'Responsabilidade do host', body: 'Quem hospeda a jam responde pelo uso das credenciais, dos links e das permissões abertas.' }
            ]
        }
    },
    en: {
        profile: {
            eyebrow: 'Local profile',
            title: 'Join the jam with a simple identity',
            body: 'Your name helps show presence in the room. The photo is optional, and when it is missing the site generates an automatic avatar so your profile never looks empty. The full jam flow stays outside the center panel to keep the setup cleaner.',
            pills: [
                { title: 'What others see', body: 'Your name and avatar appear in the jam presence rail so the host can see who is following along.' },
                { title: 'How the jam runs', body: 'The host listens locally, generates the room link, and guests follow the same player, lyrics, and visual context through the browser.' },
                { title: 'What stays saved', body: 'Name, optional photo, and a local identifier can come back automatically the next time you visit.' }
            ]
        },
        api: {
            eyebrow: 'Connect APIs',
            title: 'Create the app first, then paste the keys',
            body: 'This is the host onboarding tutorial for the jam. You create the credentials once, save them here, and after that the routine becomes simple: generate the public room link and send it to your friends.',
            pills: [
                { title: 'Do I need this every time?', body: 'No. In most cases you set it up only once, because the keys stay saved on the host for future sessions.' },
                { title: 'After saving the keys', body: 'Once the credentials are ready, you only need to generate the public jam link and share it. Your friends will hear the same track playing on the host.' },
                { title: 'Where to get the keys', body: 'Spotify: create an app in the Developer Dashboard. Google Cloud: create a project, enable YouTube Data API v3, and generate the API key.' }
            ]
        },
        themes: {
            eyebrow: 'Room visuals',
            title: 'Change the atmosphere without touching sync',
            body: 'Themes only change the visual presentation of the jam. They do not affect playback logic, lyrics, or sharing behavior.',
            pills: [
                { title: 'Album', body: 'Uses the current cover art as the main visual anchor for a more immersive room.' },
                { title: 'Gradient', body: 'Creates a lighter and more abstract background for a cleaner reading experience.' }
            ]
        },
        invites: {
            eyebrow: 'Public room',
            title: 'Generate the link and share the room calmly',
            body: 'This area keeps the public link, the guest link, and the private host link together so sharing the jam feels easier to understand.',
            pills: [
                { title: 'Guest link', body: 'This is the normal room link for invited listeners to open the jam.' },
                { title: 'Host link', body: 'Keep this private link to yourself if you need to access the room outside localhost with host permissions.' }
            ]
        },
        privacy: {
            eyebrow: 'Usage and limits',
            title: 'A study project, not a shady service',
            body: 'This area explains usage limits, platform non-affiliation, and the host responsibility when sharing links, credentials, and room permissions.',
            pills: [
                { title: 'No commercial use', body: 'The purpose is research, study, and technical experimentation, not sales or an official service.' },
                { title: 'Host responsibility', body: 'The host remains responsible for how credentials, links, and permissions are used.' }
            ]
        }
    }
};

function buildApiUrl(path) {
    return path;
}

function buildHostHeaders(extraHeaders = {}) {
    return HOST_ACCESS_TOKEN ? { ...extraHeaders, 'X-Host-Token': HOST_ACCESS_TOKEN } : extraHeaders;
}

function getSetupLanguage() {
    const saved = (localStorage.getItem(SETUP_LANGUAGE_KEY) || 'pt').toLowerCase();
    return saved === 'en' ? 'en' : 'pt';
}

function getSetupCopy() {
    return setupTranslations[getSetupLanguage()] || setupTranslations.pt;
}

function interpolateCopy(text, values = {}) {
    return String(text || '').replace(/\{(\w+)\}/g, (_, key) => values[key] ?? '');
}

function setText(selector, value) {
    const node = document.querySelector(selector);
    if (node) node.textContent = value;
}

function setHtml(selector, value) {
    const node = document.querySelector(selector);
    if (node) node.innerHTML = value;
}

function setPlaceholder(selector, value) {
    const node = document.querySelector(selector);
    if (node) node.setAttribute('placeholder', value);
}

function setFieldLabelByInputId(inputId, value) {
    const input = document.getElementById(inputId);
    const label = input?.closest('.input-group')?.querySelector('label');
    if (label) label.textContent = value;
}

function setFieldHelpByInputId(inputId, value, useHtml = false) {
    const input = document.getElementById(inputId);
    const help = input?.closest('.input-group')?.querySelector('.field-help');
    if (!help) return;
    if (useHtml) {
        help.innerHTML = value;
    } else {
        help.textContent = value;
    }
}

function renderSetupContextHints(section = null) {
    const lang = getSetupLanguage();
    const activeSection = section || document.querySelector('.setup-nav-btn.is-active')?.dataset.target || 'profile';
    const copy = (setupContextContent[lang] || setupContextContent.pt)[activeSection] || (setupContextContent[lang] || setupContextContent.pt).profile;
    const eyebrow = document.getElementById('setupContextEyebrow');
    const title = document.getElementById('setupContextTitle');
    const body = document.getElementById('setupContextBody');
    const pills = document.getElementById('setupContextPills');
    if (eyebrow) eyebrow.textContent = copy.eyebrow;
    if (title) title.textContent = copy.title;
    if (body) body.textContent = copy.body;
    if (pills) {
        pills.innerHTML = '';
        (copy.pills || []).forEach((item) => {
            const pill = document.createElement('div');
            pill.className = 'setup-context-pill';
            pill.innerHTML = `<b>${item.title}</b><p>${item.body}</p>`;
            pills.appendChild(pill);
        });
    }
}

function applySetupLanguage() {
    const copy = getSetupCopy();

    setText('.setup-eyebrow', copy.header.eyebrow);
    setText('.setup-header h2', copy.header.title);
    setText('.setup-header p', copy.header.desc);

    document.querySelectorAll('.setup-lang-btn').forEach((button) => {
        button.classList.toggle('is-active', button.dataset.lang === getSetupLanguage());
    });

    const navButtons = Array.from(document.querySelectorAll('.setup-nav-btn'));
    navButtons.forEach((button, index) => {
        const navCopy = copy.nav[index];
        if (!navCopy) return;
        const small = button.querySelector('small');
        const strong = button.querySelector('strong');
        if (small) small.textContent = navCopy.small;
        if (strong) strong.textContent = navCopy.strong;
    });

    setText('#setupPanelProfile > .setup-section-title small', copy.profile.titleSmall);
    setText('#setupPanelProfile > .setup-section-title strong', copy.profile.titleStrong);
    setText('#profileOnboardingCard .setup-section-title small', copy.profile.onboardingSmall);
    setText('#profileOnboardingCard .setup-section-title strong', copy.profile.onboardingStrong);
    setHtml('#profileOnboardingHint1', copy.profile.onboardingP1);
    setHtml('#profileOnboardingHint2', copy.profile.onboardingP2);
    setText('#setupPanelProfile .profile-identity-card .input-group:nth-of-type(1) label', copy.profile.nameLabel);
    setPlaceholder('#profileNameInput', copy.profile.namePlaceholder);
    setHtml('#profileNameHelp', copy.profile.nameHelp);
    setText('#setupPanelProfile .profile-identity-card .input-group:nth-of-type(2) label', copy.profile.photoLabel);
    setText('#profilePhotoHelp', copy.profile.photoHelp);
    setText('#saveProfileBtn', copy.profile.saveProfile);
    setText('#guestControlCard .setup-section-title small', copy.profile.guestSmall);
    setText('#guestControlCard .setup-section-title strong', copy.profile.guestStrong);
    setText('#guestControlCard .toggle-row b', copy.profile.guestLabel);
    setText('#saveGuestControlBtn', copy.profile.saveGuest);
    setText('#hostLinksCard .setup-section-title small', copy.invites.linksSmall);
    setText('#hostLinksCard .setup-section-title strong', copy.invites.linksStrong);

    const shareGuideItems = Array.from(document.querySelectorAll('#hostLinksCard .share-flow-card .guide-item'));
    shareGuideItems.forEach((item, index) => {
        const current = copy.invites.shareGuides[index];
        if (!current) return;
        const b = item.querySelector('b');
        const p = item.querySelector('p');
        if (b) b.textContent = current.b;
        if (p) p.textContent = current.p;
    });

    setText('#hostLinksCard .input-group:nth-of-type(1) label', copy.invites.baseLabel);
    setPlaceholder('#publicBaseUrlInput', 'Ex.: https://my-jam.trycloudflare.com');
    setHtml('#hostLinksCard .input-group:nth-of-type(1) .field-help', copy.invites.baseHelp);
    setText('#startTunnelBtn', copy.invites.generateLink);
    setText('#stopTunnelBtn', copy.invites.stopLink);
    setText('#savePublicBaseUrlBtn', copy.invites.saveUrl);
    setText('#hostLinksCard .share-link-grid .input-group:nth-of-type(1) label', copy.invites.viewerLabel);
    setText('#hostLinksCard .share-link-grid .input-group:nth-of-type(1) .field-help', copy.invites.viewerHelp);
    setText('#copyViewerLinkBtn', copy.invites.copyViewer);
    setText('#viewerQrCard small', copy.invites.qrCaption);
    setText('#hostLinksCard .share-link-grid .input-group:nth-of-type(2) label', copy.invites.hostLabel);
    setText('#hostLinksCard .share-link-grid .input-group:nth-of-type(2) .field-help', copy.invites.hostHelp);
    setText('#copyHostLinkBtn', copy.invites.copyHost);

    setText('#setupPanelApi .setup-section-title small', copy.api.titleSmall);
    setText('#setupPanelApi .setup-section-title strong', copy.api.titleStrong);
    setText('#apiTutorialEyebrow', copy.api.tutorialEyebrow);
    setText('#apiTutorialTitle', copy.api.tutorialTitle);
    setHtml('#apiTutorialBody', copy.api.tutorialBody);
    setHtml('#apiTutorialFooter', copy.api.tutorialFooter);
    const apiGuides = Array.from(document.querySelectorAll('#setupPanelApi .config-guide-card .guide-item'));
    apiGuides.forEach((item, index) => {
        const current = copy.api.guides[index];
        if (!current) return;
        const b = item.querySelector('b');
        const p = item.querySelector('p');
        if (b) b.textContent = current.b;
        if (p) p.innerHTML = current.p;
    });
    const apiLinks = Array.from(document.querySelectorAll('#setupPanelApi .help-link'));
    apiLinks.forEach((link, index) => {
        if (copy.api.links[index]) link.textContent = copy.api.links[index];
    });
    setFieldLabelByInputId('clientIdInput', copy.api.clientIdLabel);
    setPlaceholder('#clientIdInput', copy.api.clientIdPlaceholder);
    setFieldHelpByInputId('clientIdInput', copy.api.clientIdHelp, true);
    setFieldLabelByInputId('clientSecretInput', copy.api.clientSecretLabel);
    setPlaceholder('#clientSecretInput', copy.api.clientSecretPlaceholder);
    setFieldHelpByInputId('clientSecretInput', copy.api.clientSecretHelp, true);
    setFieldLabelByInputId('ytKeyInput', copy.api.ytLabel);
    setPlaceholder('#ytKeyInput', copy.api.ytPlaceholder);
    setFieldHelpByInputId('ytKeyInput', copy.api.ytHelp);
    setText('#saveSetupHint', copy.api.saveHint);
    setText('#saveSetupBtn', copy.api.save);
    ensureSpotifyAuthButton();

    setText('#setupPanelThemes .setup-section-title small', copy.themes.titleSmall);
    setText('#setupPanelThemes .setup-section-title strong', copy.themes.titleStrong);
    const themeGuides = Array.from(document.querySelectorAll('#setupPanelThemes .config-guide-card .guide-item'));
    themeGuides.forEach((item, index) => {
        const current = copy.themes.guides[index];
        if (!current) return;
        const b = item.querySelector('b');
        const p = item.querySelector('p');
        if (b) b.textContent = current.b;
        if (p) p.textContent = current.p;
    });
    const themeCards = Array.from(document.querySelectorAll('#setupPanelThemes .theme-option-card'));
    themeCards.forEach((card, index) => {
        const current = copy.themes.cards[index];
        if (!current) return;
        const strong = card.querySelector('strong');
        const span = card.querySelector('span');
        if (strong) strong.textContent = current.strong;
        if (span) span.textContent = current.span;
    });
    setText('#saveThemeBtn', copy.themes.save);

    setText('#setupPanelPrivacy .setup-section-title small', copy.privacy.titleSmall);
    setText('#setupPanelPrivacy .setup-section-title strong', copy.privacy.titleStrong);
    const privacyGuides = Array.from(document.querySelectorAll('#setupPanelPrivacy .guide-item'));
    privacyGuides.forEach((item, index) => {
        const current = copy.privacy.guides[index];
        if (!current) return;
        const b = item.querySelector('b');
        const p = item.querySelector('p');
        if (b) b.textContent = current.b;
        if (p) p.innerHTML = current.p;
    });

    setText('#privacyBanner .privacy-banner-copy small', copy.banner.small);
    setText('#privacyBanner .privacy-banner-copy strong', copy.banner.strong);
    setText('#privacyBanner .privacy-banner-copy p', copy.banner.p);
    setText('#privacyBannerDetailsBtn', copy.banner.details);
    setText('#privacyBannerAcceptBtn', copy.banner.accept);

    updateTunnelUi();
    updateControlAvailability();
    renderSetupContextHints();
}

function finishAppBoot() {
    const body = document.body;
    if (!body) return;
    requestAnimationFrame(() => {
        body.classList.remove('app-preboot');
    });
}

function debugHydrationSync(stage, details = {}) {
    if (hydrationDebugLogged && stage === 'start') return;
    if (stage === 'done') hydrationDebugLogged = true;
    try {
        console.log('[hydration-sync]', stage, details);
    } catch (e) {}
}

function armHydrationSyncBurst(extraPolls = 3) {
    hydrationSyncBurstRemaining = Math.max(hydrationSyncBurstRemaining, Math.max(0, Number(extraPolls) || 0));
}

function clearHydrationSyncBurst() {
    hydrationSyncBurstRemaining = 0;
}

function scheduleHydrationSeekReinforcement(player, targetTime) {
    if (!player || typeof player.seekTo !== 'function') return;
    [120, 380].forEach((delayMs) => {
        setTimeout(() => {
            if (currentVideoId && Player.playerAtivo === player) {
                try {
                    player.seekTo(targetTime, true);
                } catch (e) {}
            }
        }, delayMs);
    });
}

const RING_COLOR = "29, 185, 84";
document.documentElement.style.setProperty('--ring-rgb', RING_COLOR);

Player.initYouTube(
    async () => {
        await loadSessionState();
        await loadTunnelStatus();
        setInterval(() => fetchArtistContext(false), 5000);
        setInterval(() => fetchProfiles(), 5000);
        setInterval(() => loadSessionState(), 10000);
        setInterval(() => loadTunnelStatus(), 5000);
        fetchQueuePreview();
        setInterval(() => fetchQueuePreview(), 20000);
        setInterval(() => syncStoredProfileToServer(), 15000);
        finishAppBoot();
        await syncEngine.checkStatus();
        maybeShowSpotifyResumePrompt();
        requestAnimationFrame(renderLoop);
    },
    onPlayerStateChange
);

function getStatusPollInterval() {
    const totalTimeLabel = document.getElementById('totalTime')?.innerText || "0:00";
    const currentTimeLabel = document.getElementById('currentTime')?.innerText || "0:00";
    const toSeconds = (value) => {
        const [min, sec] = value.split(':').map((part) => parseInt(part, 10) || 0);
        return (min * 60) + sec;
    };

    const remaining = Math.max(0, toSeconds(totalTimeLabel) - toSeconds(currentTimeLabel));
    const currentSeconds = Math.max(0, toSeconds(currentTimeLabel));
    if (isSetupSyncRetryActive()) return 320;
    if (hydrationSyncBurstRemaining > 0) return 240;
    if (isSwapping || isWaitingForSync || isSyncAssistActive()) return 650;
    if (document.body.classList.contains('is-track-handoff-late')) return 360;
    if (document.body.classList.contains('is-track-handoff')) return 900;
    if (currentSeconds > 0 && currentSeconds < 3) return 2400;
    if (remaining > 0 && remaining <= 4) return 2800;
    return 1600;
}

function scheduleStatusPoll(delay = getStatusPollInterval()) {
    clearTimeout(statusPollTimer);
    const safeDelay = Math.max(120, delay || 0);
    statusPollTimer = setTimeout(() => syncEngine.checkStatus(), safeDelay);
}

function openSyncAssistWindow(durationMs = 2400) {
    syncAssistUntil = Date.now() + durationMs;
}

function isSyncAssistActive() {
    return Date.now() < syncAssistUntil;
}

function openLocalPausePending(durationMs = 1400) {
    localPausePendingUntil = Date.now() + durationMs;
}

function openUnresolvedTrackGrace(trackKey, durationMs = 900) {
    unresolvedTrackGraceKey = trackKey || "";
    unresolvedTrackGraceUntil = Date.now() + durationMs;
}

function isUnresolvedTrackGraceActive(trackKey = "") {
    if (!unresolvedTrackGraceKey || !trackKey) return false;
    return unresolvedTrackGraceKey === trackKey && Date.now() < unresolvedTrackGraceUntil;
}

function clearUnresolvedTrackGrace() {
    unresolvedTrackGraceKey = "";
    unresolvedTrackGraceUntil = 0;
}

function openSetupSyncRetryWindow(durationMs = 15000) {
    setupSyncRetryUntil = Date.now() + durationMs;
}

function isSetupSyncRetryActive() {
    return Date.now() < setupSyncRetryUntil;
}

function clearSetupSyncRetryWindow() {
    setupSyncRetryUntil = 0;
}

function clearSpotifyAuthQueryParam() {
    try {
        const params = new URLSearchParams(window.location.search);
        if (!params.has('spotify_auth')) return;
        params.delete('spotify_auth');
        const query = params.toString();
        const nextUrl = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash || ''}`;
        window.history.replaceState({}, document.title, nextUrl);
    } catch (e) {}
}

function ensureSpotifyResumePrompt() {
    let prompt = document.getElementById('spotifyResumePrompt');
    if (prompt) return prompt;

    prompt = document.createElement('button');
    prompt.id = 'spotifyResumePrompt';
    prompt.type = 'button';
    prompt.className = 'spotify-resume-prompt hidden';
    prompt.innerHTML = '<strong>Retomar a jam</strong><span>Clique para iniciar o audio da jam nesta mesma aba</span>';
    prompt.addEventListener('click', async () => {
        if (!audioUnlocked) {
            audioUnlocked = true;
            Player.turnOnAudio(true);
            prepareActivePlayerAudio();
        }
        openSetupSyncRetryWindow(15000);
        openSyncAssistWindow(3600);
        armHydrationSyncBurst(3);
        isWaitingForSync = true;
        prompt.classList.add('hidden');
        clearSpotifyAuthQueryParam();
        await syncEngine.checkStatus();
        setTimeout(() => syncEngine.checkStatus(), 320);
        scheduleStatusPoll(120);
    });
    document.body.appendChild(prompt);
    return prompt;
}

function showSpotifyResumePrompt(mode = 'playback') {
    const prompt = ensureSpotifyResumePrompt();
    if (mode === 'auth') {
        prompt.innerHTML = '<strong>Spotify conectado</strong><span>Clique para retomar a jam nesta mesma aba</span>';
    } else {
        prompt.innerHTML = '<strong>Retomar a jam</strong><span>Esta aba precisa de um clique para tocar a musica que ja esta no Spotify</span>';
    }
    prompt.classList.remove('hidden');
    return prompt;
}

function maybeShowSpotifyResumePrompt() {
    if (SPOTIFY_AUTH_STATE !== 'ok') return;
    showSpotifyResumePrompt('auth');
}

function ensureSpotifyAuthButton() {
    const saveButton = document.getElementById('saveSetupBtn');
    if (!saveButton || document.getElementById('spotifyAuthBtn')) return;

    const authButton = document.createElement('button');
    authButton.id = 'spotifyAuthBtn';
    authButton.type = 'button';
    authButton.className = 'secondary-btn';
    authButton.textContent = 'Autorizar Spotify';

    const authHint = document.createElement('small');
    authHint.id = 'spotifyAuthHint';
    authHint.className = 'field-help field-help-block';
    authHint.textContent = 'Se a autorização não abrir sozinha, use este botão para abrir o login do Spotify manualmente.';

    saveButton.insertAdjacentElement('afterend', authButton);
    authButton.insertAdjacentElement('afterend', authHint);
    authButton.addEventListener('click', openSpotifyAuthFlow);
}

async function openSpotifyAuthFlow() {
    try {
        const response = await fetch(buildApiUrl('/spotify/auth-url'), {
            headers: buildHostHeaders()
        });
        const data = await response.json();
        if (response.ok && data?.status === 'OK' && data?.url) {
            window.location.href = data.url;
            return;
        }
    } catch (_error) {
        // noop
    }
    showSetupMessage('Não foi possível abrir a autorização do Spotify agora.');
}

function isLocalPausePending() {
    return Date.now() < localPausePendingUntil;
}

function updateSpotifyClockState(data) {
    latestSpotifyTime = Math.max(0, Number(data?.spotify_time || 0));
    latestSpotifyDuration = Math.max(0, Number(data?.duration_ms || 0) / 1000);
    latestSpotifyIsPlaying = !!data?.is_playing && !isLocalPausePending();
    latestSpotifyStatusAt = Date.now();
}

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function isRelaxedOffsetTrack(trackKey = "") {
    const key = String(trackKey || "").toLowerCase();
    return /\blive\b|ao vivo|acoustic|session|mtv unplugged|unplugged|concert|tour/.test(key);
}

function getCurrentTrackOffset() {
    return 0;
}

function getReferencePlaybackTime() {
    const ytCurrent = (Player.playerAtivo && typeof Player.playerAtivo.getCurrentTime === 'function')
        ? Player.playerAtivo.getCurrentTime()
        : 0;

    const statusAge = Date.now() - latestSpotifyStatusAt;
    if (!latestSpotifyStatusAt || statusAge > 2500) {
        return ytCurrent;
    }

    let spotifyCurrent = latestSpotifyTime;
    if (latestSpotifyIsPlaying) {
        spotifyCurrent += statusAge / 1000;
    }

    if (latestSpotifyDuration > 0) {
        spotifyCurrent = Math.min(spotifyCurrent, latestSpotifyDuration);
    }

    if (isWaitingForSync || isSyncAssistActive()) {
        return spotifyCurrent;
    }

    if (Math.abs(spotifyCurrent - ytCurrent) <= 0.45) {
        return spotifyCurrent;
    }

    return ytCurrent;
}

function getLyricsPlaybackTime() {
    const ytCurrent = (Player.playerAtivo && typeof Player.playerAtivo.getCurrentTime === 'function')
        ? Player.playerAtivo.getCurrentTime()
        : 0;

    if (isWaitingForSync) {
        return getReferencePlaybackTime();
    }

    if (isSyncAssistActive()) {
        const referenceTime = getReferencePlaybackTime();
        if (Math.abs(referenceTime - ytCurrent) <= 1.2) {
            return referenceTime;
        }
    }

    return ytCurrent;
}

function renderLoop() {
    if (Player.playerAtivo && typeof Player.playerAtivo.getCurrentTime === 'function' && !isSetupMode) {
        const lyricTime = getLyricsPlaybackTime();
        const referenceTime = getReferencePlaybackTime();
        syncEngine.handleLyricSync(lyricTime);
        syncEngine.updateProgressBar(referenceTime);
        updateAmbientBeat(referenceTime);
    }
    updateJamInviteToast();
    requestAnimationFrame(renderLoop);
}

function updateAmbientBeat(currentTime = 0) {
    const body = document.body;
    if (!body) return;

    const isPlayingNow = !!Player.isPlaying && !isWaitingForSync;
    body.classList.toggle('is-playing', isPlayingNow);

    if (!isPlayingNow) {
        body.classList.remove('beat-a', 'beat-b');
        return;
    }

    const pulseIndex = Math.floor(currentTime * 1.6) % 2;
    body.classList.toggle('beat-a', pulseIndex === 0);
    body.classList.toggle('beat-b', pulseIndex === 1);
}

function onPlayerStateChange(event) {
    const albumArt = document.querySelector('.album-art-container');
    if (event.target !== Player.playerAtivo) return;

    if (event.data === YT.PlayerState.PLAYING) {
        pauseDetectionCount = 0;
        Player.setIsPlaying(true);
        if (!isWaitingForSync) updatePlayIcons('pause');
        if (albumArt) albumArt.style.animation = 'spin 20s linear infinite';
    } else if (
        event.data === YT.PlayerState.PAUSED ||
        event.data === YT.PlayerState.ENDED ||
        event.data === YT.PlayerState.CUED
    ) {
        Player.setIsPlaying(false);
        if (!isWaitingForSync) updatePlayIcons('play');
        if (albumArt) albumArt.style.animationPlayState = 'paused';
    }
}

async function fetchArtistContext(force = false) {
    try {
        const response = await fetch(buildApiUrl('/artist-context'), {
            headers: buildHostHeaders()
        });
        const data = await response.json();
        if (!data || !data.artist) return;
        renderArtistWidget(data);
        lastArtistContextArtist = data.artist;
    } catch (e) {
        console.error("Artist Context Error:", e);
    }
}

function setArtistWidgetRow(rowId, textId, value) {
    return { rowId, textId, value };
}

function renderArtistWidget(data) {
    const loading = document.getElementById('artistWidgetLoading');
    const frame = document.getElementById('artistWidgetFrame');
    if (!loading || !frame) return;

    if (data.loading) {
        const sameArtistStillMounted = data.artist && data.artist === mountedArtistWidgetArtist && !!frame.src;
        const eyebrow = document.getElementById('artistWidgetLoadingEyebrow');
        const title = document.getElementById('artistWidgetLoadingTitle');
        if (eyebrow) eyebrow.innerText = data.artist ? 'Montando a jam visual' : 'Contexto do artista';
        if (title) title.innerText = data.artist ? `Buscando universo de ${data.artist}...` : 'Buscando informacoes...';
        if (sameArtistStillMounted) {
            loading.style.display = 'none';
            frame.style.display = 'block';
            mountedArtistWidgetArtist = data.artist || mountedArtistWidgetArtist;
            if (data.updated_at && data.updated_at !== lastArtistContextTs) {
                lastArtistContextTs = data.updated_at;
                frame.src = `/artist-widget?ts=${data.updated_at}`;
            }
        } else {
            loading.style.display = 'flex';
            frame.style.display = 'none';
        }
        return;
    }

    const hasWidgetData =
        (Array.isArray(data.image_urls) && data.image_urls.length > 0) ||
        !!data.video_url ||
        !!data.status ||
        !!data.proximo_show ||
        !!data.ultimo_show ||
        (Array.isArray(data.curiosidades) && data.curiosidades.length > 0);

    if (!hasWidgetData) {
        loading.style.display = 'flex';
        frame.style.display = 'none';
        return;
    }

    loading.style.display = 'none';
    frame.style.display = 'block';
    mountedArtistWidgetArtist = data.artist || mountedArtistWidgetArtist;

    if (data.updated_at && data.updated_at !== lastArtistContextTs) {
        lastArtistContextTs = data.updated_at;
        frame.src = `/artist-widget?ts=${data.updated_at}`;
    } else if (!frame.src) {
        frame.src = '/artist-widget';
    }
}

function updatePageTitle(title, artist) {
    const cleanTitle = (title || '').trim();
    const cleanArtist = (artist || '').trim();

    if (cleanTitle && cleanArtist) {
        document.title = `nonuser35 player - ${cleanTitle} - ${cleanArtist}`;
        return;
    }

    if (cleanTitle) {
        document.title = `nonuser35 player - ${cleanTitle}`;
        return;
    }

    document.title = 'nonuser35 player';
}

function openSetupModal(targetSection = null) {
    clearTimeout(jamInviteToastTimer);
    jamInviteToastTimer = null;
    jamInviteToastVisible = false;
    document.getElementById('jamInviteToast')?.classList.add('hidden');
    document.getElementById('jamInviteToast')?.classList.remove('is-visible');
    document.getElementById('setupModal')?.classList.remove('hidden');
    applySetupLanguage();
    const effectiveTarget = targetSection || (setupApiLockActive ? 'api' : null);
    if (effectiveTarget) {
        toggleSetupSection(effectiveTarget);
        if (effectiveTarget === 'profile') {
            setTimeout(() => {
                document.getElementById('profileNameInput')?.focus();
            }, 40);
        }
    }
    if (sessionState.isHost) {
        loadServerConfig();
    }
    loadThemeSelection();
}

function closeSetupModal() {
    if (isSetupMode) return;
    document.getElementById('setupModal')?.classList.add('hidden');
    scheduleJamInviteToast();
}

function updatePrivacyBanner() {
    const banner = document.getElementById('privacyBanner');
    if (!banner) return;
    const accepted = localStorage.getItem(PRIVACY_BANNER_ACCEPTED_KEY) === 'true';
    banner.classList.toggle('hidden', accepted);
}

function acceptPrivacyBanner() {
    localStorage.setItem(PRIVACY_BANNER_ACCEPTED_KEY, 'true');
    updatePrivacyBanner();
    updateJamInviteToast();
}

function toggleSetupSection(targetSection) {
    if (setupApiLockActive && !['api', 'privacy'].includes(targetSection)) {
        targetSection = 'api';
    }
    if (targetSection === 'api' && !sessionState.isHost) {
        targetSection = 'profile';
    }
    document.querySelectorAll('.setup-nav-btn').forEach((button) => {
        button.classList.toggle('is-active', button.dataset.target === targetSection);
    });
    document.querySelectorAll('.setup-panel').forEach((panel) => {
        const shouldOpen = panel.dataset.section === targetSection;
        panel.classList.toggle('is-active', shouldOpen);
    });
    renderSetupContextHints(targetSection);
}

function updateControlAvailability() {
    const canControl = !!sessionState.canControl;
    const copy = getSetupCopy();
    ['playPauseBtn', 'nextBtn', 'prevBtn'].forEach((id) => {
        const button = document.getElementById(id);
        if (!button) return;
        button.disabled = !canControl;
        button.classList.toggle('is-locked', !canControl);
        button.setAttribute('title', canControl ? '' : copy.lockTitle);
    });
}

function ensureStatusMetaNode() {
    const monitor = document.querySelector('.server-monitor');
    const statusText = document.getElementById('statusText');
    if (!monitor || !statusText) return null;

    let copyWrap = monitor.querySelector('.server-monitor-copy');
    if (!copyWrap) {
        copyWrap = document.createElement('div');
        copyWrap.className = 'server-monitor-copy';
        statusText.parentNode?.insertBefore(copyWrap, statusText);
        copyWrap.appendChild(statusText);
    }

    let meta = document.getElementById('statusMeta');
    if (!meta) {
        meta = document.createElement('small');
        meta.id = 'statusMeta';
        copyWrap.appendChild(meta);
    }

    return meta;
}

function getJamPresenceLabel() {
    if (latestJamPresenceCount <= 0) {
        return 'sala em preparo';
    }
    return latestJamPresenceCount <= 1 ? '1 pessoa na sala' : `${latestJamPresenceCount} pessoas na sala`;
}

function setJamStatus(mainText, metaText, color, stateName) {
    const statusText = document.getElementById('statusText');
    const statusIcon = document.getElementById('connectionStatus');
    const statusMeta = ensureStatusMetaNode();
    const monitor = document.querySelector('.server-monitor');
    if (statusText) statusText.innerText = mainText;
    if (statusMeta) statusMeta.innerText = metaText;
    if (statusIcon) statusIcon.style.color = color;
    if (monitor) monitor.dataset.state = stateName || 'idle';
}

function updateShareLinks() {
    const linkCard = document.getElementById('hostLinksCard');
    const viewerInput = document.getElementById('viewerLinkInput');
    const hostInput = document.getElementById('hostLinkInput');
    const publicBaseUrlInput = document.getElementById('publicBaseUrlInput');
    const viewerQrCard = document.getElementById('viewerQrCard');
    const viewerQrImage = document.getElementById('viewerQrImage');
    if (!linkCard || !viewerInput || !hostInput) return;

    linkCard.classList.toggle('hidden', !sessionState.isHost);
    if (!sessionState.isHost) return;

    const publicBase = (sessionState.publicBaseUrl || '').trim();
    const shouldAvoidLocalLinks = sessionState.isLocalRequest && !publicBase;
    const cleanPath = publicBase ? `${publicBase}${window.location.pathname}` : '';
    const viewerLink = shouldAvoidLocalLinks ? '' : (cleanPath || `${window.location.origin}${window.location.pathname}`);
    const hostLink = viewerLink && sessionState.hostToken ? `${viewerLink}?host=${encodeURIComponent(sessionState.hostToken)}` : viewerLink;

    viewerInput.value = viewerLink;
    hostInput.value = hostLink;
    if (publicBaseUrlInput) {
        publicBaseUrlInput.value = sessionState.publicBaseUrl || '';
    }
    if (viewerQrCard && viewerQrImage) {
        const shouldShowQr = !!viewerLink && !shouldAvoidLocalLinks;
        viewerQrCard.classList.toggle('hidden', !shouldShowQr);
        if (shouldShowQr) {
            viewerQrImage.src = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(viewerLink)}`;
        } else {
            viewerQrImage.removeAttribute('src');
        }
    }
}

function updateTunnelUi() {
    const tunnelStatusText = document.getElementById('tunnelStatusText');
    const startTunnelBtn = document.getElementById('startTunnelBtn');
    const stopTunnelBtn = document.getElementById('stopTunnelBtn');
    if (!tunnelStatusText || !startTunnelBtn || !stopTunnelBtn) return;
    const copy = getSetupCopy();

    startTunnelBtn.classList.toggle('hidden', !sessionState.isHost);
    stopTunnelBtn.classList.toggle('hidden', !sessionState.isHost);

    if (sessionState.tunnelStatus === 'active') {
        tunnelStatusText.innerText = sessionState.publicBaseUrl
            ? interpolateCopy(copy.tunnel.active, { url: sessionState.publicBaseUrl })
            : copy.tunnel.activeWaiting;
    } else if (sessionState.tunnelStatus === 'starting') {
        tunnelStatusText.innerText = copy.tunnel.starting;
    } else if (sessionState.tunnelStatus === 'error') {
        tunnelStatusText.innerText = copy.tunnel.error;
    } else {
        tunnelStatusText.innerText = sessionState.isLocalRequest
            ? copy.tunnel.idleLocal
            : copy.tunnel.idleRemote;
    }

    startTunnelBtn.disabled = sessionState.tunnelStatus === 'starting';
    stopTunnelBtn.disabled = !sessionState.tunnelActive && sessionState.tunnelStatus !== 'starting';
}

function applySessionUi() {
    const profileNavBtn = document.querySelector('.setup-nav-btn[data-target="profile"]');
    const themesNavBtn = document.querySelector('.setup-nav-btn[data-target="themes"]');
    const apiNavBtn = document.querySelector('.setup-nav-btn[data-target="api"]');
    const invitesNavBtn = document.querySelector('.setup-nav-btn[data-target="invites"]');
    const privacyNavBtn = document.querySelector('.setup-nav-btn[data-target="privacy"]');
    const apiPanel = document.getElementById('setupPanelApi');
    const invitesPanel = document.getElementById('setupPanelInvites');
    const guestControlCard = document.getElementById('guestControlCard');
    const guestControlToggle = document.getElementById('guestControlToggle');
    const guestControlStatus = document.getElementById('guestControlStatus');
    setupApiLockActive = !!(sessionState.isHost && sessionState.setupRequired && !sessionState.hasApiCredentials);

    if (apiNavBtn) {
        apiNavBtn.classList.toggle('hidden', !sessionState.isHost);
        apiNavBtn.disabled = false;
    }
    if (privacyNavBtn) {
        privacyNavBtn.disabled = false;
    }
    if (profileNavBtn) {
        profileNavBtn.classList.toggle('hidden', setupApiLockActive);
        profileNavBtn.disabled = setupApiLockActive;
    }
    if (themesNavBtn) {
        themesNavBtn.classList.toggle('hidden', setupApiLockActive);
        themesNavBtn.disabled = setupApiLockActive;
    }
    if (invitesNavBtn) {
        invitesNavBtn.classList.toggle('hidden', !sessionState.isHost || setupApiLockActive);
        invitesNavBtn.disabled = !sessionState.isHost || setupApiLockActive;
    }
    if (apiPanel) {
        apiPanel.classList.toggle('hidden', !sessionState.isHost);
    }
    if (invitesPanel) {
        invitesPanel.classList.toggle('hidden', !sessionState.isHost);
    }
    if (guestControlCard) {
        guestControlCard.classList.toggle('hidden', !sessionState.isHost);
    }
    if (guestControlToggle) {
        guestControlToggle.checked = !!sessionState.allowGuestControls;
    }
    if (guestControlStatus) {
        const copy = getSetupCopy();
        guestControlStatus.innerText = sessionState.allowGuestControls
            ? copy.profile.guestStatusOn
            : copy.profile.guestStatusOff;
    }

    const activeSetupSection = document.querySelector('.setup-nav-btn.is-active')?.dataset.target || '';
    if (!sessionState.isHost && ['api', 'invites'].includes(activeSetupSection)) {
        toggleSetupSection('profile');
    }
    if (setupApiLockActive && !['api', 'privacy'].includes(activeSetupSection)) {
        toggleSetupSection('api');
    }

    updateControlAvailability();
    updateShareLinks();
    updateTunnelUi();
    applySetupLanguage();
}

async function loadSessionState() {
    try {
        const response = await fetch(buildApiUrl('/session'), {
            headers: buildHostHeaders()
        });
        const data = await response.json();
        sessionState.isHost = !!data.is_host;
        sessionState.canControl = !!data.can_control;
        sessionState.allowGuestControls = !!data.allow_guest_controls;
        sessionState.setupRequired = !!data.setup_required;
        sessionState.hasApiCredentials = !!data.has_api_credentials;
        sessionState.hostToken = data.host_token || sessionState.hostToken || HOST_ACCESS_TOKEN;
        sessionState.publicBaseUrl = (data.public_base_url || '').trim();
        sessionState.isLocalRequest = !!data.is_local_request;
        sessionState.tunnelStatus = data.tunnel_status || data.tunnel_state || 'idle';
        sessionState.tunnelActive = !!data.tunnel_active;
    } catch (error) {
        console.error('Session Load Error:', error);
    } finally {
        applySessionUi();
        maybeAutoStartTunnel();
    }
}

function maybeAutoStartTunnel() {
    if (
        !sessionState.isHost ||
        !sessionState.isLocalRequest ||
        sessionState.tunnelActive ||
        sessionState.tunnelStatus === 'starting' ||
        tunnelAutoStartAttempted
    ) {
        return;
    }

    tunnelAutoStartAttempted = true;
    const startTunnelBtn = document.getElementById('startTunnelBtn');
    startTunnelBtn?.click();
}

async function loadTunnelStatus() {
    if (!sessionState.isHost) return;
    try {
        const response = await fetch(buildApiUrl('/tunnel/status'), {
            headers: buildHostHeaders()
        });
        const data = await response.json();
        sessionState.tunnelStatus = data.tunnel_state || 'idle';
        sessionState.tunnelActive = !!data.active;
        if (data.public_base_url) {
            sessionState.publicBaseUrl = data.public_base_url.trim();
        } else if (!data.active && sessionState.tunnelStatus === 'idle') {
            sessionState.publicBaseUrl = sessionState.publicBaseUrl;
        }
        applySessionUi();
    } catch (error) {
        console.error('Tunnel Status Error:', error);
    }
}

function applyThemeMode(themeMode = 'album') {
    const safeTheme = ['album', 'gradient'].includes(themeMode) ? themeMode : 'album';
    document.body.dataset.themeMode = safeTheme;
}

function loadThemeSelection() {
    const savedTheme = localStorage.getItem(THEME_MODE_KEY) || 'album';
    document.querySelectorAll('input[name="backgroundTheme"]').forEach((input) => {
        input.checked = input.value === savedTheme;
    });
    applyThemeMode(savedTheme);
}

function ensureProfileClientId() {
    let clientId = localStorage.getItem(PROFILE_CLIENT_ID_KEY) || '';
    if (!clientId) {
        clientId = `jam-${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36)}`;
        localStorage.setItem(PROFILE_CLIENT_ID_KEY, clientId);
    }
    return clientId;
}

function getStoredGuestToken() {
    return (localStorage.getItem(PROFILE_GUEST_TOKEN_KEY) || '').trim();
}

function storeGuestIdentity(guestToken = '', recoveryCode = '') {
    if (guestToken) {
        localStorage.setItem(PROFILE_GUEST_TOKEN_KEY, guestToken);
    }
    if (recoveryCode) {
        localStorage.setItem(PROFILE_RECOVERY_CODE_KEY, recoveryCode);
    }
}

function getProfileInitials(name = '') {
    const cleanName = (name || '').trim();
    return cleanName
        ? cleanName.split(/\s+/).slice(0, 2).map(part => part[0]?.toUpperCase() || '').join('')
        : 'N';
}

function escapeHtml(value = '') {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function buildSampleProfiles() {
    const now = Math.floor(Date.now() / 1000);
    const profiles = SAMPLE_JAM_PROFILES.map((profile, index) => ({
        ...profile,
        updated_at: now - (index * 6)
    }));
    profiles.host_client_id = SAMPLE_JAM_PROFILES[0].client_id;
    profiles.total_online = profiles.length;
    profiles.joined_recently_window = 30;
    profiles.server_time = now;
    return profiles;
}

function clampChannel(value) {
    return Math.max(0, Math.min(255, Math.round(value)));
}

function mixRgb(rgbA, rgbB, factor = 0.5) {
    return [
        clampChannel((rgbA[0] * (1 - factor)) + (rgbB[0] * factor)),
        clampChannel((rgbA[1] * (1 - factor)) + (rgbB[1] * factor)),
        clampChannel((rgbA[2] * (1 - factor)) + (rgbB[2] * factor))
    ];
}

function boostRgb(rgb, boost = 1.08) {
    return rgb.map((value) => clampChannel(value * boost));
}

function darkenRgb(rgb, factor = 0.28) {
    return rgb.map((value) => clampChannel(value * factor));
}

function rgbToCss(rgb, alpha = 1) {
    return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

function getProminentColor(imageUrl) {
    return new Promise((resolve) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d', { willReadFrequently: true });
            const size = 36;
            canvas.width = size;
            canvas.height = size;
            ctx.drawImage(img, 0, 0, size, size);

            const data = ctx.getImageData(0, 0, size, size).data;
            let r = 0, g = 0, b = 0, count = 0;

            for (let i = 0; i < data.length; i += 4) {
                const alpha = data[i + 3];
                if (alpha < 120) continue;
                r += data[i];
                g += data[i + 1];
                b += data[i + 2];
                count++;
            }

            if (!count) {
                resolve('rgba(0, 230, 255, 0.7)');
                return;
            }

            const avg = [clampChannel(r / count), clampChannel(g / count), clampChannel(b / count)];
            const boosted = boostRgb(avg, 1.12);
            resolve(rgbToCss(boosted, 0.7));
        };
        img.onerror = () => resolve('rgba(0, 230, 255, 0.7)');
        img.src = imageUrl;
    });
}

function applyAlbumTheme(imageUrl) {
    return new Promise((resolve) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d', { willReadFrequently: true });
            const size = 32;
            canvas.width = size;
            canvas.height = size;
            ctx.drawImage(img, 0, 0, size, size);

            const pixels = ctx.getImageData(0, 0, size, size).data;
            let left = [0, 0, 0];
            let right = [0, 0, 0];
            let center = [0, 0, 0];
            let leftCount = 0;
            let rightCount = 0;
            let centerCount = 0;

            for (let y = 0; y < size; y++) {
                for (let x = 0; x < size; x++) {
                    const index = ((y * size) + x) * 4;
                    const alpha = pixels[index + 3];
                    if (alpha < 110) continue;
                    const rgb = [pixels[index], pixels[index + 1], pixels[index + 2]];

                    if (x < size / 3) {
                        left[0] += rgb[0];
                        left[1] += rgb[1];
                        left[2] += rgb[2];
                        leftCount++;
                    } else if (x > (size * 2) / 3) {
                        right[0] += rgb[0];
                        right[1] += rgb[1];
                        right[2] += rgb[2];
                        rightCount++;
                    } else {
                        center[0] += rgb[0];
                        center[1] += rgb[1];
                        center[2] += rgb[2];
                        centerCount++;
                    }
                }
            }

            const averageRgb = (sum, count, fallback) => count
                ? [clampChannel(sum[0] / count), clampChannel(sum[1] / count), clampChannel(sum[2] / count)]
                : fallback;

            const leftAvg = averageRgb(left, leftCount, [0, 230, 255]);
            const centerAvg = averageRgb(center, centerCount, leftAvg);
            const rightAvg = averageRgb(right, rightCount, leftAvg);

            const accent = boostRgb(centerAvg, 1.14);
            const secondary = boostRgb(rightAvg, 1.06);
            const deep = darkenRgb(mixRgb(accent, secondary, 0.5), 0.22);

            document.documentElement.style.setProperty('--cover-accent-rgb', accent.join(', '));
            document.documentElement.style.setProperty('--cover-secondary-rgb', secondary.join(', '));
            document.documentElement.style.setProperty('--cover-deep-rgb', deep.join(', '));

            const bgLayerAura = document.getElementById('bgLayerAura');
            const bgLayer = document.getElementById('bgLayer');
            const overlay = document.querySelector('.overlay');

            if (bgLayerAura) {
                bgLayerAura.style.filter = `blur(42px) brightness(0.64) saturate(1.12) drop-shadow(0 0 36px ${rgbToCss(accent, 0.16)})`;
            }
            if (bgLayer) {
                bgLayer.style.filter = `blur(3px) saturate(1.18)`;
            }
            if (overlay) {
                overlay.style.background = `linear-gradient(180deg, ${rgbToCss(deep, 0.4)}, rgba(0,0,0,0.3))`;
            }

            const container = document.querySelector('.album-art-container');
            if (container) {
                container.style.borderColor = rgbToCss(mixRgb(accent, deep, 0.65), 0.12);
                container.style.boxShadow = [
                    `0 24px 58px rgba(0, 0, 0, 0.28)`,
                    `0 0 46px ${rgbToCss(accent, 0.16)}`,
                    `0 0 18px ${rgbToCss(secondary, 0.1)}`
                ].join(', ');
                container.style.filter = `drop-shadow(0 0 18px ${rgbToCss(secondary, 0.12)}) saturate(1.03)`;
                container.style.background = `radial-gradient(circle at 35% 30%, ${rgbToCss(accent, 0.12)}, ${rgbToCss(secondary, 0.06)} 58%, rgba(255,255,255,0.02) 74%)`;
            }

            resolve({
                accent,
                secondary,
                deep
            });
        };
        img.onerror = () => resolve(null);
        img.src = imageUrl;
    });
}

function renderQueuePreview(items = []) {
    const shell = document.getElementById('jamQueueShell');
    const tracklist = document.getElementById('jamQueueTracklist');
    if (!shell || !tracklist) return;

    if (!items.length) {
        shell.classList.add('hidden');
        tracklist.innerHTML = '';
        clearInterval(queueRotateTimer);
        queueRotateTimer = null;
        currentQueueItems = [];
        currentQueueIndex = 0;
        return;
    }

    shell.classList.remove('hidden');
    currentQueueItems = items.slice(0, 4);
    currentQueueIndex = 0;

    const markup = currentQueueItems.map((item) => `
        <div class="jam-queue-item">
            <span class="jam-queue-dot"></span>
            <div class="jam-queue-text">
                <span class="jam-queue-title">${escapeHtml(item.title || 'Faixa')}</span>
                <span class="jam-queue-artist">${escapeHtml(item.artist || '')}</span>
            </div>
        </div>
    `).join('');

    tracklist.innerHTML = markup;
    tracklist.style.transform = 'translateY(0)';

    clearInterval(queueRotateTimer);
    queueRotateTimer = null;

    if (currentQueueItems.length > 1) {
        queueRotateTimer = setInterval(() => {
            currentQueueIndex = (currentQueueIndex + 1) % currentQueueItems.length;
            tracklist.style.transform = `translateY(-${currentQueueIndex * 32}px)`;
        }, 3200);
    }
}

async function fetchQueuePreview() {
    try {
        const response = await fetch(buildApiUrl('/queue-preview'), {
            headers: buildHostHeaders()
        });
        const data = await response.json();
        const items = Array.isArray(data.items) ? data.items : [];
        renderQueuePreview(items);
    } catch (error) {
        console.error('Queue Preview Error:', error);
    }
}

function scheduleLeavingProfiles(profiles = []) {
    leavingProfiles = profiles.map((profile) => ({
        ...profile,
        leaving_token: `${profile.client_id}-${Date.now()}`
    }));

    setTimeout(() => {
        leavingProfiles = [];
        fetchProfiles();
    }, 900);
}

function getJamAccessLockMeta() {
    if (sessionState.allowGuestControls) {
        return {
            icon: '&#128275;',
            label: 'Jam aberta: qualquer convidado pode controlar a musica'
        };
    }
    return {
        icon: '&#128274;',
        label: 'Jam fechada: somente o host pode controlar a musica'
    };
}

function renderProfiles(profiles = []) {
    const stack = document.getElementById('jamProfilesStack');
    const shell = document.getElementById('jamProfiles');
    if (!stack || !shell) return;

    if (!profiles.length) {
        latestJamPresenceCount = 0;
        shell.classList.add('hidden');
        stack.innerHTML = '';
        return;
    }

    shell.classList.remove('hidden');
    const currentClientId = ensureProfileClientId();
    const hostClientId = profiles.host_client_id || '';
    const serverTime = profiles.server_time || Math.floor(Date.now() / 1000);
    const joinedWindow = profiles.joined_recently_window || 30;
    const totalOnline = profiles.total_online || profiles.length;
    latestJamPresenceCount = totalOnline;
    const visibleProfiles = profiles.slice(0, MAX_VISIBLE_PROFILES);
    const hiddenCount = Math.max(0, profiles.length - visibleProfiles.length);
    const presenceLabel = totalOnline === 1 ? '1 na jam' : `${totalOnline} na jam`;
    const currentProfileIds = new Set(profiles.map((profile) => profile.client_id));
    const removedProfiles = [];

    lastRenderedProfileMap.forEach((profile, clientId) => {
        if (!currentProfileIds.has(clientId)) {
            removedProfiles.push(profile);
        }
    });

    if (removedProfiles.length) {
        scheduleLeavingProfiles(removedProfiles);
    }

    const chipsMarkup = visibleProfiles.map((profile) => {
        const name = (profile.name || 'Convidado').trim();
        const safeName = escapeHtml(name);
        const initials = getProfileInitials(name);
        const isSelf = profile.client_id === currentClientId ? ' is-self' : '';
        const isHost = profile.client_id === hostClientId ? ' is-host' : '';
        const isFresh = (serverTime - (profile.updated_at || 0)) <= joinedWindow ? ' is-fresh' : '';
        const isBurst = profile.client_id === profileBurstClientId && Date.now() < profileBurstUntil ? ' is-burst' : '';
        const lockMeta = isHost ? getJamAccessLockMeta() : null;
        const avatarMarkup = profile.avatar
            ? `<img class="jam-profile-avatar" src="${profile.avatar}" alt="${safeName}">`
            : `<div class="jam-profile-fallback">${initials}</div>`;

        return `
            <div class="jam-profile-chip${isSelf}${isHost}${isFresh}${isBurst}" title="${safeName}">
                ${lockMeta ? `
                    <span class="jam-profile-lock-badge" aria-label="${escapeHtml(lockMeta.label)}">
                        <span class="jam-profile-lock-icon">${lockMeta.icon}</span>
                        <span class="jam-profile-lock-tooltip">${escapeHtml(lockMeta.label)}</span>
                    </span>
                ` : ''}
                ${avatarMarkup}
                <span class="jam-profile-name">${safeName}</span>
            </div>
        `;
    }).join('');

    const overflowMarkup = hiddenCount > 0
        ? `
            <div class="jam-profile-chip jam-profile-overflow" title="+${hiddenCount} perfis">
                <div class="jam-profile-fallback">+${hiddenCount}</div>
                <span class="jam-profile-name">+${hiddenCount} pessoas na jam</span>
            </div>
        `
        : '';

    const leavingMarkup = leavingProfiles.map((profile) => {
        const name = escapeHtml((profile.name || 'Convidado').trim());
        const initials = getProfileInitials(profile.name || '');
        const avatarMarkup = profile.avatar
            ? `<img class="jam-profile-avatar" src="${profile.avatar}" alt="${name}">`
            : `<div class="jam-profile-fallback">${initials}</div>`;

        return `
            <div class="jam-profile-chip is-leaving" title="${name}">
                ${avatarMarkup}
                <span class="jam-profile-name">${name}</span>
            </div>
        `;
    }).join('');

    stack.innerHTML = `<div class="jam-presence-pill">${presenceLabel}</div>${chipsMarkup}${overflowMarkup}${leavingMarkup}`;
    lastRenderedProfileMap = new Map(profiles.map((profile) => [profile.client_id, profile]));
}

async function fetchProfiles() {
    try {
        const response = await fetch(buildApiUrl('/profiles'), {
            headers: buildHostHeaders()
        });
        const data = await response.json();
        const profiles = Array.isArray(data.profiles) ? data.profiles : [];
        if (profiles.length) {
            profiles.host_client_id = data.host_client_id || '';
            profiles.total_online = data.total_online || profiles.length;
            profiles.joined_recently_window = data.joined_recently_window || 30;
            profiles.server_time = data.server_time || Math.floor(Date.now() / 1000);
        }
        renderProfiles(profiles);
    } catch (error) {
        console.error('Profiles Load Error:', error);
        renderProfiles([]);
    }
}

function updateProfilePreview(name = '', photoDataUrl = '') {
    const initials = document.getElementById('profileInitials');
    const avatar = document.getElementById('profileAvatar');
    const preview = document.getElementById('profilePreview');
    if (!initials || !avatar || !preview) return;

    const computedInitials = getProfileInitials(name);

    initials.innerText = computedInitials;
    if (photoDataUrl) {
        avatar.src = photoDataUrl;
        avatar.classList.remove('hidden');
        initials.classList.add('hidden');
        preview.classList.remove('is-empty');
    } else {
        avatar.removeAttribute('src');
        avatar.classList.add('hidden');
        initials.classList.remove('hidden');
        preview.classList.add('is-empty');
    }
}

function loadStoredProfile() {
    const storedName = localStorage.getItem(PROFILE_NAME_KEY) || '';
    const storedPhoto = localStorage.getItem(PROFILE_PHOTO_KEY) || '';
    const nameInput = document.getElementById('profileNameInput');
    if (nameInput) {
        nameInput.value = storedName;
    }
    updateProfilePreview(storedName, storedPhoto);
}

function hasStoredProfileName() {
    return !!(localStorage.getItem(PROFILE_NAME_KEY) || '').trim();
}

async function restoreStoredProfileFromServer() {
    const clientId = ensureProfileClientId();
    const guestToken = getStoredGuestToken();
    const hasName = !!(localStorage.getItem(PROFILE_NAME_KEY) || '').trim();
    const hasPhoto = !!(localStorage.getItem(PROFILE_PHOTO_KEY) || '').trim();

    if (hasName && hasPhoto) {
        return false;
    }

    try {
        const params = new URLSearchParams();
        if (guestToken) {
            params.set('guest_token', guestToken);
        } else {
            params.set('client_id', clientId);
        }
        const response = await fetch(`${buildApiUrl('/profiles/restore')}?${params.toString()}`, {
            headers: buildHostHeaders()
        });
        const payload = await response.json();
        const profile = payload?.profile;
        if (!response.ok || !profile) {
            return false;
        }

        const restoredName = (profile.name || '').trim();
        const restoredAvatar = (profile.avatar || '').trim();

        if (restoredName && !hasName) {
            localStorage.setItem(PROFILE_NAME_KEY, restoredName);
        }
        if (restoredAvatar && !hasPhoto) {
            localStorage.setItem(PROFILE_PHOTO_KEY, restoredAvatar);
        }
        storeGuestIdentity(profile.guest_token || '', profile.recovery_code || '');

        loadStoredProfile();
        updateJamInviteToast();
        return !!(restoredName || restoredAvatar);
    } catch (error) {
        return false;
    }
}

function maybePromptProfileSetup() {
    if (hasStoredProfileName()) return;
    scheduleJamInviteToast(2800);
}

function shouldShowJamInviteToast() {
    if (hasStoredProfileName()) return false;
    if (isSetupMode || !latestSpotifyIsPlaying) return false;
    return true;
}

function scheduleJamInviteToast(delayMs = 2600) {
    clearTimeout(jamInviteToastTimer);
    jamInviteToastTimer = setTimeout(() => {
        jamInviteToastTimer = null;
        updateJamInviteToast();
    }, delayMs);
}

function updateJamInviteToast() {
    const toast = document.getElementById('jamInviteToast');
    if (!toast) return;
    const shouldShow = shouldShowJamInviteToast();
    if (!shouldShow) {
        toast.classList.add('hidden');
        toast.classList.remove('is-visible');
        jamInviteToastVisible = false;
        return;
    }
    if (!jamInviteToastVisible) {
        toast.classList.remove('hidden');
        toast.classList.remove('is-visible');
        requestAnimationFrame(() => {
            toast.classList.add('is-visible');
        });
        jamInviteToastVisible = true;
        return;
    }
    toast.classList.remove('hidden');
}

function saveProfileLocally() {
    const nameInput = document.getElementById('profileNameInput');
    const photoInput = document.getElementById('profilePhotoInput');
    const name = (nameInput?.value || '').trim();
    const existingPhoto = localStorage.getItem(PROFILE_PHOTO_KEY) || '';
    const file = photoInput?.files?.[0];

    localStorage.setItem(PROFILE_NAME_KEY, name);
    ensureProfileClientId();

    return new Promise((resolve) => {
        if (file) {
            const reader = new FileReader();
            reader.onload = () => {
                const dataUrl = typeof reader.result === 'string' ? reader.result : '';
                localStorage.setItem(PROFILE_PHOTO_KEY, dataUrl);
                updateProfilePreview(name, dataUrl);
                resolve({ name, avatar: dataUrl });
            };
            reader.readAsDataURL(file);
            return;
        }

        updateProfilePreview(name, existingPhoto);
        resolve({ name, avatar: existingPhoto });
    });
}

function clearStoredProfilePhoto() {
    localStorage.removeItem(PROFILE_PHOTO_KEY);
    const photoInput = document.getElementById('profilePhotoInput');
    if (photoInput) {
        photoInput.value = '';
    }
    const currentName = (localStorage.getItem(PROFILE_NAME_KEY) || document.getElementById('profileNameInput')?.value || '').trim();
    updateProfilePreview(currentName, '');
}

async function syncStoredProfileToServer() {
    const name = (localStorage.getItem(PROFILE_NAME_KEY) || '').trim();
    if (!name) {
        await fetchProfiles();
        return false;
    }

    try {
        const response = await fetch(buildApiUrl('/profiles'), {
            method: 'POST',
            headers: buildHostHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                client_id: ensureProfileClientId(),
                guest_token: getStoredGuestToken(),
                name,
                avatar: localStorage.getItem(PROFILE_PHOTO_KEY) || ''
            })
        });
        const data = await response.json();
        if (!response.ok || data.status !== 'OK') {
            throw new Error(data.message || 'Erro ao salvar perfil');
        }
        storeGuestIdentity(data.guest_token || '', data.recovery_code || '');
        profileBurstClientId = ensureProfileClientId();
        profileBurstUntil = Date.now() + 2400;
        await fetchProfiles();
        updateJamInviteToast();
        return true;
    } catch (error) {
        console.error('Profile Sync Error:', error);
        return false;
    }
}

async function loadServerConfig() {
    try {
        const response = await fetch(buildApiUrl('/config'), {
            headers: buildHostHeaders()
        });
        const data = await response.json();
        document.getElementById('clientIdInput').value = data.CLIENT_ID || '';
        document.getElementById('clientSecretInput').value = data.CLIENT_SECRET || '';
        document.getElementById('ytKeyInput').value = data.YOUTUBE_API_KEY || '';
        sessionState.publicBaseUrl = (data.PUBLIC_BASE_URL || '').trim();
        const guestControlToggle = document.getElementById('guestControlToggle');
        if (guestControlToggle) {
            guestControlToggle.checked = !!data.ALLOW_GUEST_CONTROLS;
        }
        updateShareLinks();
    } catch (error) {
        console.error('Config Load Error:', error);
    }
}

function showSetupMessage(message, isError = true) {
    const errorMsg = document.getElementById('setupError');
    if (!errorMsg) return;

    errorMsg.innerText = message;
    errorMsg.classList.remove('hidden');
    errorMsg.style.color = isError ? '#ffb5b5' : '#aff8d3';
    errorMsg.style.background = isError ? 'rgba(255,85,85,0.12)' : 'rgba(29,185,84,0.14)';
}

function setLyricVisibility(hasActiveLyric) {
    const container = document.querySelector('.lyrics-display');
    if (!container) return;
    container.classList.toggle('is-empty', !hasActiveLyric);
    container.classList.toggle('has-lyric', !!hasActiveLyric);
    if (!hasActiveLyric) {
        container.classList.remove('is-translated');
    }
}

function setLyricsFeedbackState(message, isPositive = false) {
    const sourceText = document.getElementById('lyricsSourceText');
    const likeBtn = document.getElementById('lyricsLikeBtn');
    if (!sourceText) return;

    clearTimeout(lyricsFeedbackTimeout);
    sourceText.innerText = message;

    if (likeBtn) {
        likeBtn.classList.toggle('is-active', isPositive);
    }

    lyricsFeedbackTimeout = setTimeout(() => {
        refreshLyricsControls();
        if (likeBtn) {
            likeBtn.classList.remove('is-active');
        }
    }, 1400);
}

function updateTrackHandoffState(data) {
    const durationMs = Number(data?.duration_ms || 0);
    const progressMs = Number(data?.progress_ms || 0);
    const isPlayingNow = !!data?.is_playing;
    const remainingMs = Math.max(0, durationMs - progressMs);
    const shouldActivate = isPlayingNow && remainingMs > 0 && remainingMs <= 4500 && !isSwapping;
    const shouldIntensify = shouldActivate && remainingMs <= 1400;
    document.body.classList.toggle('is-track-handoff', shouldActivate);
    document.body.classList.toggle('is-track-handoff-late', shouldIntensify);
}

function refreshLyricsControlsLegacy() {
    const sourceText = document.getElementById('lyricsSourceText');
    const likeBtn = document.getElementById('lyricsLikeBtn');
    const dislikeBtn = document.getElementById('lyricsDislikeBtn');
    const resetBtn = document.getElementById('lyricsResetBtn');
    const translateBtn = document.getElementById('lyricsTranslateBtn');
    const artist = document.getElementById('trackArtist')?.innerText || '';
    const track = document.getElementById('trackTitle')?.innerText || '';
    const state = Lyrics.getLyricsUiState();

    if (sourceText) {
        sourceText.innerText = state.isTranslated ? `${state.sourceLabel} · PT` : state.sourceLabel;
    }

    if (likeBtn) {
        likeBtn.disabled = !state.canLike;
        likeBtn.classList.remove('is-active');
        likeBtn.classList.toggle('is-glow', Lyrics.isCurrentLyricsLiked(artist, track));
    }

    if (dislikeBtn) {
        dislikeBtn.disabled = !state.canDislike;
    }

    if (resetBtn) {
        resetBtn.disabled = !state.totalCandidates;
    }

    if (translateBtn) {
        translateBtn.disabled = !state.canTranslate;
        translateBtn.classList.toggle('is-active', !!state.isTranslated);
        translateBtn.setAttribute('title', state.isTranslated ? 'Tradução ativa' : 'Traduzir letra');
        translateBtn.setAttribute('aria-pressed', state.isTranslated ? 'true' : 'false');
    }

    const lyricDisplay = document.querySelector('.lyrics-display');
    if (lyricDisplay) {
        lyricDisplay.classList.toggle('is-favorite', Lyrics.isCurrentLyricsLiked(artist, track));
    }
}

function refreshLyricsControls() {
    const sourceText = document.getElementById('lyricsSourceText');
    const sourcePill = document.getElementById('lyricsSourcePill');
    const likeBtn = document.getElementById('lyricsLikeBtn');
    const dislikeBtn = document.getElementById('lyricsDislikeBtn');
    const resetBtn = document.getElementById('lyricsResetBtn');
    const translateBtn = document.getElementById('lyricsTranslateBtn');
    const artist = document.getElementById('trackArtist')?.innerText || '';
    const track = document.getElementById('trackTitle')?.innerText || '';
    const state = Lyrics.getLyricsUiState();
    const hasPreviewTranslation = !!(state.hasCachedTranslation && !state.hasFullTranslation);

    if (sourceText) {
        if (state.isTranslated && hasPreviewTranslation) {
            sourceText.innerText = `${state.sourceLabel} | PT-BR no começo`;
        } else if (state.isTranslating && !state.hasCachedTranslation) {
            sourceText.innerText = `${state.sourceLabel} | PT-BR entrando...`;
        } else if (state.isTranslating && state.hasCachedTranslation) {
            sourceText.innerText = `${state.sourceLabel} | PT-BR completando...`;
        } else {
            sourceText.innerText = state.isTranslated ? `${state.sourceLabel} | PT-BR` : state.sourceLabel;
        }
    }

    if (sourcePill) {
        sourcePill.classList.toggle('is-translated', !!state.isTranslated);
        sourcePill.classList.toggle('is-translation-pending', !!(state.isTranslating && !state.hasCachedTranslation));
        sourcePill.classList.toggle('is-preview-ready', !!(state.isTranslated && hasPreviewTranslation));
        sourcePill.setAttribute(
            'title',
            state.isTranslated
                ? (hasPreviewTranslation ? 'Tradução do começo ja pronta em PT-BR' : 'Tradução PT-BR ativa')
                : (state.isTranslating ? 'Tradução PT-BR em preparacao' : 'Fonte atual da letra')
        );
    }

    if (likeBtn) {
        likeBtn.disabled = !state.canLike;
        likeBtn.classList.remove('is-active');
        likeBtn.classList.toggle('is-glow', Lyrics.isCurrentLyricsLiked(artist, track));
    }

    if (dislikeBtn) {
        dislikeBtn.disabled = !state.canDislike;
    }

    if (resetBtn) {
        resetBtn.disabled = !state.totalCandidates;
    }

    if (translateBtn) {
        translateBtn.disabled = !state.canTranslate;
        translateBtn.classList.toggle('is-active', !!state.isTranslated);
        translateBtn.classList.toggle('is-loading', !!state.isTranslating);
        translateBtn.classList.toggle('is-preview-ready', !!(state.isTranslated && hasPreviewTranslation));
        translateBtn.setAttribute(
            'title',
            state.isTranslating
                ? (state.hasCachedTranslation ? 'Completando traducao PT-BR...' : 'Preparando traducao PT-BR...')
                : (state.isTranslated
                    ? (hasPreviewTranslation ? 'PT-BR no começo da musica' : 'Tradução PT-BR ativa')
                    : 'Traduzir letra para PT-BR')
        );
        translateBtn.setAttribute('aria-pressed', state.isTranslated ? 'true' : 'false');
        translateBtn.setAttribute('aria-busy', state.isTranslating ? 'true' : 'false');
    }

    const lyricDisplay = document.querySelector('.lyrics-display');
    if (lyricDisplay) {
        lyricDisplay.classList.toggle('is-favorite', Lyrics.isCurrentLyricsLiked(artist, track));
    }
}

function setTranslationPendingUi(isPending) {
    const sourceText = document.getElementById('lyricsSourceText');
    const sourcePill = document.getElementById('lyricsSourcePill');
    const translateBtn = document.getElementById('lyricsTranslateBtn');

    if (translateBtn) {
        translateBtn.classList.toggle('is-loading', !!isPending);
        translateBtn.classList.toggle('is-preview-ready', false);
        translateBtn.setAttribute('aria-busy', isPending ? 'true' : 'false');
        if (isPending) {
            translateBtn.setAttribute('title', 'Preparando traducao PT-BR...');
        }
    }

    if (sourcePill) {
        sourcePill.classList.toggle('is-translation-pending', !!isPending);
        if (!isPending) {
            sourcePill.classList.remove('is-preview-ready');
        }
    }

    if (sourceText && isPending) {
        const state = Lyrics.getLyricsUiState();
        sourceText.innerText = `${state.sourceLabel} | PT-BR entrando...`;
    }
}
function refreshCurrentLyricFrame() {
    const lyricEl = document.getElementById('currentLyric');
    if (lyricEl) {
        lyricEl.dataset.current = "__refresh__";
    }
    syncEngine.handleLyricSync(getLyricsPlaybackTime());
}

function bindInstantPressFeedback(targets) {
    targets.forEach((target) => {
        if (!target) return;

        const addPress = () => {
            if (!target.disabled) {
                target.classList.add('is-pressing');
            }
        };
        const clearPress = () => target.classList.remove('is-pressing');

        target.addEventListener('pointerdown', addPress);
        target.addEventListener('pointerup', clearPress);
        target.addEventListener('pointerleave', clearPress);
        target.addEventListener('pointercancel', clearPress);
        target.addEventListener('blur', clearPress);
    });
}

const syncEngine = {
    async checkStatus() {
        if (statusRequestInFlight) {
            return;
        }
        statusRequestInFlight = true;
        try {
            const response = await fetch(buildApiUrl('/status'), {
                headers: buildHostHeaders()
            });
            const data = await response.json();
            updateSpotifyClockState(data);
            const effectiveIsPlaying = data.is_playing && !isLocalPausePending();

            const statusText = document.getElementById('statusText');
            const statusIcon = document.getElementById('connectionStatus');
            const setupModal = document.getElementById('setupModal');
            const presenceLabel = getJamPresenceLabel();
            const roleLabel = sessionState.isHost ? 'Host local' : 'Convidado na sala';
            const controlLabel = sessionState.isHost
                ? (sessionState.allowGuestControls ? 'controles liberados' : 'host no comando')
                : (sessionState.canControl ? 'controles liberados' : 'host no comando');
            ensureStatusMetaNode();

            if (data.status === "SETUP_REQUIRED") {
                if (sessionState.isHost && !isSetupMode) {
                    isSetupMode = true;
                    openSetupModal('api');
                    statusText.innerText = "Configuração Necessária";
                    statusIcon.style.color = "#ffaa00";
                } else if (!sessionState.isHost) {
                    statusText.innerText = "Host configurando a jam";
                    statusIcon.style.color = "#ffaa00";
                }
                const statusMeta = ensureStatusMetaNode();
                if (statusMeta) {
                    statusMeta.innerText = sessionState.isHost
                        ? "Host local · conecte Spotify e YouTube para liberar a jam"
                        : "A sala libera assim que o host concluir as conexões";
                }
                document.querySelector('.server-monitor')?.setAttribute('data-state', 'setup');
                if (isSetupSyncRetryActive()) {
                    scheduleStatusPoll(320);
                }
                return;
            } else if (isSetupMode) {
                isSetupMode = false;
                setupModal.classList.add('hidden');
            }

            if (isWaitingForSync) {
                statusText.innerText = "Sincronizando...";
                statusIcon.style.color = "#ffdd00";
            } else if (document.body.classList.contains('is-track-handoff-late')) {
                statusText.innerText = "Entrada iminente";
                statusIcon.style.color = "#7dffcb";
            } else if (document.body.classList.contains('is-track-handoff')) {
                statusText.innerText = "Preparando próxima faixa";
                statusIcon.style.color = "#7fffd4";
            } else if (effectiveIsPlaying) {
                statusText.innerText = (!sessionState.isHost && !sessionState.canControl)
                    ? "Jam ao vivo · controles bloqueados"
                    : "Jam ao vivo";
                statusIcon.style.color = "#00e6ff";
            } else {
                statusText.innerText = (!sessionState.isHost && !sessionState.canControl)
                    ? "Host bloqueou os controles"
                    : "Player Pausado";
                statusIcon.style.color = "#ffaa00";
            }

            if (data.status === "SETUP_REQUIRED") {
                if (sessionState.isHost) {
                    setJamStatus("Configuração necessária", "Host local · conecte Spotify e YouTube para liberar a jam", "#ffaa00", "setup");
                } else {
                    setJamStatus("Host configurando a jam", "A sala libera assim que o host concluir as conexões", "#ffaa00", "setup");
                }
            } else if (isWaitingForSync) {
                setJamStatus("Sincronizando...", `${roleLabel} · alinhando player, tempo e letras`, "#ffdd00", "sync");
            } else if (document.body.classList.contains('is-track-handoff-late')) {
                setJamStatus("Entrada iminente", `${presenceLabel} · a próxima faixa já está assumindo`, "#7dffcb", "handoff");
            } else if (document.body.classList.contains('is-track-handoff')) {
                setJamStatus("Preparando próxima faixa", `${presenceLabel} · troca suave em andamento`, "#7fffd4", "handoff");
            } else if (effectiveIsPlaying) {
                const mainText = (!sessionState.isHost && !sessionState.canControl)
                    ? "Jam ao vivo · controles bloqueados"
                    : "Jam ao vivo";
                setJamStatus(mainText, `${roleLabel} · ${presenceLabel} · ${controlLabel}`, "#00e6ff", "live");
            } else {
                const mainText = (!sessionState.isHost && !sessionState.canControl)
                    ? "Host bloqueou os controles"
                    : "Player pausado";
                setJamStatus(mainText, `${roleLabel} · ${presenceLabel} · aguardando retomada`, "#ffaa00", "paused");
            }

            const inactivePlayer = (Player.playerAtivo === Player.player1) ? Player.player2 : Player.player1;
            pendingVideoId = data.videoId || pendingVideoId;
            const incomingTrackKey = `${data.artist || ""}-${data.title || ""}`;

            if (
                incomingTrackKey &&
                currentTrackKey &&
                incomingTrackKey !== currentTrackKey &&
                !data.videoId &&
                !isSwapping
            ) {
                latestServerTrackKey = incomingTrackKey;
                isWaitingForSync = true;
                if (!isUnresolvedTrackGraceActive(incomingTrackKey)) {
                    openUnresolvedTrackGrace(incomingTrackKey, 900);
                } else {
                    clearDriftCorrection();
                    if (Player.playerAtivo) {
                        try {
                            if (typeof Player.playerAtivo.mute === 'function') {
                                Player.playerAtivo.mute();
                            }
                            if (typeof Player.playerAtivo.pauseVideo === 'function') {
                                Player.playerAtivo.pauseVideo();
                            }
                        } catch (e) {}
                    }
                }
                scheduleStatusPoll(120);
            }

            if (data.videoId === currentVideoId && !isSwapping) {
                if (data.nextVideoId && data.nextVideoId !== preCachedVideoId && inactivePlayer && typeof inactivePlayer.cueVideoById === 'function') {
                    console.log("Pre-cache preparado no player inativo:", data.nextVideoId);
                    inactivePlayer.cueVideoById({
                        videoId: data.nextVideoId,
                        suggestedQuality: 'small'
                    });
                    preCachedVideoId = data.nextVideoId;
                }
            }

            if (isSwapping && data.videoId && activeSwapVideoId && data.videoId !== activeSwapVideoId) {
                pendingVideoId = data.videoId;
                scheduleStatusPoll(120);
            }

            if (data.videoId && data.videoId !== currentVideoId && !isSwapping) {
                clearUnresolvedTrackGrace();
                const proxPlayer = inactivePlayer;
                const antigoPlayer = Player.playerAtivo;
                const isInitialHydrationSwap = !currentVideoId;
                latestServerTrackKey = incomingTrackKey;
                if (isInitialHydrationSwap) {
                    debugHydrationSync('start', {
                        videoId: data.videoId,
                        progressMs: Number(data.progress_ms || 0),
                        durationMs: Number(data.duration_ms || 0),
                        isPlaying: !!effectiveIsPlaying
                    });
                }

                if (!proxPlayer || typeof proxPlayer.loadVideoById !== 'function') {
                    isSwapping = false;
                    scheduleStatusPoll(300);
                    return;
                }

                isSwapping = true;
                activeSwapVideoId = data.videoId;
                scheduleStatusPoll(120);

                console.log("Trocando vídeo para:", data.videoId);

                if (antigoPlayer) {
                    if (typeof antigoPlayer.mute === 'function') {
                        try { antigoPlayer.mute(); } catch (e) {}
                    }
                    if (typeof antigoPlayer.stopVideo === 'function') {
                        try { antigoPlayer.stopVideo(); } catch (e) {}
                    } else if (typeof antigoPlayer.pauseVideo === 'function') {
                        try { antigoPlayer.pauseVideo(); } catch (e) {}
                    }
                }

                const trackKey = `${data.artist}-${data.title}`;
                if (currentTrackKey !== trackKey) {
                    currentTrackKey = trackKey;
                    Lyrics.resetLyrics();
                    document.getElementById('currentLyric').innerText = "";
                    document.getElementById('currentLyric').dataset.current = "";
                    document.getElementById('translatedLyric').innerText = "";
                    setLyricVisibility(false);
                    refreshLyricsControls();
                    Lyrics.fetchLyrics(data.artist, data.title)
                        .finally(() => {
                            refreshLyricsControls();
                        });
                }

                if (proxPlayer && typeof proxPlayer.setVolume === 'function' && !audioUnlocked) {
                    proxPlayer.setVolume(0);
                }

                const COMPENSATION_DELAY = SYNC_COMPENSATION_DELAY;
                const spotifyProgressSeconds = Math.max(0, Number(data.progress_ms || 0) / 1000);

                const targetTime = Math.max(0, spotifyProgressSeconds + COMPENSATION_DELAY);
                const shouldPlayNow = !!effectiveIsPlaying;
                const shouldForceInitialSeek = isInitialHydrationSwap && shouldPlayNow;
                if (isInitialHydrationSwap) {
                    clearHydrationSyncBurst();
                }
                if (shouldPlayNow) {
                    isWaitingForSync = true;
                } else {
                    isWaitingForSync = false;
                }

                const executeSwap = () => {
                    if (pendingVideoId && pendingVideoId !== data.videoId) {
                        try {
                            if (proxPlayer && typeof proxPlayer.stopVideo === 'function') {
                                proxPlayer.stopVideo();
                            }
                        } catch (e) {}
                        isSwapping = false;
                        activeSwapVideoId = "";
                        scheduleStatusPoll(60);
                        return;
                    }

                    if (proxPlayer) {
                        const playerStateBefore = typeof proxPlayer.getPlayerState === 'function'
                            ? proxPlayer.getPlayerState()
                            : null;
                        const playerTimeBefore = typeof proxPlayer.getCurrentTime === 'function'
                            ? proxPlayer.getCurrentTime()
                            : null;
                        if (!audioUnlocked && typeof proxPlayer.mute === 'function') {
                            proxPlayer.mute();
                        } else if (audioUnlocked) {
                            if (typeof proxPlayer.unMute === 'function') proxPlayer.unMute();
                            if (typeof proxPlayer.setVolume === 'function') {
                                proxPlayer.setVolume(getCurrentVolume());
                            }
                        }

                        Player.setPlayerAtivo(proxPlayer);
                        currentVideoId = data.videoId;
                        pendingVideoId = data.videoId;
                        openSyncAssistWindow(2600);
                        forceVisibleYoutubeToCurrentTrack();

                        if (typeof proxPlayer.seekTo === 'function') {
                            try {
                                proxPlayer.seekTo(targetTime, true);
                            } catch (e) {}
                        }

                        if (shouldForceInitialSeek) {
                            openSyncAssistWindow(3200);
                            armHydrationSyncBurst(3);
                            performHardSeek(targetTime, 0);
                            scheduleHydrationSeekReinforcement(proxPlayer, targetTime);
                        }

                        if (shouldPlayNow && typeof proxPlayer.playVideo === 'function') {
                            proxPlayer.playVideo();
                        } else if (!shouldPlayNow && typeof proxPlayer.pauseVideo === 'function') {
                            proxPlayer.pauseVideo();
                            isWaitingForSync = false;
                            clearHydrationSyncBurst();
                        }

                        if (isInitialHydrationSwap) {
                            setTimeout(() => {
                                const playerStateAfter = typeof proxPlayer.getPlayerState === 'function'
                                    ? proxPlayer.getPlayerState()
                                    : null;
                                const playerTimeAfter = typeof proxPlayer.getCurrentTime === 'function'
                                    ? proxPlayer.getCurrentTime()
                                    : null;
                                debugHydrationSync('done', {
                                    targetTime,
                                    playerStateBefore,
                                    playerTimeBefore,
                                    playerStateAfter,
                                    playerTimeAfter,
                                    waitingForSync: isWaitingForSync
                                });
                            }, 320);
                        }

                        if (antigoPlayer && typeof antigoPlayer.stopVideo === 'function') {
                            antigoPlayer.stopVideo();
                        }
                        isSwapping = false;
                        activeSwapVideoId = "";
                    } else {
                        isSwapping = false;
                        activeSwapVideoId = "";
                    }
                };

                if (preCachedVideoId === data.videoId) {
                    console.log("[GAPLESS] Transition Instantânea Acionada!");
                    proxPlayer.seekTo(targetTime, true);
                    executeSwap();
                } else {
                    if (shouldPlayNow) {
                        proxPlayer.loadVideoById({
                            videoId: data.videoId,
                            startSeconds: targetTime,
                            suggestedQuality: 'small'
                        });
                    } else if (typeof proxPlayer.cueVideoById === 'function') {
                        proxPlayer.cueVideoById({
                            videoId: data.videoId,
                            startSeconds: targetTime,
                            suggestedQuality: 'small'
                        });
                    } else {
                        proxPlayer.loadVideoById({
                            videoId: data.videoId,
                            startSeconds: targetTime,
                            suggestedQuality: 'small'
                        });
                    }
                    await waitForSwapPrime(
                        proxPlayer,
                        targetTime,
                        isInitialHydrationSwap ? 900 : (shouldPlayNow ? 260 : 220)
                    );
                    executeSwap();
                }

                preCachedVideoId = "";
                fetchArtistContext(true);
            }

            const COMPENSATION_DELAY = SYNC_COMPENSATION_DELAY;
            const baseSpotifyCurrent = Math.max(0, Number(data.progress_ms || 0) / 1000) + COMPENSATION_DELAY;
            const spotifyCurrent = Math.max(0, baseSpotifyCurrent);
            const ytCurrent = (Player.playerAtivo && typeof Player.playerAtivo.getCurrentTime === 'function') ? Player.playerAtivo.getCurrentTime() : 0;
            const ytDuration = (Player.playerAtivo && typeof Player.playerAtivo.getDuration === 'function') ? Player.playerAtivo.getDuration() : 0;
            const jumpDiff = Math.abs(ytCurrent - spotifyCurrent);
            const remainingTrackSeconds = Math.max(0, (Number(data.duration_ms || 0) - Number(data.progress_ms || 0)) / 1000);
            const localRemainingTrackSeconds = ytDuration > 0 ? Math.max(0, ytDuration - ytCurrent) : 0;
            const currentPlayerState = (Player.playerAtivo && typeof Player.playerAtivo.getPlayerState === 'function')
                ? Player.playerAtivo.getPlayerState()
                : null;
            const isEndingCurrentTrack = currentPlayerState === YT.PlayerState.ENDED && remainingTrackSeconds <= 2.8;
            const isNearTrackHandoff =
                (remainingTrackSeconds > 0 && remainingTrackSeconds <= 3.4)
                || (localRemainingTrackSeconds > 0 && localRemainingTrackSeconds <= 2.6);

            if (!effectiveIsPlaying && !isWaitingForSync && Player.playerAtivo) {
                pauseDetectionCount += 1;
                clearDriftCorrection();
                if (
                    pauseDetectionCount >= 2 &&
                    currentPlayerState === YT.PlayerState.PLAYING &&
                    typeof Player.playerAtivo.pauseVideo === 'function'
                ) {
                    Player.playerAtivo.pauseVideo();
                }
            } else if (effectiveIsPlaying && !isWaitingForSync && Player.playerAtivo) {
                pauseDetectionCount = 0;
                if (
                    !isNearTrackHandoff &&
                    !isEndingCurrentTrack &&
                    currentPlayerState !== YT.PlayerState.PLAYING &&
                    currentPlayerState !== YT.PlayerState.BUFFERING
                ) {
                    forceVisibleYoutubeToCurrentTrack();
                    prepareActivePlayerAudio();
                    if (typeof Player.playerAtivo.playVideo === 'function') {
                        Player.playerAtivo.playVideo();
                    }
                }
            }

            if (effectiveIsPlaying && !isWaitingForSync && !isEndingCurrentTrack && !isNearTrackHandoff) {
                const driftSeconds = spotifyCurrent - ytCurrent;
                if (isSyncAssistActive()) {
                    const correctedByRate = applySubtleDriftCorrection(driftSeconds, true);
                    if (!correctedByRate && jumpDiff > DRIFT_RATE_HARD_LIMIT) {
                        clearDriftCorrection();
                        performHardSeek(spotifyCurrent, 6000);
                    }
                } else if (jumpDiff > DRIFT_EMERGENCY_SEEK) {
                    clearDriftCorrection();
                    performHardSeek(spotifyCurrent, 12000);
                } else if (jumpDiff > DRIFT_IGNORE_ZONE) {
                    const correctedByRate = applySubtleDriftCorrection(driftSeconds, false);
                    if (!correctedByRate) {
                        clearDriftCorrection();
                    }
                } else {
                    clearDriftCorrection();
                }
            } else {
                clearDriftCorrection();
            }

            applyVariantTrackFade(Number(data.duration_ms || 0) - Number(data.progress_ms || 0));

            if (isWaitingForSync && effectiveIsPlaying) {
                pauseDetectionCount = 0;
                clearDriftCorrection();
                if (Player.playerAtivo && typeof Player.playerAtivo.seekTo === 'function') {
                    openSyncAssistWindow(2800);
                    const seekApplied = performHardSeek(spotifyCurrent, 0);
                    forceVisibleYoutubeToCurrentTrack();

                    const currentVol = document.getElementById('volumeRange').value;
                    if (audioUnlocked) {
                        Player.playerAtivo.unMute();
                        Player.playerAtivo.setVolume(currentVol);
                    }
                    Player.playerAtivo.playVideo();

                    if (seekApplied || jumpDiff <= 1.2) {
                        isWaitingForSync = false;
                        clearHydrationSyncBurst();
                        const icons = document.getElementById('playPauseBtn');
                        if (icons) {
                            icons.querySelector('#playIcon').classList.add('hidden');
                            icons.querySelector('#pauseIcon').classList.remove('hidden');
                            icons.querySelector('#btnLoading').classList.add('hidden');
                        }
                    } else {
                        scheduleStatusPoll(120);
                    }
                }
            }

            updateTrackHandoffState(data);
            if (sessionState.isHost && effectiveIsPlaying && !!data.videoId && !audioUnlocked) {
                showSpotifyResumePrompt('playback');
            } else if (audioUnlocked || !effectiveIsPlaying) {
                document.getElementById('spotifyResumePrompt')?.classList.add('hidden');
            }
            this.updateUI(data);
            if (isSetupSyncRetryActive()) {
                const hasResolvedPausedState = !effectiveIsPlaying && !!(data.track_id || data.title || data.artist);
                const hasResolvedPlayingState = !!data.videoId && currentVideoId === data.videoId && !isWaitingForSync;
                if (hasResolvedPausedState || hasResolvedPlayingState) {
                    clearSetupSyncRetryWindow();
                }
            }

            if (!incomingTrackKey || incomingTrackKey === currentTrackKey || data.videoId) {
                clearUnresolvedTrackGrace();
            }
        } catch (e) {
            console.error("Sync Loop Error:", e);
        } finally {
            statusRequestInFlight = false;
            scheduleStatusPoll();
            if (hydrationSyncBurstRemaining > 0) {
                hydrationSyncBurstRemaining -= 1;
            }
        }
    },

    handleLyricSync(currentTime) {
        const lyricEl = document.getElementById('currentLyric');
        const translatedEl = document.getElementById('translatedLyric');
        const activeLine = Lyrics.getActiveOriginalLyricAtTime(currentTime);
        const translatedLine = Lyrics.getActiveTranslatedLyricAtTime(currentTime);
        const isTranslated = Lyrics.isTranslationEnabled();

        if (!activeLine) {
            if (lyricEl.dataset.current !== "") {
                lyricEl.dataset.current = "";
                lyricEl.style.opacity = 0;
                if (translatedEl) {
                    translatedEl.dataset.current = "";
                    translatedEl.style.opacity = 0;
                }
                setTimeout(() => {
                    if (lyricEl.dataset.current === "") {
                        lyricEl.innerText = "";
                        if (translatedEl) translatedEl.innerText = "";
                        setLyricVisibility(false);
                    }
                }, 180);
            } else {
                setLyricVisibility(false);
            }
            return;
        }

        if (lyricEl.dataset.current !== activeLine.text) {
            lyricEl.dataset.current = activeLine.text;
            lyricEl.style.opacity = 0;
            if (translatedEl) translatedEl.style.opacity = 0;
            setTimeout(() => {
                lyricEl.innerText = activeLine.text;
                if (translatedEl) {
                    const translatedText = isTranslated ? (translatedLine?.text || "") : "";
                    translatedEl.dataset.current = translatedText;
                    translatedEl.innerText = translatedText;
                    translatedEl.style.opacity = translatedText ? 1 : 0;
                }
                lyricEl.style.opacity = 1;
                setLyricVisibility(true);
                const container = document.querySelector('.lyrics-display');
                if (container) {
                    container.classList.toggle('is-translated', !!(isTranslated && translatedLine?.text));
                    container.classList.remove('lyric-impact');
                    void container.offsetWidth;
                    container.classList.add('lyric-impact');
                }
            }, 200);
        } else {
            if (translatedEl) {
                const translatedText = isTranslated ? (translatedLine?.text || "") : "";
                translatedEl.dataset.current = translatedText;
                translatedEl.innerText = translatedText;
                translatedEl.style.opacity = translatedText ? 1 : 0;
            }
            const container = document.querySelector('.lyrics-display');
            if (container) {
                container.classList.toggle('is-translated', !!(isTranslated && translatedLine?.text));
            }
            setLyricVisibility(true);
        }
    },

    updateProgressBar(referenceCurrent = null) {
        if (!Player.playerAtivo || typeof Player.playerAtivo.getCurrentTime !== 'function') return;

        const current = typeof referenceCurrent === 'number' ? referenceCurrent : Player.playerAtivo.getCurrentTime();
        const duration = Player.playerAtivo.getDuration() || 1;
        const pct = (current / duration) * 100;

        document.getElementById('progressBarFill').style.width = pct + "%";
        document.getElementById('progressThumb').style.left = pct + "%";
        const pRange = document.getElementById('progressRange');
        if (pRange) pRange.value = pct;

        document.getElementById('currentTime').innerText = formatTime(current);
        document.getElementById('totalTime').innerText = formatTime(duration);
    },

    updateUI(data) {
        document.getElementById('trackTitle').innerText = data.title || "---";
        document.getElementById('trackArtist').innerText = data.artist || "---";
        updatePageTitle(data.title, data.artist);
        if (data.artist && data.artist !== lastArtistContextArtist) {
            fetchArtistContext(true);
        }

        if (data.cover) {
            const art = document.getElementById('albumArt');

            if (art.src !== data.cover) art.src = data.cover;

            const bgLayerAura = document.getElementById('bgLayerAura');
            if (bgLayerAura && bgLayerAura.dataset.bgUrl !== data.cover) {
                bgLayerAura.dataset.bgUrl = data.cover;
                bgLayerAura.style.backgroundImage = `url('${data.cover}')`;
            }

            const bgLayer = document.getElementById('bgLayer');
            if (bgLayer && bgLayer.dataset.bgUrl !== data.cover) {
                bgLayer.dataset.bgUrl = data.cover;
                bgLayer.style.backgroundImage = `url('${data.cover}')`;
            }

            getProminentColor(data.cover).then(color => {
                const container = document.querySelector('.album-art-container');
                if (container) {
                    container.style.boxShadow = `0 24px 58px rgba(0,0,0,0.28), 0 0 42px ${color.replace('0.7)', '0.16)')}`;
                    container.style.borderColor = color.replace('0.7)', '0.12)');
                }
            });

            applyAlbumTheme(data.cover);
        }
    }
};

function formatTime(s) {
    const min = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${min}:${sec < 10 ? '0' : ''}${sec}`;
}

function updatePlayIcons(state) {
    const play = document.getElementById('playIcon');
    const pause = document.getElementById('pauseIcon');
    const load = document.getElementById('btnLoading');

    if (isWaitingForSync) {
        play?.classList.add('hidden');
        pause?.classList.add('hidden');
        load?.classList.remove('hidden');
    } else {
        load?.classList.add('hidden');

        if (state === 'pause') {
            play?.classList.add('hidden');
            pause?.classList.remove('hidden');
        } else {
            play?.classList.remove('hidden');
            pause?.classList.add('hidden');
        }
    }
}

function getCurrentVolume() {
    return document.getElementById('volumeRange')?.value || 80;
}

function setVolumeValue(nextVolume) {
    const volumeRange = document.getElementById('volumeRange');
    if (!volumeRange) return;
    const safeVolume = Math.max(0, Math.min(100, Number(nextVolume) || 0));
    volumeRange.value = safeVolume;
    if (safeVolume > 0) {
        lastAudibleVolume = safeVolume;
    }
    if (!audioUnlocked && Player.playerAtivo) {
        audioUnlocked = true;
        Player.turnOnAudio(false);
        prepareActivePlayerAudio();
    }
    if (Player.playerAtivo) {
        if (safeVolume <= 0 && typeof Player.playerAtivo.mute === 'function') {
            Player.playerAtivo.mute();
        } else {
            if (typeof Player.playerAtivo.unMute === 'function') Player.playerAtivo.unMute();
            if (typeof Player.playerAtivo.setVolume === 'function') {
                Player.playerAtivo.setVolume(safeVolume);
            }
        }
    }
}

function clearDriftCorrection() {
    if (driftCorrectionTimer) {
        clearTimeout(driftCorrectionTimer);
        driftCorrectionTimer = null;
    }

    if (Player.playerAtivo && typeof Player.playerAtivo.setPlaybackRate === 'function') {
        try {
            Player.playerAtivo.setPlaybackRate(1);
        } catch (e) {}
    }
}

function canPerformHardSeek(minIntervalMs = 5000) {
    return (Date.now() - lastHardSeekAt) >= minIntervalMs;
}

function performHardSeek(targetTime, minIntervalMs = 5000) {
    if (!Player.playerAtivo || typeof Player.playerAtivo.seekTo !== 'function') return false;
    if (!canPerformHardSeek(minIntervalMs)) return false;
    try {
        lastHardSeekAt = Date.now();
        Player.playerAtivo.seekTo(targetTime, true);
        return true;
    } catch (e) {
        return false;
    }
}

function applySubtleDriftCorrection(driftSeconds, allowMediumCorrection = false) {
    if (!Player.playerAtivo || typeof Player.playerAtivo.setPlaybackRate !== 'function') return false;

    const absDrift = Math.abs(driftSeconds);
    if (absDrift <= DRIFT_IGNORE_ZONE || absDrift > DRIFT_RATE_HARD_LIMIT) {
        clearDriftCorrection();
        return false;
    }

    let targetRate = 1;
    if (absDrift <= DRIFT_RATE_SOFT_LIMIT) {
        targetRate = driftSeconds > 0 ? 1.02 : 0.98;
    } else if (allowMediumCorrection) {
        targetRate = driftSeconds > 0 ? 1.04 : 0.96;
    } else {
        clearDriftCorrection();
        return false;
    }

    try {
        Player.playerAtivo.setPlaybackRate(targetRate);
        if (driftCorrectionTimer) clearTimeout(driftCorrectionTimer);
        driftCorrectionTimer = setTimeout(() => {
            if (Player.playerAtivo && typeof Player.playerAtivo.setPlaybackRate === 'function') {
                try {
                    Player.playerAtivo.setPlaybackRate(1);
                } catch (e) {}
            }
            driftCorrectionTimer = null;
        }, allowMediumCorrection ? 900 : 700);
        return true;
    } catch (e) {
        return false;
    }
}

function prepareActivePlayerAudio() {
    if (!Player.playerAtivo) return;

    if (audioUnlocked) {
        if (typeof Player.playerAtivo.unMute === 'function') Player.playerAtivo.unMute();
        if (typeof Player.playerAtivo.setVolume === 'function') Player.playerAtivo.setVolume(getCurrentVolume());
    } else if (typeof Player.playerAtivo.mute === 'function') {
        Player.playerAtivo.mute();
    }
}

function applyVariantTrackFade(remainingMs = 0) {
    if (!audioUnlocked || !Player.playerAtivo || typeof Player.playerAtivo.setVolume !== 'function') {
        return;
    }

    const baseVolume = Number(getCurrentVolume() || 80);
    const shouldFadeVariant = isRelaxedOffsetTrack(currentTrackKey);
    const shouldApplyUniversalHandoffFade = remainingMs > 0 && remainingMs <= 420;

    if (!shouldFadeVariant && !shouldApplyUniversalHandoffFade) {
        try {
            Player.playerAtivo.setVolume(baseVolume);
        } catch (e) {}
        return;
    }

    if (shouldFadeVariant && remainingMs > 1200) {
        try {
            Player.playerAtivo.setVolume(baseVolume);
        } catch (e) {}
        return;
    }

    const fadeWindowMs = shouldFadeVariant ? 1200 : 420;
    const minVolumeRatio = shouldFadeVariant ? 0.35 : 0.18;
    const fadeRatio = clamp(remainingMs / fadeWindowMs, 0, 1);
    const fadedVolume = Math.round(baseVolume * (minVolumeRatio + ((1 - minVolumeRatio) * fadeRatio)));
    try {
        Player.playerAtivo.setVolume(fadedVolume);
    } catch (e) {}
}

function forceVisibleYoutubeToCurrentTrack() {
    if (typeof Player.syncVisiblePlayerShell === 'function') {
        Player.syncVisiblePlayerShell();
    }
}

function isPlayerPrimedForSwap(player, expectedStartTime = 0) {
    if (!player || typeof player.getPlayerState !== 'function') {
        return false;
    }

    try {
        const state = player.getPlayerState();
        const currentTime = typeof player.getCurrentTime === 'function' ? Number(player.getCurrentTime() || 0) : 0;
        const duration = typeof player.getDuration === 'function' ? Number(player.getDuration() || 0) : 0;
        const requiresResolvedStart = expectedStartTime > 1.5;
        const isNearExpectedStart = Math.abs(currentTime - expectedStartTime) <= 1.4;
        const hasDuration = duration > 0;

        if (state === YT.PlayerState.CUED || state === YT.PlayerState.PLAYING || state === YT.PlayerState.PAUSED) {
            if (!hasDuration) return false;
            return requiresResolvedStart ? isNearExpectedStart : true;
        }

        if (state === YT.PlayerState.BUFFERING) {
            if (!hasDuration) return false;
            if (requiresResolvedStart) {
                return currentTime > 0.25 && isNearExpectedStart;
            }
            return currentTime > 0.25 || expectedStartTime <= 0.35;
        }

        return false;
    } catch (e) {
        return false;
    }
}

function waitForSwapPrime(player, expectedStartTime = 0, timeoutMs = 180, intervalMs = 16) {
    if (isPlayerPrimedForSwap(player, expectedStartTime)) {
        return Promise.resolve(true);
    }

    return new Promise((resolve) => {
        const startedAt = Date.now();
        const timer = setInterval(() => {
            if (isPlayerPrimedForSwap(player, expectedStartTime)) {
                clearInterval(timer);
                resolve(true);
                return;
            }

            if ((Date.now() - startedAt) >= timeoutMs) {
                clearInterval(timer);
                resolve(false);
            }
        }, intervalMs);
    });
}

function isPlayerActuallyPlaying() {
    if (!Player.playerAtivo || typeof Player.playerAtivo.getPlayerState !== 'function') {
        return !!Player.isPlaying;
    }

    try {
        const state = Player.playerAtivo.getPlayerState();
        return state === YT.PlayerState.PLAYING || state === YT.PlayerState.BUFFERING;
    } catch (e) {
        return !!Player.isPlaying;
    }
}

document.body.addEventListener('click', () => {
    if (!audioUnlocked) {
        console.log("Áudio global desbloqueado");
        audioUnlocked = true;
        Player.turnOnAudio(true);
        prepareActivePlayerAudio();
        if (sessionState.isHost) {
            openSetupSyncRetryWindow(6000);
            openSyncAssistWindow(2400);
            isWaitingForSync = true;
            scheduleStatusPoll(120);
            syncEngine.checkStatus();
        }
    }
}, { once: true });

const closeSetupBtnEl = document.getElementById('closeSetupBtn');
if (closeSetupBtnEl) {
    closeSetupBtnEl.innerHTML = '&times;';
}

const connectionStatusEl = document.getElementById('connectionStatus');
if (connectionStatusEl) {
    connectionStatusEl.innerHTML = '&#9679;';
}

document.getElementById('playPauseBtn').addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!sessionState.canControl) {
        setLyricsFeedbackState('Somente o host controla a jam');
        return;
    }
    forceVisibleYoutubeToCurrentTrack();

    if (!audioUnlocked) {
        console.log("Áudio desbloqueado pelo usuário");
        audioUnlocked = true;
        Player.turnOnAudio(false);
        prepareActivePlayerAudio();
    }

    if (Player.isPlaying || isPlayerActuallyPlaying() || isWaitingForSync) {
        isWaitingForSync = false;
        openLocalPausePending(1600);
        pauseDetectionCount = 0;
        clearDriftCorrection();
        Player.setIsPlaying(false);
        updatePlayIcons('play');

        if (Player.playerAtivo && typeof Player.playerAtivo.pauseVideo === 'function') {
            Player.playerAtivo.pauseVideo();
        }
        await Player.sendSpotifyCommand('pause');
        scheduleStatusPoll(120);
    } else {
        localPausePendingUntil = 0;
        isWaitingForSync = true;
        openSyncAssistWindow(3000);
        Player.setIsPlaying(false);
        updatePlayIcons();

        if (!audioUnlocked && Player.playerAtivo && typeof Player.playerAtivo.setVolume === 'function') {
            Player.playerAtivo.setVolume(0);
        } else if (audioUnlocked && Player.playerAtivo) {
            if (typeof Player.playerAtivo.unMute === 'function') Player.playerAtivo.unMute();
            if (typeof Player.playerAtivo.setVolume === 'function') Player.playerAtivo.setVolume(document.getElementById('volumeRange').value || 80);
        }

        await Player.sendSpotifyCommand('play');
        scheduleStatusPoll(120);
    }
});

document.getElementById('nextBtn').addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!sessionState.canControl) {
        setLyricsFeedbackState('Somente o host controla a jam');
        return;
    }
    openSyncAssistWindow(3600);
    await Player.sendSpotifyCommand('next');
    scheduleStatusPoll(120);
});

document.getElementById('prevBtn').addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!sessionState.canControl) {
        setLyricsFeedbackState('Somente o host controla a jam');
        return;
    }
    openSyncAssistWindow(3600);
    await Player.sendSpotifyCommand('prev');
    scheduleStatusPoll(120);
});

document.getElementById('volumeRange').addEventListener('input', (e) => {
    setVolumeValue(e.target.value);
});

document.getElementById('volumeBtn').addEventListener('click', (e) => {
    e.stopPropagation();
    const currentVolume = Number(getCurrentVolume() || 0);
    if (currentVolume <= 0) {
        setVolumeValue(lastAudibleVolume || 80);
    } else {
        setVolumeValue(0);
    }
});

document.getElementById('lyricsLikeBtn').addEventListener('click', (e) => {
    e.stopPropagation();

    const artist = document.getElementById('trackArtist').innerText;
    const track = document.getElementById('trackTitle').innerText;

    if (Lyrics.likeCurrentLyrics(artist, track)) {
        setLyricsFeedbackState('Letra salva', true);
    } else {
        setLyricsFeedbackState('Nada para salvar');
    }
});

document.getElementById('lyricsDislikeBtn').addEventListener('click', (e) => {
    e.stopPropagation();

    const candidate = Lyrics.dislikeCurrentLyrics();
    const lyricEl = document.getElementById('currentLyric');
    const translatedEl = document.getElementById('translatedLyric');

    lyricEl.dataset.current = "";
    lyricEl.style.opacity = 1;
    if (translatedEl) {
        translatedEl.innerText = "";
        translatedEl.dataset.current = "";
        translatedEl.style.opacity = 0;
    }

    if (candidate) {
        lyricEl.innerText = "";
        setLyricVisibility(false);
        setLyricsFeedbackState('Tentando outra letra');
        refreshCurrentLyricFrame();
    } else {
        lyricEl.innerText = "";
        setLyricVisibility(false);
        setLyricsFeedbackState('Sem mais opcoes');
    }

    refreshLyricsControls();
});

document.getElementById('lyricsResetBtn').addEventListener('click', (e) => {
    e.stopPropagation();

    const artist = document.getElementById('trackArtist').innerText;
    const track = document.getElementById('trackTitle').innerText;
    const lyricEl = document.getElementById('currentLyric');

    Lyrics.clearLikedLyrics(artist, track);
    Lyrics.resetLyrics();
    lyricEl.innerText = "";
    lyricEl.dataset.current = "";
    const translatedEl = document.getElementById('translatedLyric');
    translatedEl.innerText = "";
    translatedEl.dataset.current = "";
    translatedEl.style.opacity = 0;
    setLyricVisibility(false);
    refreshLyricsControls();

    Lyrics.fetchLyrics(artist, track)
        .finally(() => {
            refreshLyricsControls();
            setLyricsFeedbackState('Preferencia limpa');
        });
});

document.getElementById('lyricsTranslateBtn').addEventListener('click', async (e) => {
    e.stopPropagation();
    const currentState = Lyrics.getLyricsUiState();
    if (!currentState.currentCandidate) {
        setLyricsFeedbackState('Sem letra para traduzir');
        return;
    }

    const turningOff = currentState.isTranslated;
    const needsRemoteTranslation = !turningOff && !currentState.hasCachedTranslation;
    if (turningOff) {
        const translatePromise = Lyrics.toggleTranslation();
        refreshLyricsControls();
        const translatedEl = document.getElementById('translatedLyric');
        translatedEl.innerText = '';
        translatedEl.dataset.current = '';
        translatedEl.style.opacity = 0;
        try {
            const candidate = await translatePromise;
            if (candidate) {
                refreshCurrentLyricFrame();
            }
            refreshLyricsControls();
            setLyricsFeedbackState('Voltando para original');
        } catch (error) {
            refreshLyricsControls();
            setLyricsFeedbackState('Tradução indisponivel');
        }
        return;
    }

    try {
        const translatePromise = Lyrics.toggleTranslation();
        refreshLyricsControls();
        if (needsRemoteTranslation) {
            setTranslationPendingUi(true);
        }

        const candidate = await translatePromise;
        setTranslationPendingUi(false);
        if (candidate) {
            refreshCurrentLyricFrame();
            refreshLyricsControls();
            setLyricsFeedbackState(needsRemoteTranslation && !Lyrics.getLyricsUiState().hasFullTranslation ? 'PT-BR entrou no começo' : (needsRemoteTranslation ? 'Tradução PT-BR pronta' : 'Tradução PT-BR ativa'));
        } else {
            refreshLyricsControls();
            setLyricsFeedbackState('Tradução indisponível');
        }
    } catch (error) {
        setTranslationPendingUi(false);
        refreshLyricsControls();
        setLyricsFeedbackState('Tradução indisponível');
    }
});

document.getElementById('lyricsTranslateBtn').addEventListener('pointerup', (e) => {
    e.stopPropagation();
});

refreshLyricsControls();
window.addEventListener('lyrics-state-change', () => {
    refreshLyricsControls();
    const state = Lyrics.getLyricsUiState();
    if (state.isTranslated && state.hasCachedTranslation) {
        refreshCurrentLyricFrame();
    }
});
applySessionUi();
setLyricVisibility(false);
loadThemeSelection();
loadStoredProfile();
fetchProfiles();
syncStoredProfileToServer();
updatePrivacyBanner();
applySetupLanguage();
restoreStoredProfileFromServer()
    .finally(() => {
        setTimeout(() => maybePromptProfileSetup(), 180);
    });

window.addEventListener('focus', () => {
    syncEngine.checkStatus();
});

document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        syncEngine.checkStatus();
    }
});

bindInstantPressFeedback([
    document.getElementById('lyricsTranslateBtn'),
    document.getElementById('lyricsLikeBtn'),
    document.getElementById('lyricsDislikeBtn'),
    document.getElementById('lyricsResetBtn'),
    document.getElementById('playPauseBtn'),
    document.getElementById('nextBtn'),
    document.getElementById('prevBtn'),
    document.getElementById('shuffleBtn'),
    document.getElementById('repeatBtn'),
    document.getElementById('volumeBtn'),
    document.getElementById('settingsFab'),
    document.getElementById('closeSetupBtn'),
    document.getElementById('saveProfileBtn'),
    document.getElementById('saveGuestControlBtn'),
    document.getElementById('saveThemeBtn'),
    document.getElementById('saveSetupBtn'),
    document.getElementById('savePublicBaseUrlBtn'),
    document.getElementById('startTunnelBtn'),
    document.getElementById('stopTunnelBtn'),
    document.getElementById('copyViewerLinkBtn'),
    document.getElementById('copyHostLinkBtn'),
    document.getElementById('setupLangPtBtn'),
    document.getElementById('setupLangEnBtn'),
    ...Array.from(document.querySelectorAll('.setup-nav-btn')),
]);

document.getElementById('settingsFab').addEventListener('click', () => {
    openSetupModal();
});

document.getElementById('privacyBannerAcceptBtn')?.addEventListener('click', () => {
    acceptPrivacyBanner();
});

document.getElementById('privacyBannerDetailsBtn')?.addEventListener('click', () => {
    openSetupModal('privacy');
});

document.getElementById('jamInviteOpenBtn')?.addEventListener('click', () => {
    openSetupModal('profile');
});

document.getElementById('closeSetupBtn').addEventListener('click', () => {
    closeSetupModal();
});

document.querySelectorAll('.setup-nav-btn').forEach((button) => {
    button.addEventListener('click', () => {
        toggleSetupSection(button.dataset.target);
    });
});

document.querySelectorAll('.setup-lang-btn').forEach((button) => {
    button.addEventListener('click', () => {
        const nextLanguage = button.dataset.lang === 'en' ? 'en' : 'pt';
        localStorage.setItem(SETUP_LANGUAGE_KEY, nextLanguage);
        applySetupLanguage();
    });
});

document.getElementById('setupModal').addEventListener('click', (e) => {
    if (e.target.id === 'setupModal') {
        closeSetupModal();
    }
});

document.getElementById('profilePhotoInput').addEventListener('change', (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        const photo = typeof reader.result === 'string' ? reader.result : '';
        const name = (document.getElementById('profileNameInput').value || '').trim();
        updateProfilePreview(name, photo);
    };
    reader.readAsDataURL(file);
});

document.getElementById('profileNameInput').addEventListener('input', (e) => {
    const name = (e.target.value || '').trim();
    const storedPhoto = localStorage.getItem(PROFILE_PHOTO_KEY) || '';
    updateProfilePreview(name, storedPhoto);
});

document.getElementById('saveProfileBtn').addEventListener('click', async () => {
    const savedProfile = await saveProfileLocally();
    if (!savedProfile.name) {
        showSetupMessage('Digite um nome para sincronizar o perfil.');
        return;
    }

    const synced = await syncStoredProfileToServer();
    if (synced) {
        showSetupMessage('Perfil salvo e sincronizado na jam.', false);
    } else {
        showSetupMessage('Perfil salvo localmente, mas a sincronizacao falhou.');
    }
});

document.getElementById('clearProfilePhotoBtn')?.addEventListener('click', async () => {
    clearStoredProfilePhoto();
    const hasName = !!(localStorage.getItem(PROFILE_NAME_KEY) || '').trim();
    if (hasName) {
        const synced = await syncStoredProfileToServer();
        showSetupMessage(synced ? 'Foto removida do perfil.' : 'Foto removida localmente, mas a sincronizacao falhou.', !synced);
    } else {
        showSetupMessage('Foto removida deste navegador.', false);
    }
});

document.getElementById('saveThemeBtn').addEventListener('click', () => {
    const selected = document.querySelector('input[name="backgroundTheme"]:checked')?.value || 'album';
    localStorage.setItem(THEME_MODE_KEY, selected);
    applyThemeMode(selected);
    showSetupMessage('Tema visual salvo neste navegador.', false);
});

document.getElementById('copyViewerLinkBtn')?.addEventListener('click', async () => {
    const value = document.getElementById('viewerLinkInput')?.value || '';
    if (!value) return;
    try {
        await navigator.clipboard.writeText(value);
        showSetupMessage('Link dos convidados copiado.', false);
    } catch (error) {
        showSetupMessage('Nao foi possivel copiar o link.');
    }
});

document.getElementById('copyHostLinkBtn')?.addEventListener('click', async () => {
    const value = document.getElementById('hostLinkInput')?.value || '';
    if (!value) return;
    try {
        await navigator.clipboard.writeText(value);
        showSetupMessage('Link do host copiado.', false);
    } catch (error) {
        showSetupMessage('Nao foi possivel copiar o link.');
    }
});

document.getElementById('savePublicBaseUrlBtn')?.addEventListener('click', async () => {
    if (!sessionState.isHost) return;
    const publicBaseUrl = (document.getElementById('publicBaseUrlInput')?.value || '').trim().replace(/\/+$/, '');
    try {
        const res = await fetch(buildApiUrl('/host/preferences'), {
            method: 'POST',
            headers: buildHostHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                ALLOW_GUEST_CONTROLS: !!document.getElementById('guestControlToggle')?.checked,
                PUBLIC_BASE_URL: publicBaseUrl
            })
        });
        const payload = await res.json();
        if (res.ok && payload.status === 'OK') {
            sessionState.publicBaseUrl = (payload.public_base_url || '').trim();
            applySessionUi();
            showSetupMessage(sessionState.publicBaseUrl ? 'URL publica salva para compartilhar a jam.' : 'URL publica removida.', false);
        } else {
            showSetupMessage(payload.message || 'Nao foi possivel salvar a URL publica.');
        }
    } catch (error) {
        showSetupMessage('Erro ao salvar a URL publica.');
    }
});

document.getElementById('startTunnelBtn')?.addEventListener('click', async () => {
    if (!sessionState.isHost) return;
    sessionState.tunnelStatus = 'starting';
    updateTunnelUi();
    try {
        const res = await fetch(buildApiUrl('/tunnel/start'), {
            method: 'POST',
            headers: buildHostHeaders({ 'Content-Type': 'application/json' })
        });
        const payload = await res.json();
        if (res.ok) {
            sessionState.tunnelStatus = payload.tunnel_state || (payload.starting ? 'starting' : 'idle');
            sessionState.tunnelActive = !!payload.active;
            sessionState.publicBaseUrl = (payload.public_base_url || sessionState.publicBaseUrl || '').trim();
            updateTunnelUi();
            showSetupMessage('Tunnel iniciado. Aguarde o link publico aparecer.', false);
            setTimeout(() => loadTunnelStatus(), 1800);
        } else {
            sessionState.tunnelStatus = 'error';
            updateTunnelUi();
            showSetupMessage(payload.message || 'Nao foi possivel iniciar o tunnel.');
        }
    } catch (error) {
        sessionState.tunnelStatus = 'error';
        updateTunnelUi();
        showSetupMessage('Erro ao iniciar o tunnel automatico.');
    }
});

document.getElementById('stopTunnelBtn')?.addEventListener('click', async () => {
    if (!sessionState.isHost) return;
    try {
        const res = await fetch(buildApiUrl('/tunnel/stop'), {
            method: 'POST',
            headers: buildHostHeaders({ 'Content-Type': 'application/json' })
        });
        const payload = await res.json();
        if (res.ok) {
            sessionState.tunnelStatus = payload.tunnel_state || 'idle';
            sessionState.tunnelActive = !!payload.active;
            sessionState.publicBaseUrl = '';
            updateTunnelUi();
            updateShareLinks();
            showSetupMessage('Tunnel encerrado.', false);
        } else {
            showSetupMessage(payload.message || 'Nao foi possivel encerrar o tunnel.');
        }
    } catch (error) {
        showSetupMessage('Erro ao encerrar o tunnel.');
    }
});

document.getElementById('saveGuestControlBtn')?.addEventListener('click', async () => {
    if (!sessionState.isHost) return;
    const allowGuestControls = !!document.getElementById('guestControlToggle')?.checked;
    try {
        const res = await fetch(buildApiUrl('/host/preferences'), {
            method: 'POST',
            headers: buildHostHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ ALLOW_GUEST_CONTROLS: allowGuestControls })
        });
        const payload = await res.json();
        if (res.ok && payload.status === 'OK') {
            sessionState.allowGuestControls = !!payload.allow_guest_controls;
            sessionState.canControl = sessionState.isHost || sessionState.allowGuestControls;
            applySessionUi();
            fetchProfiles();
            showSetupMessage(sessionState.allowGuestControls ? 'Convidados podem controlar a jam.' : 'Somente o host controla a jam.', false);
        } else {
            showSetupMessage(payload.message || 'Nao foi possivel salvar a permissao.');
        }
    } catch (error) {
        showSetupMessage('Erro ao salvar permissao dos convidados.');
    }
});

document.getElementById('saveSetupBtn').addEventListener('click', async () => {
    if (!sessionState.isHost) {
        showSetupMessage('Somente o host pode editar as APIs.');
        return;
    }
    const errorMsg = document.getElementById('setupError');
    const clientId = document.getElementById('clientIdInput').value.trim();
    const clientSecret = document.getElementById('clientSecretInput').value.trim();
    const ytKey = document.getElementById('ytKeyInput').value.trim();
    const allowGuestControls = !!document.getElementById('guestControlToggle')?.checked;

    if (!clientId || !clientSecret || !ytKey) {
        showSetupMessage('Preencha todos os campos.');
        return;
    }

    try {
        const res = await fetch(buildApiUrl('/setup'), {
            method: 'POST',
            headers: buildHostHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                CLIENT_ID: clientId,
                CLIENT_SECRET: clientSecret,
                YOUTUBE_API_KEY: ytKey,
                ALLOW_GUEST_CONTROLS: allowGuestControls
            })
        });

        const jsonData = await res.json();

        if (res.ok && jsonData.status === "OK") {
            if (jsonData.spotify_auth_required && jsonData.spotify_auth_url) {
                window.location.href = jsonData.spotify_auth_url;
                return;
            }
            errorMsg.classList.add('hidden');
            document.getElementById('setupModal').classList.add('hidden');
            isSetupMode = false;
            sessionState.allowGuestControls = allowGuestControls;
            sessionState.canControl = true;
            sessionState.setupRequired = false;
            sessionState.hasApiCredentials = true;
            audioUnlocked = true;
            currentVideoId = "";
            pendingVideoId = "";
            activeSwapVideoId = "";
            isSwapping = false;
            isWaitingForSync = true;
            latestSpotifyStatusAt = 0;
            openSetupSyncRetryWindow(15000);
            Player.turnOnAudio(false);
            prepareActivePlayerAudio();
            openSyncAssistWindow(3600);
            armHydrationSyncBurst(3);
            applySessionUi();
            await loadSessionState();
            await loadTunnelStatus();
            try {
                window.focus();
            } catch (e) {}
            await syncEngine.checkStatus();
            setTimeout(() => syncEngine.checkStatus(), 320);
            scheduleStatusPoll(120);
            fetchQueuePreview();
            fetchProfiles();
            showSetupMessage('APIs conectadas. A jam segue nesta mesma guia.', false);
        } else {
            errorMsg.innerText = jsonData.message || "Credenciais Inválidas";
            errorMsg.classList.remove('hidden');
        }
    } catch (e) {
        errorMsg.innerText = "Erro ao conectar com o Servidor local.";
        errorMsg.classList.remove('hidden');
    }
});





