#!/bin/sh
# Sign release files with the project's key: writes <file>.sig next to each one.
#   tools/sign-release.sh dist/cornerplay-X.Y.Z.run dist/cornerplay.run
# The key (~/.ssh/cornerplay-release, or $CORNERPLAY_SIGNING_KEY) never goes to GitHub; its public
# half is PUBLIC_KEY in cornerplay/updates.py. Anyone can check a download by hand:
#   echo 'cornerplay-release namespaces="cornerplay-release" <PUBLIC_KEY>' > signers
#   ssh-keygen -Y verify -f signers -I cornerplay-release -n cornerplay-release -s cornerplay.run.sig < cornerplay.run
set -eu
KEY=${CORNERPLAY_SIGNING_KEY:-$HOME/.ssh/cornerplay-release}
[ -r "$KEY" ] || { echo "No signing key at $KEY" >&2; exit 1; }
for f in "$@"; do
    rm -f "$f.sig"
    ssh-keygen -Y sign -q -f "$KEY" -n cornerplay-release "$f"
    echo "Signed $f.sig"
done
