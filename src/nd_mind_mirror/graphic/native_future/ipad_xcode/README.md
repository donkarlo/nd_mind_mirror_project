# Future Xcode build

The source in this directory is kept synchronized with the Swift Playgrounds iPad source under `graphic/ipad/nd_graphic.swiftpm`.

When a Mac is available, build the native iPad target from this source and connect to the Ubuntu bridge with the direct LAN endpoint:

```text
tcp://<ubuntu-lan-ip>:8767
```

The Ubuntu bridge still exposes its HTTP/WebSocket compatibility endpoint on port 8766, but the native iPad client uses the direct TCP JSON-lines transport on port 8767.
