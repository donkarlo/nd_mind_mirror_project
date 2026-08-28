# ND Mind Mirror graphic bridge

Run the bridge on the Ubuntu computer from the project root:

```bash
./nd_graphic_bridge
```

The bridge currently supports three transports:

- HTTP/WebSocket for desktop diagnostics and compatibility clients. The preferred port is `8766`.
- Legacy direct TCP fallback. The preferred port is `8767`.
- Reverse iPad transport: the native iPad app listens on TCP port `8768`, and Ubuntu scans the LAN and connects to the iPad. This is the current native iPad transport.

## Automatic port fallback

`nd_graphic_bridge` no longer fails just because another program already owns one of the Ubuntu listener ports.

- If WebSocket port `8766` is occupied, the launcher selects the next available port while keeping the legacy TCP preferred port and iPad listener port reserved. With the defaults this normally means `8769`, then `8770`, and so on.
- If legacy TCP port `8767` is occupied, the launcher also selects the next available non-conflicting port.
- TCP port `8768` is reserved for the listener running on the iPad and is never reused as an Ubuntu fallback port.
- Existing processes are not killed or modified.
- The selected ports are printed in the launcher output, for example `websocket port 8766 busy -> using 8769`.
- The Python module performs the same collision check as a second safeguard when it is launched directly with `python -m nd_mind_mirror.graphic.bridge`.

The port probe uses ordinary socket binding and does not require `sudo`, `lsof`, or manual PID cleanup.

To inspect the Ubuntu LAN address when needed:

```bash
hostname -I
```

The iPad and Ubuntu computer must be on the same local network, and Local Network permission must be enabled for ND Graphic on iPadOS.
