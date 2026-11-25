# Cornerplay in winget

`winget install raulgbh-ctrl.Cornerplay` once the manifests are in
[microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs).

## For each release

1. Publish the release on GitHub (with `cornerplay-<version>-windows-setup.exe`).
2. `python3 tools/winget_manifest.py <version>` writes the three manifests to
   `manifests/r/raulgbh-ctrl/Cornerplay/<version>/` here, with the installer's SHA-256 from GitHub.
3. Submit them, either way:
   - **wingetcreate** (on Windows): `wingetcreate submit --token <GitHub token> manifests/r/raulgbh-ctrl/Cornerplay/<version>`
   - **by hand**: fork microsoft/winget-pkgs, copy the folder to the same path in it, open a pull
     request. Microsoft's bot checks the manifests and installs the app in a test machine; a
     moderator merges it (usually within a few days for a new package, faster for updates).

The first submission creates the package; later versions only add a folder. The manifests'
`ProductCode` matches the installer's AppId (`packaging/windows/cornerplay.iss`), so winget
sees an installed Cornerplay and can update it.
