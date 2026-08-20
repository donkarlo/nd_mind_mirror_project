# nd_tikz_sketch iPad app — v0.2.0

Native iPadOS 17+ SwiftUI/PencilKit client. Open `nd_tikz_sketch.xcodeproj` in Xcode, select your Apple developer team for signing, connect an iPad, and Run.

The app connects directly to `nd_tikz_bridge` on Ubuntu over WebSocket. The bridge writes the real `.tikz` file in your Ubuntu workspace; if the workspace is under Dropbox, Dropbox syncs it normally.

Drawing tools: freehand, line, arrow, rectangle node, ellipse node, and handwriting text.

For handwriting text, select the dotted `abc` text tool, write with Apple Pencil, then stop writing for about 0.9 s. The app uses Apple Vision OCR. If the text lies inside an editable TikZ node, it updates that node's `{...}` text. Otherwise it creates a standalone `\\node at (...) {...};`. Once Ubuntu renders the changed TikZ, the hand-drawn ink is replaced by the clean TikZ result.

For a trusted home LAN you can use `ws://<ubuntu-ip>:8765/ws`. The included Info.plist allows this development/personal-install workflow. For Internet exposure, use a VPN/Tailscale or TLS and a bridge token.
