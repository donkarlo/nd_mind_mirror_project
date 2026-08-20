# nd_tikz_bridge (Ubuntu)

The bridge is the low-latency path between the iPad Pencil app and your real TikZ file. Point it at the workspace already synced by Dropbox; it writes the `.tikz` file atomically, renders it with LuaLaTeX, returns a PNG to the iPad, and broadcasts changes made from Ubuntu back to the iPad.

## Install

```bash
cd bridge
/home/donkarlo/phd-venv/bin/python -m pip install -e .
```

The render side also needs `lualatex` and `pdftocairo` (Poppler).

## Run

```bash
nd-tikz-bridge \
  --workspace ~/Dropbox/repo \
  --host 0.0.0.0 \
  --port 8765 \
  --token 'choose-a-private-token'
```

Then set the iPad connection to `ws://<UBUNTU-LAN-IP>:8765/ws` and use the same token.

If a TikZ fragment depends on macros/styles from your paper, put those definitions in a small preamble file and add:

```bash
--preamble ~/.config/nd_tikz_sketch/preamble.tex
```

Dropbox is not required for live transport. It is useful for persistence and normal cross-device sync because the bridge edits the actual file under the Dropbox workspace.
