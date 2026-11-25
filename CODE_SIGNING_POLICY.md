# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by
[SignPath Foundation](https://signpath.org/).

The Windows installer of Cornerplay (`cornerplay-<version>-windows-setup.exe`) is signed with a
code signing certificate so that Windows can show who published it. Only files built by this
repository's own GitHub Actions workflow (`.github/workflows/ci.yml`, job `windows`) from a
release tag (`v*`) are sent for signing. Nothing built on a personal computer is signed.

Every release file (the Linux `.run` installer and the Windows installer) is also signed with the
project's own release key, and Cornerplay checks that signature before it installs an update.

## Team roles

- Committers and reviewers: [raulgbh-ctrl](https://github.com/raulgbh-ctrl)
- Approvers: [raulgbh-ctrl](https://github.com/raulgbh-ctrl)

Every signing request is approved by hand before the certificate is used.

## Privacy policy

Cornerplay has no telemetry and no analytics, and it does not send information about you or your
PC to the project or to anyone else.

It connects to other services only for what you use it for:

- **Stores you sign in to**, to list, install, update and start your games and sync their saves:
  Steam, Epic Games (through legendary), GOG (through gogdl), Amazon Games (through nile),
  Battle.net, Xbox / PC Game Pass (through Nexus Launcher on Linux, the Xbox app on Windows) and
  Humble Bundle. Sign-ins happen on the stores' own pages; Cornerplay keeps only the session
  tokens they hand back, on your PC.
- **Public game information**: cover art and details (Steam, Epic, GOG, Microsoft's Game Pass
  catalog, SteamGridDB and IGDB with your own optional keys, PCGamingWiki, ProtonDB, libretro
  thumbnails), prices (IsThereAnyDeal), mods (Nexus Mods, Thunderstore).
- **GitHub**, to check for a new version of Cornerplay and to download the tools it uses
  (legendary, gogdl, nile, Nexus Launcher), each checked against its published checksum.

What is sent to each service is what that service needs to answer (a game's id, your account's
session where you signed in). See each service's own privacy policy for what it does with it.
