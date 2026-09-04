#!/usr/bin/env bash
set -euo pipefail

IPAD_DIR="/home/donkarlo/Dropbox/repo/nd_mind_mirror_project/src/nd_mind_mirror/graphic/ipad"

cd "$IPAD_DIR"
rm -f nd_graphic.zip

zip -r nd_graphic.zip nd_graphic.swiftpm \
    -x '*__MACOSX*' '*.DS_Store' '*.ndtmp'

echo
echo "Created: $IPAD_DIR/nd_graphic.zip"
