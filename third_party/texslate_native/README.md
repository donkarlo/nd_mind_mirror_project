# TeXslate native compiler binary

Mind Mirror currently bundles the unmodified ARM64 native Tectonic compiler library
from TeXslate v1.0-alpha26 core as the Android on-device LaTeX engine.

Source:
https://github.com/thobgg/TeXslate/tree/v1.0-alpha26

Release artifact:
TeXslate-1.0-alpha26-core-arm64-v8a.apk

Pinned release APK SHA-256:
`2c0502df3f306ee970deef432e4bbbaed69c051b2deb54710201ec96aab7f7c0`

The reproducible extraction script is `scripts/android/build_native_tectonic.sh`; it verifies this digest before extracting the native runtime.

Bundled files:
- libtexslate_native.so
- libc++_shared.so

TeXslate is licensed under GPL-3.0-or-later. Its native library embeds Tectonic,
which is licensed under the MIT License and incorporates TeX/XeTeX components with
their respective upstream licenses. The TeXslate GPL-3.0 license text is included
in this directory and in the Android APK assets.

The Mind Mirror Kotlin/JavaScript integration is implemented independently in this
repository. The binary is kept unmodified so its corresponding source remains the
exact tagged TeXslate source above.
