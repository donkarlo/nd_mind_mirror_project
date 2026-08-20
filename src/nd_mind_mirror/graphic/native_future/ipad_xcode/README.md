# nd_graphic for iPad

This is the Apple Pencil companion app used by Mind Mirror's **Insert / update image in iPad…** command. It edits ordinary raster graphics, not TikZ.

The Pencil tool uses PencilKit's pencil ink, with selectable color and base width. Apple Pencil pressure/tilt are handled by PencilKit, so stronger pressure naturally produces a darker/broader pencil mark. The Eraser tool removes strokes. Every drawing change is autosaved after a short debounce through the Ubuntu WebSocket bridge; the bridge updates both the editable `.ndgraphic` sidecar and the PNG that LaTeX includes.

Open `nd_graphic.xcodeproj` on a Mac, select your development team, build for iPad, then connect to `ws://<ubuntu-lan-ip>:8766/ws`.
