# nonuser35-jam

Language: English | [Português (Brasil)](README.pt-BR.md)

Experimental browser-based jam sync project with Spotify-driven playback, YouTube matching, synced lyrics, PT-BR translation, artist context, and a portable Windows host app.

## Quick Summary

- the host connects Spotify and YouTube once;
- the jam follows the host's current Spotify track;
- the site resolves an equivalent version on YouTube / YT Music;
- guests join through localhost or a public link;
- the interface shows player, lyrics, translation, artist context, and presence in the room.

## What You Will Find Here

- Spotify-driven track sync for the web jam player;
- dual-player YouTube swaps to reduce cuts;
- synced lyrics with PT-BR translation;
- artist widget with images, curiosities, website, and tour context;
- portable Windows host app to launch and manage the jam quickly.

## Usage, Privacy, and Scope

This project exists for:

- study;
- prototyping;
- UX research;
- audiovisual sync research;
- local technical experimentation.

It is not presented as:

- an official product;
- a commercial service;
- a guaranteed uptime solution;
- a licensed commercial playback tool;
- software officially affiliated with Spotify, YouTube, or Cloudflare.

The host is responsible for:

- their own API credentials;
- public links they choose to share;
- permissions given to guests;
- the local environment where the jam runs.

The project stores local runtime data such as:

- configuration;
- profiles;
- video cache;
- logs;
- downloaded visual context assets.

These stay in the host's local environment. For the full policy, see `docs/PRIVACY_AND_USE.md`.

## Spotify API Notice

The project depends on the Spotify Web API to:

- identify the current track;
- know play/pause state;
- track playback progress;
- detect track changes;
- inspect queue state;
- send playback commands when applicable.

Important points:

- Spotify uses a rolling 30-second request window;
- this limit is not exposed as a clear “remaining quota” dashboard like Google Cloud;
- in development mode, the limit tends to be more sensitive;
- when rate limited, the jam may temporarily react slower to track, state, or queue updates.

When that happens:

- the block is usually temporary;
- it may last minutes or a few hours depending on the `Retry-After`;
- it does not affect normal use of the official Spotify app;
- the impact stays on the jam app/site because that layer depends on Web API reads.

The project already tries to reduce this risk with:

- leaner polling;
- short bursts only in critical moments;
- local playback progress projection;
- local video cache;
- automatic backoff when the API starts limiting requests.

## Quick Start

### Local site

```bat
cd /d "C:\Users\Usuario\Documents\scrapping dados\projeto"
python yp2.py
```

Then open:

```text
http://localhost:5000
```

### Windows host app

1. run `host_app/setup_build_env.bat`
2. then run `host_app/build_host.bat`
3. use the final folder in `host_app/final/NONUSER35 JAM Host`

## Overview

The project follows the current track playing on the host's Spotify, finds an equivalent version on YouTube for the jam player, and synchronizes playback for guests.

Besides playback, the interface can also show:

- synced lyrics;
- PT-BR translation;
- artist visual context;
- curiosities;
- official website;
- tour / show data;
- participant profiles;
- a public session link.

## How the App Works

General flow:

1. the host opens the local site or the Windows host app;
2. Spotify and YouTube are configured the first time;
3. the local backend reads the current Spotify track;
4. the system resolves an equivalent version on YouTube / YT Music;
5. the jam player takes over that track;
6. the site keeps time, play/pause, and track swaps aligned;
7. the host can generate a public link for guests.

In practice, the project is split like this:

- `Spotify`: tells the app what is currently playing and its playback state;
- `local backend`: owns jam state, resolves videos, keeps cache, and exposes local routes;
- `web frontend`: plays the jam track, manages swaps and sync, and renders lyrics and artist context;
- `Cloudflare Tunnel`: optional layer for sharing the jam outside localhost;
- `host app`: wraps the host experience into a portable `.exe`.

## Sync Logic

The jam does not work by simply pressing play on a video.

It currently relies on:

- Spotify current-track reads;
- `track_id` comparison to detect real track changes;
- `videoId` resolution for the new track;
- dual YouTube player swaps to reduce cuts;
- drift correction;
- next-track pre-cache when possible;
- short polling bursts during critical moments.

Most of the time:

- the site runs more freely;
- the backend confirms Spotify state at controlled intervals;
- heavier correction happens during track changes, initial hydration, play/pause, or handoff moments.

This exists to balance:

- responsiveness;
- stability;
- and Spotify API pressure.

## Track Changes

The project handles two main cases:

### 1. Natural transition

When one track ends and the next one starts normally:

- the queue helps prepare the next track;
- the inactive player can be preloaded;
- the transition tends to be smoother.

### 2. Manual change outside queue

When the host clicks another song directly in Spotify:

- the backend detects the change from the current track, not from the queue;
- it tries to resolve the new video immediately;
- it opens a short faster-polling window;
- the frontend holds a small grace interval before killing the old player, reducing silence or awkward repeats.

This is the hardest case and where the project depends most on:

- local cache;
- fast video resolution;
- and good Spotify API responsiveness.

## Lyrics and Translation

The lyrics system tries to:

- fetch synced lyrics;
- show the active line at the right moment;
- allow PT-BR translation;
- bring the first translated lines early enough so the beginning of the song is not lost.

Translation may arrive in stages:

- first a useful beginning;
- then more lines;
- and finally the full translated lyric.

## Artist Visual Context

The artist widget may bring together:

- artist photos;
- curiosities;
- website;
- status;
- next show;
- last show;
- contextual venue imagery.

These assets are collected and cached locally to keep the site more stable during real use.

## Required APIs and Services

### Spotify

Used to:

- identify the current track;
- read play/pause state;
- read progress;
- detect track changes;
- inspect queue state;
- send playback commands when the host uses controls.

Before authorizing Spotify, the host must register this Redirect URI in the Spotify Developer Dashboard:

```text
http://127.0.0.1:5000/spotify/callback
```

Without that callback configured in the host's Spotify app, authorization will fail even if `CLIENT_ID` and `CLIENT_SECRET` are correct.

### YouTube Data API v3

Used to find the equivalent track that the jam player will reproduce.

### Cloudflare Tunnel

Used to create a public link when the host wants to share the session outside the local network.

## Repository Structure

- `projeto`: Flask backend, jam frontend, and runtime-facing code.
- `host_app`: launcher, build scripts, icons, and host app packaging.
- `docs/QUICKSTART.md`: usage and setup guide.
- `docs/PRIVACY_AND_USE.md`: privacy, scope, responsibility, and usage notes.

## Development Requirements

- Python 3.11
- a Spotify Developer app
- a Google Cloud project with YouTube Data API v3 enabled
- `cloudflared` available for public links

## Technical Structure

### Local backend

- runs on Flask;
- talks to Spotify;
- resolves videos;
- keeps cache and session state;
- exposes local routes for the frontend and host app.

### Web frontend

- plays the jam track;
- manages sync, swaps, and drift;
- shows lyrics, translation, and the artist widget;
- works both in a normal browser and inside the host app flow.

### Host app

- starts the local backend;
- opens the jam;
- shows room status, public link, and recent request counters;
- organizes the host experience into a portable `.exe`.

## Natural Technical Limits

Even when the app is behaving well, some limits are still inherent to the stack:

- catalog differences between Spotify and YouTube;
- live, remaster, lyric-video, or alternate uploads;
- occasional delays in video resolution;
- temporary Spotify API limits;
- timing differences across platforms;
- browser autoplay constraints, especially after authentication flows.

These do not automatically mean a critical bug; many come from the platforms themselves.
