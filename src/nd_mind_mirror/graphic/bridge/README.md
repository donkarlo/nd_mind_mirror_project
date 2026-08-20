# Mind Mirror Graphic bridge

This bridge connects Mind Mirror on Ubuntu to the native **ND Graphic** iPad app.

The iPad app is a Swift Playgrounds application package:

```text
src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm
```

No Mac or Xcode is required. Install Swift Playgrounds from the App Store on the iPad, copy the `.swiftpm` package to **On My iPad** or iCloud Drive, open it in Swift Playgrounds, and run the app.

Run the bridge on Ubuntu:

```bash
TOKEN='choose-a-token' ./nd_graphic_bridge
```

The default workspace is `~/Dropbox/repo`, host is `0.0.0.0`, and port is `8766`.
Find the Ubuntu LAN address with:

```bash
hostname -I
```

In ND Graphic on iPad, configure:

```text
ws://UBUNTU_IP:8766/ws
```

and enter the same token. Both devices must be on the same local network.

When **Insert / update image in iPad…** is selected in Mind Mirror, the requested `.ndgraphic` document is pushed through WebSocket and opens automatically in the iPad app. PencilKit preserves editable strokes. Each drawing change is autosaved through the bridge; the neighboring PNG is replaced atomically on Ubuntu, Visual reloads the image, and Preview recompiles against the new PNG. New images are created in the same directory as the active `.tex` file.

The browser implementation under `graphic/web/` is kept only as a fallback.
