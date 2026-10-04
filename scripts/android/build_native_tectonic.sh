#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_DIR="$PROJECT_ROOT/src/nd_mind_mirror/mobile/android/app/src/main/jniLibs/arm64-v8a"
VERSION="v1.0-alpha26"
APK_NAME="TeXslate-1.0-alpha26-core-arm64-v8a.apk"
APK_SHA256="2c0502df3f306ee970deef432e4bbbaed69c051b2deb54710201ec96aab7f7c0"
DOWNLOAD_URL="https://github.com/thobgg/TeXslate/releases/download/$VERSION/$APK_NAME"

temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT

apk_path="$temporary_directory/$APK_NAME"

curl --fail --location --retry 3 --output "$apk_path" "$DOWNLOAD_URL"
printf '%s  %s\n' "$APK_SHA256" "$apk_path" | sha256sum --check --status

mkdir -p "$TARGET_DIR"
rm -f "$TARGET_DIR"/*.so

unzip -p "$apk_path" lib/arm64-v8a/libtexslate_native.so > "$TARGET_DIR/libtexslate_native.so"
unzip -p "$apk_path" lib/arm64-v8a/libc++_shared.so > "$TARGET_DIR/libc++_shared.so"
chmod 755 "$TARGET_DIR"/*.so

echo "Installed the pinned TeXslate/Tectonic ARM64 runtime:"
ls -lh "$TARGET_DIR"
