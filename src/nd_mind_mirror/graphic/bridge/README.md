# ND Mind Mirror graphic bridge

Run the bridge on the Ubuntu computer from the project root:

```bash
./nd_graphic_bridge
```

The process exposes two local transports at the same time:

- `http://0.0.0.0:8766` / `ws://0.0.0.0:8766/ws` for the desktop notifier, diagnostics, and compatibility clients.
- `tcp://0.0.0.0:8767` for the native iPad Swift Playgrounds app.

The current iPad app uses the WebSocket endpoint on port 8766 through `URLSessionWebSocketTask`. On iPadOS 17 and later, IP-literal connections are covered by explicit private-network CIDR exceptions in the app's `Info.plist`, which avoids the ATS `-1022` failure seen with a bare IP URL. The direct TCP endpoint on port 8767 remains available as a diagnostic/fallback transport.

To get the Ubuntu LAN address:

```bash
hostname -I
```

For example, if the LAN address is `10.0.0.73`, enter this in ND Graphic:

```text
ws://10.0.0.73:8766/ws
```

The iPad and Ubuntu computer must be on the same local network, and Local Network permission must be enabled for ND Graphic on iPadOS.
