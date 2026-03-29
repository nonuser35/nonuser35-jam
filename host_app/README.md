# Host App

Language: English | [Português (Brasil)](README.pt-BR.md)

This folder contains the Windows host app packaging layer for `nonuser35-jam`.

It exists so the host can run the jam from a portable `.exe` without needing Python installed on the final machine.

## What Is Included

- `launcher.py`: host app entrypoint and desktop control panel
- `nonuser35_host.spec`: PyInstaller build spec
- `setup_build_env.bat`: creates a clean build virtual environment
- `build_host.bat`: quick build script
- `requirements-build.txt`: build-time dependencies
- `app_icon.png` / `app_icon.ico`: host app icon assets

## What the Host App Does

The host app:

- starts the local backend on port `5000`;
- opens the host jam in the browser when requested;
- shows a desktop control panel for the host;
- exposes local and public guest links;
- controls Cloudflare Tunnel startup and shutdown;
- keeps runtime files inside the packaged app structure.

## Current Host UX

The desktop window acts as a host control panel.

It now shows:

- host control guidance;
- server status;
- room / control state;
- Spotify request window summary;
- Spotify limit state;
- host local link;
- guest public link;
- QR for the guest public link;
- dedicated buttons for:
  - opening the host jam;
  - opening the public jam;
  - copying the guest link;
  - starting or stopping the tunnel.

## Cloudflare

The backend looks automatically for:

- `cloudflared.exe`
- `cloudflared-windows-amd64.exe`

inside:

- `projeto/`
- or the project root

So if `cloudflared-windows-amd64.exe` is placed in `projeto/`, the host app will already use it.

## Build Flow

Recommended flow:

1. run `host_app/setup_build_env.bat`
2. then run `host_app/build_host.bat`
3. the final output is generated in:

```text
host_app/final/NONUSER35 JAM Host/
```

## Why This Build Flow Is Used

- it uses a clean build-only virtual environment;
- it avoids pulling unnecessary packages from the main Python install;
- it keeps the final app smaller and more predictable;
- it works well with a Flask backend, local assets, JSON runtime files, and Cloudflare executable packaging.

## How the Site Side Works

When the host uses the packaged app:

- the backend still runs locally;
- the browser UI still lives at `http://localhost:5000`;
- Spotify provides current playback state;
- the jam resolves an equivalent track on YouTube / YT Music;
- lyrics, artist context, and guest presence remain part of the same site experience.

Guests:

- join through browser;
- follow the same jam session;
- see lyrics, artist context, and room presence;
- may or may not control playback depending on host permissions.

## API Roles

### Spotify

Used to:

- read the current track;
- detect play / pause;
- detect track changes;
- track progress;
- keep the jam aligned with the host's listening session.

Before the host authorizes Spotify, the Spotify Developer app must include this Redirect URI:

```text
http://127.0.0.1:5000/spotify/callback
```

Without that callback configured, the Spotify auth flow in the host app / local jam will fail.

### YouTube Data API v3

Used to:

- find the playback candidate for the jam player;
- improve matching quality when the Spotify track changes.

### Cloudflare Tunnel

Used to:

- expose the jam publicly outside localhost;
- let guests join from outside the local network.

It does not replace the player. It only exposes the host's local session to remote guests.

## First-Time Flow

1. the host opens the app
2. the host starts the host jam flow
3. the browser opens `http://localhost:5000`
4. the setup screen asks for APIs
5. the host creates:
   - a Spotify Developer app
   - a Google Cloud project with YouTube Data API v3 enabled
6. in the Spotify app settings, the host adds:

```text
http://127.0.0.1:5000/spotify/callback
```
7. the host pastes the credentials into the setup screen
8. the same browser flow continues into the jam
9. when needed, the host generates and shares the public guest link

## Notes

The packaging is intentionally `onedir`, which is usually more stable for a project that mixes:

- Flask backend;
- static site assets;
- local JSON/runtime files;
- cached resources;
- external tunnel executable.

So the final experience is:

- deliver a ready folder;
- the user does not install Python;
- the user does not install packages;
- they simply open the `.exe` inside the final folder.
