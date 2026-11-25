"""Write the winget manifests for a Cornerplay release, ready for github.com/microsoft/winget-pkgs.

    python3 tools/winget_manifest.py 0.25.0        (the release must be published on GitHub)

The files land in packaging/winget/manifests/r/raulgbh-ctrl/Cornerplay/<version>/, the same
path they take in winget-pkgs; the installer's SHA-256 is the one GitHub lists for the asset.
Submitting: packaging/winget/README.md.
"""
import json
import sys
import urllib.request
from pathlib import Path

REPO = "raulgbh-ctrl/cornerplay"
ID = "raulgbh-ctrl.Cornerplay"
# Inno Setup registers the app under its AppId (packaging/windows/cornerplay.iss) plus "_is1".
PRODUCT_CODE = "{6C1E0E7A-3B5B-4C55-9F0E-C0A7E7B1A0D1}_is1"
SCHEMA = "1.28.0"
ROOT = Path(__file__).resolve().parent.parent


def asset(version):
    with urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/releases/tags/v{version}", timeout=30) as r:
        rel = json.load(r)
    name = f"cornerplay-{version}-windows-setup.exe"
    for a in rel.get("assets") or []:
        if a.get("name") == name:
            digest = a.get("digest") or ""
            if not digest.startswith("sha256:"):
                raise SystemExit(f"GitHub lists no SHA-256 for {name}")
            return a["browser_download_url"], digest.split(":", 1)[1].upper(), (rel.get("published_at") or "")[:10]
    raise SystemExit(f"{name} is not in release v{version}")


def manifests(version, url, sha256, date):
    head = "# yaml-language-server: $schema=https://aka.ms/winget-manifest.{kind}.%s.schema.json\n\n" % SCHEMA
    return {
        f"{ID}.yaml": head.format(kind="version") + f"""PackageIdentifier: {ID}
PackageVersion: {version}
DefaultLocale: en-US
ManifestType: version
ManifestVersion: {SCHEMA}
""",
        f"{ID}.installer.yaml": head.format(kind="installer") + f"""PackageIdentifier: {ID}
PackageVersion: {version}
MinimumOSVersion: 10.0.17763.0
InstallerType: inno
Scope: user
InstallModes:
- interactive
- silent
UpgradeBehavior: install
Protocols:
- nxm
ProductCode: '{PRODUCT_CODE}'
ReleaseDate: {date}
Installers:
- Architecture: x64
  InstallerUrl: {url}
  InstallerSha256: {sha256}
ManifestType: installer
ManifestVersion: {SCHEMA}
""",
        f"{ID}.locale.en-US.yaml": head.format(kind="defaultLocale") + f"""PackageIdentifier: {ID}
PackageVersion: {version}
PackageLocale: en-US
Publisher: raulgbh-ctrl
PublisherUrl: https://github.com/raulgbh-ctrl
PublisherSupportUrl: https://github.com/{REPO}/issues
PackageName: Cornerplay
PackageUrl: https://raulgbh-ctrl.github.io/cornerplay/
License: MIT
LicenseUrl: https://github.com/{REPO}/blob/main/LICENSE
ShortDescription: One cosy library for Steam, Epic, GOG, Amazon, Battle.net, Xbox / Game Pass and Humble Bundle, with a TV mode.
Description: |-
  Cornerplay puts every game you own in one library: Steam, Epic Games, GOG, Amazon Games,
  Battle.net, Xbox and PC Game Pass, Humble Bundle, emulators and your own games. Install, update
  and play from one place, with cloud and local save backups, playtime, achievements, mods, and a
  TV mode for the couch and a controller. Free and open source.
Moniker: cornerplay
Tags:
- games
- game-launcher
- library
- steam
- epic-games
- gog
- game-pass
ReleaseNotesUrl: https://github.com/{REPO}/releases/tag/v{version}
ManifestType: defaultLocale
ManifestVersion: {SCHEMA}
""",
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    version = sys.argv[1].lstrip("v")
    url, sha256, date = asset(version)
    out = ROOT / "packaging" / "winget" / "manifests" / "r" / "raulgbh-ctrl" / "Cornerplay" / version
    out.mkdir(parents=True, exist_ok=True)
    for name, text in manifests(version, url, sha256, date).items():
        (out / name).write_text(text, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
