"""Remove legacy recent/fixed tool UI state before the dynamic saved-tool patch runs."""
from __future__ import annotations

from pathlib import Path
import re


class IpadDynamicLegacyCleanup:
    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        path = self.source_root / "Views" / "ContentView.swift"
        if not path.is_file():
            return False

        original = path.read_text(encoding="utf-8")
        text = original

        for line in (
            "    @StateObject private var recentPresets = RecentToolPresetStore()\n",
            "    @StateObject private var fixedPresets = FixedToolPresetStore()\n",
            "    @State private var showToolPresets = false\n",
            "                    recentPresets.remember(hex: color, width: pencil.width, for: tool)\n",
            "                recentPresets.remember(color: newColor, width: pencil.width, for: tool)\n",
        ):
            text = text.replace(line, "")

        old_change = '''        .onChange(of: tool) { oldTool, newTool in
            switchToolColor(from: oldTool, to: newTool)
            showRecentColors = false
            if !newTool.supportsColor {
                showToolPresets = false
            } else {
                recentPresets.remember(color: pencil.color, width: pencil.width, for: newTool)
            }
        }
        .onChange(of: pencil.width) { _, newWidth in
            if tool.supportsWidth {
                recentPresets.remember(color: pencil.color, width: newWidth, for: tool)
            }
        }
'''
        simple_change = '''        .onChange(of: tool) { _, _ in
            showRecentColors = false
        }
'''
        text = text.replace(old_change, simple_change)

        core_change = '''        .onChange(of: tool) { oldTool, newTool in
            switchToolColor(from: oldTool, to: newTool)
            showRecentColors = false
        }
'''
        text = text.replace(core_change, simple_change)

        text = re.sub(
            r'        \.onChange\(of: pencil\.width\) \{ _, newWidth in\n'
            r'            if tool\.supportsWidth \{\n'
            r'                recentPresets\.remember\(color: pencil\.color, width: newWidth, for: tool\)\n'
            r'            \}\n'
            r'        \}\n',
            "",
            text,
        )

        if text == original:
            return False
        path.write_text(text, encoding="utf-8")
        return True
