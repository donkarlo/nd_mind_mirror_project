"""Apply the migration_4 desktop and iPad fixes without creating backup files."""

from __future__ import annotations

from pathlib import Path
import re


class ProjectMigration4Patch:
    """Patch desktop/bridge sources before their modules are imported by the Qt app."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.src = self.project_root / "src" / "nd_mind_mirror"

    def apply(self) -> bool:
        changed = False
        changed |= self._patch_search_window()
        changed |= self._patch_small_preview()
        changed |= self._patch_single_preview_highlight()
        changed |= self._patch_latex_shortcut_safety()
        changed |= self._patch_graphic_document_manager()
        changed |= self._patch_bridge_jpeg_save()
        changed |= self._patch_readme_feature_source()
        return changed

    @staticmethod
    def _write_if_changed(path: Path, original: str, updated: str) -> bool:
        if updated == original:
            return False
        path.write_text(updated, encoding="utf-8")
        return True

    @staticmethod
    def _replace_once(text: str, old: str, new: str) -> str:
        if old not in text:
            return text
        return text.replace(old, new, 1)

    def _patch_search_window(self) -> bool:
        path = self.src / "ui" / "search" / "window" / "search_window.py"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        if "ND_MIGRATION4_FOLDER_REVEAL" in original:
            return False
        old = '''        if path.is_dir():
            item.setExpanded(not item.isExpanded())
            return
'''
        new = '''        if path.is_dir():
            # ND_MIGRATION4_FOLDER_REVEAL
            # Folder hits behave like file hits: close Search and reveal the
            # actual folder in the main Navigator instead of expanding the
            # temporary search-result tree.
            parent = self.parentWidget()
            navigator = getattr(parent, "_file_system_panel", None)
            if navigator is not None:
                navigator.select_path(
                    str(path.resolve()),
                    force_reveal=True,
                )
            self.close()
            return
'''
        updated = self._replace_once(original, old, new)
        return self._write_if_changed(path, original, updated)

    def _patch_small_preview(self) -> bool:
        changed = False
        enhanced = self.src / "ui" / "window" / "main" / "enhanced_main_window.py"
        if enhanced.is_file():
            original = enhanced.read_text(encoding="utf-8")
            text = original
            if "ND_MIGRATION4_IMMEDIATE_SMALL_OPEN" not in text:
                anchor = "        base_compile_pending_source = renderer._compile_pending_source\n"
                addition = '''        base_compile_pending_source = renderer._compile_pending_source
        base_render = renderer.render
        last_render_path: Path | None = None

        # ND_MIGRATION4_IMMEDIATE_SMALL_OPEN
        # A newly opened small source should start compiling immediately. The
        # normal typing debounce remains in force for subsequent keystrokes.
        def render_source(
            source: str,
            source_path=None,
            immediate: bool = False,
        ) -> None:
            nonlocal last_render_path
            resolved = None
            if source_path is not None:
                try:
                    resolved = Path(source_path).expanduser().resolve()
                except (OSError, TypeError, ValueError):
                    resolved = None
            first_small_open = (
                len(source) < self._SMALL_PREVIEW_SOURCE_CHARS
                and resolved is not None
                and resolved != last_render_path
            )
            if resolved is not None:
                last_render_path = resolved
            base_render(
                source,
                source_path=source_path,
                immediate=bool(immediate or first_small_open),
            )
'''
                text = self._replace_once(text, anchor, addition)
                assignment = "        renderer._compile_pending_source = compile_pending_source\n"
                text = self._replace_once(
                    text,
                    assignment,
                    "        renderer.render = render_source\n" + assignment,
                )
            changed |= self._write_if_changed(enhanced, original, text)

        pdf_view = self.src / "ui" / "preview" / "pdf" / "selectable_pdf_view.py"
        if pdf_view.is_file():
            original = pdf_view.read_text(encoding="utf-8")
            text = original
            if "ND_MIGRATION4_NO_FIT_RASTER_SCAN" not in text:
                marker = '''        """Estimate horizontal painted-content bounds from a small PDF render."""
'''
                text = self._replace_once(
                    text,
                    marker,
                    marker
                    + "        # ND_MIGRATION4_NO_FIT_RASTER_SCAN\n"
                    + "        # Auto Fit must never raster-scan pages on the GUI thread.\n"
                    + "        return None\n",
                )
            changed |= self._write_if_changed(pdf_view, original, text)
        return changed

    def _patch_single_preview_highlight(self) -> bool:
        path = self.src / "ui" / "preview" / "pdf" / "selectable_pdf_view.qml"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        if "ND_MIGRATION4_SINGLE_HIGHLIGHT" in original:
            return False
        old = '''    function scheduleHighlightResultChoice() {
        root.highlightSearchAttempts = 0
'''
        new = '''    function scheduleHighlightResultChoice() {
        // ND_MIGRATION4_SINGLE_HIGHLIGHT
        // Qt may recreate the search-result resource after a PDF reload. Make
        // every non-current match transparent again before choosing the one
        // nearest to the SyncTeX cursor location.
        root.configureEditHighlightStyle()
        root.highlightSearchAttempts = 0
'''
        updated = self._replace_once(original, old, new)
        return self._write_if_changed(path, original, updated)

    def _patch_latex_shortcut_safety(self) -> bool:
        path = self.src / "ui" / "window" / "main" / "main_window.py"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        if "ND_MIGRATION4_SHORTCUT_AUTOSAVE_GUARD" not in text:
            old_loop = '''        for (
            path,
            content,
        ) in self._editor_panel.modified_documents():
            if self._save_document(
'''
            new_loop = '''        for (
            path,
            content,
        ) in self._editor_panel.modified_documents():
            # ND_MIGRATION4_SHORTCUT_AUTOSAVE_GUARD
            # latex_shortcuts.yaml is a configuration dictionary, not a normal
            # prose document. Never persist a half-typed transient buffer from
            # the periodic autosave timer.
            try:
                shortcut_path = Path(
                    self._app_settings.latex_shortcuts_file_path
                ).expanduser().resolve()
            except (OSError, TypeError, ValueError):
                shortcut_path = None
            try:
                current_path = Path(path).expanduser().resolve()
            except (OSError, TypeError, ValueError):
                current_path = None
            if shortcut_path is not None and current_path == shortcut_path:
                continue
            if self._save_document(
'''
            text = self._replace_once(text, old_loop, new_loop)

        if "ND_MIGRATION4_SHORTCUT_SAVE_VALIDATION" not in text:
            signature = '''    def _save_document(
        self,
        path: Path,
        content: str,
        show_error: bool,
    ) -> bool:
'''
            guard = signature + '''        # ND_MIGRATION4_SHORTCUT_SAVE_VALIDATION
        try:
            protected_shortcut_path = Path(
                self._app_settings.latex_shortcuts_file_path
            ).expanduser().resolve()
            candidate_path = Path(path).expanduser().resolve()
        except (OSError, TypeError, ValueError):
            protected_shortcut_path = None
            candidate_path = None

        if (
            protected_shortcut_path is not None
            and candidate_path == protected_shortcut_path
        ):
            valid_shortcuts = False
            validation_error = ""
            try:
                import yaml

                payload = yaml.safe_load(content)
                shortcuts = payload.get("shortcuts") if isinstance(payload, dict) else None
                valid_shortcuts = (
                    isinstance(shortcuts, dict)
                    and bool(shortcuts)
                    and all(
                        isinstance(entry, dict)
                        and isinstance(entry.get("replacement"), str)
                        and bool(entry.get("replacement", "").strip())
                        for entry in shortcuts.values()
                    )
                )
                if not valid_shortcuts:
                    validation_error = (
                        "latex_shortcuts.yaml must contain a non-empty 'shortcuts' "
                        "mapping whose entries have non-empty replacements."
                    )
            except Exception as exc:
                validation_error = str(exc)

            if not valid_shortcuts:
                message = validation_error or "Invalid latex_shortcuts.yaml"
                self.statusBar().showMessage(
                    "Not saved: " + message,
                    6000,
                )
                if show_error:
                    QMessageBox.warning(
                        self,
                        "Invalid LaTeX shortcuts",
                        "The shortcut file was not overwritten.\\n\\n" + message,
                    )
                return False

'''
            text = self._replace_once(text, signature, guard)

        return self._write_if_changed(path, original, text)

    def _patch_graphic_document_manager(self) -> bool:
        path = self.src / "graphic" / "core" / "document_manager.py"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        if "from PySide6.QtGui import QImageReader" not in text:
            text = self._replace_once(
                text,
                "import zlib\n",
                "import zlib\n\nfrom PySide6.QtGui import QImageReader\n",
            )

        text = text.replace(
            '        if image.suffix.lower() != ".png":\n            return None\n',
            '        if image.suffix.lower() not in {".png", ".jpg", ".jpeg"}:\n            return None\n',
            1,
        )

        if "ND_MIGRATION4_NATIVE_IMAGE_CANVAS" not in text:
            old = '''        if not sidecar.exists():
            self._write_sidecar(sidecar, image, source_file)
        else:
            self._ensure_source_name(sidecar, source_file)
'''
            new = '''        if not sidecar.exists():
            self._write_sidecar(sidecar, image, source_file)
        else:
            self._ensure_source_name(sidecar, source_file)
            self._ensure_image_canvas_size(sidecar, image)
'''
            text = self._replace_once(text, old, new)

            payload_anchor = '''        payload = {
            "version": 1,
            "image_name": image_path.name,
'''
            payload_new = '''        # ND_MIGRATION4_NATIVE_IMAGE_CANVAS
        native_width, native_height = self._image_dimensions(image_path)
        canvas_width = native_width if native_width > 0 else self.canvas_width
        canvas_height = native_height if native_height > 0 else self.canvas_height
        payload = {
            "version": 1,
            "image_name": image_path.name,
'''
            text = self._replace_once(text, payload_anchor, payload_new)
            text = text.replace(
                '            "canvas_width": self.canvas_width,\n            "canvas_height": self.canvas_height,\n',
                '            "canvas_width": canvas_width,\n            "canvas_height": canvas_height,\n',
                1,
            )

            helper_anchor = '''    @staticmethod
    def _ensure_source_name(sidecar: Path, source_path: Path) -> None:
'''
            helpers = '''    @staticmethod
    def _image_dimensions(image_path: Path) -> tuple[int, int]:
        try:
            size = QImageReader(str(image_path)).size()
        except Exception:
            return 0, 0
        if not size.isValid():
            return 0, 0
        return max(int(size.width()), 0), max(int(size.height()), 0)

    @classmethod
    def _ensure_image_canvas_size(cls, sidecar: Path, image_path: Path) -> None:
        """Use native JPG/PNG size until editable drawing/background data exists."""
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        if not isinstance(payload, dict):
            return
        if str(payload.get("drawing_data_base64", "") or "").strip():
            return
        if str(payload.get("background_image_base64", "") or "").strip():
            return
        if payload.get("image_objects"):
            return
        width, height = cls._image_dimensions(image_path)
        if width <= 0 or height <= 0:
            return
        if (
            int(payload.get("canvas_width", 0) or 0) == width
            and int(payload.get("canvas_height", 0) or 0) == height
        ):
            return
        payload["canvas_width"] = width
        payload["canvas_height"] = height
        try:
            temporary = sidecar.with_suffix(sidecar.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(sidecar)
        except OSError:
            return

'''
            text = self._replace_once(text, helper_anchor, helpers + helper_anchor)

        return self._write_if_changed(path, original, text)

    def _patch_bridge_jpeg_save(self) -> bool:
        path = self.src / "graphic" / "bridge" / "server_compat.py"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original
        text = text.replace(
            '"""Bridge compatibility helpers for editable PNG backgrounds and recent iPad documents."""',
            '"""Bridge compatibility helpers for editable PNG/JPEG backgrounds and recent iPad documents."""',
            1,
        )
        if "from PySide6.QtCore import QBuffer, QIODevice" not in text:
            text = self._replace_once(
                text,
                "from typing import Any\n",
                "from typing import Any\n\nfrom PySide6.QtCore import QBuffer, QIODevice\nfrom PySide6.QtGui import QImage\n",
            )

        if "ND_MIGRATION4_JPEG_PRESERVE" not in text:
            anchor = '''        update = dict(payload)
        injected = False
'''
            addition = '''        update = dict(payload)
        injected = False

        # ND_MIGRATION4_JPEG_PRESERVE
        # The iPad renderer sends a lossless PNG composite. If the LaTeX image
        # being edited is .jpg/.jpeg, encode that composite back to JPEG before
        # the base bridge atomically replaces the target file.
        try:
            _sidecar_data, target_image_path = self._read_document(sidecar)
        except (OSError, ValueError):
            target_image_path = Path()
        if target_image_path.suffix.lower() in {".jpg", ".jpeg"}:
            encoded = str(update.get("png_base64", "") or "")
            if encoded:
                try:
                    raw = base64.b64decode(encoded, validate=True)
                    image = QImage.fromData(raw)
                    if not image.isNull():
                        buffer = QBuffer()
                        if buffer.open(QIODevice.OpenModeFlag.WriteOnly):
                            if image.save(buffer, "JPG", 95):
                                update["png_base64"] = base64.b64encode(
                                    bytes(buffer.data())
                                ).decode("ascii")
                            buffer.close()
                except Exception:
                    pass
'''
            text = self._replace_once(text, anchor, addition)
        return self._write_if_changed(path, original, text)

    def _patch_readme_feature_source(self) -> bool:
        """Keep the current-capabilities README block aligned on future refreshes."""
        path = self.src / "graphic" / "ipad" / "package_builder.py"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original
        replacements = {
            '- The iPad toolbar can keep any number of persistent Pencil and Highlighter tools. Saved tools store tool type, color, visible width, and opacity in `UserDefaults`; their toolbar buttons are icon-only, with icon color, visual weight/size, and alpha reflecting those saved settings.\\n':
            '- Pencil and Highlighter toolbar buttons each open their own settings popup for color, thickness, and transparency. The popup can add a new tool immediately after the current tool, change the current tool, switch among same-kind saved tools, or delete one; the main toolbar no longer duplicates those three setting controls.\\n',
            '- Pencil and Highlighter width/opacity remain adjustable, but the toolbar no longer prints numeric thickness or transparency labels beside those controls.\\n':
            '- JPG/JPEG and PNG `\\\\includegraphics` targets can both be opened in iPad Edit mode; existing image edits use the native pixel size and save back in the target image format.\\n',
            '- Lasso stroke selection keeps its four proportional resize handles and dedicated blue move handle for dragging the selected strokes, with Undo/Redo support.\\n':
            '- Lasso stroke selection keeps four proportional resize handles plus a smaller pale-gray move handle. Resizing changes geometry without scaling stroke thickness, and transformed stroke points are tested in canvas coordinates so moving a selection cannot silently move a different stroke.\\n',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        if "Folder hits in Double-Shift Search" not in text:
            marker = '            "- Navigator selection, rename, drag, bookmarks, autosave, and idle memory compaction remain enabled.\\n"\n'
            addition = (
                '            "- Folder hits in Double-Shift Search close Search and are revealed, scrolled to, and highlighted in the main Navigator.\\n"\n'
                '            "- Small LaTeX files begin their first Preview compile immediately; Auto Fit no longer raster-scans PDF pages on the GUI thread.\\n"\n'
                '            "- Preview edit synchronization renders only the current/nearest search result as the visible highlight even when the same phrase occurs more than once.\\n"\n'
                '            "- `latex_shortcuts.yaml` is excluded from periodic autosave and is validated as a non-empty shortcut mapping before an explicit save can overwrite it.\\n"\n'
            )
            text = text.replace(marker, addition + marker, 1)
        return self._write_if_changed(path, original, text)


class IpadMigration4Patch:
    """Patch the canonical Swift package after legacy/current normalizers run."""

    def __init__(self, source_root: str | Path) -> None:
        self.source_root = Path(source_root).expanduser().resolve()

    def apply(self) -> bool:
        changed = False
        changed |= self._patch_saved_tool_store()
        changed |= self._patch_content_toolbar()
        changed |= self._patch_canvas_selection()
        return changed

    @staticmethod
    def _write_if_changed(path: Path, original: str, updated: str) -> bool:
        if updated == original:
            return False
        path.write_text(updated, encoding="utf-8")
        return True

    @staticmethod
    def _replace_once(text: str, old: str, new: str) -> str:
        if old not in text:
            return text
        return text.replace(old, new, 1)

    def _patch_saved_tool_store(self) -> bool:
        path = self.source_root / "Services" / "SavedDrawingTools.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        if "after afterID: UUID? = nil" in original:
            return False
        old = '''    @discardableResult
    func add(kind: GraphicTool, color: Color, width: Double, opacity: Double) -> UUID? {
        guard kind.supportsColor && kind.supportsWidth else { return nil }
        let value = SavedDrawingTool(
            id: UUID(),
            kindRawValue: kind.rawValue,
            colorHex: Self.canonicalColorHex(color.hexRGB()),
            width: Self.canonicalWidth(width),
            opacity: Self.canonicalOpacity(opacity)
        )
        tools.append(value)
        persist()
        return value.id
    }
'''
        new = '''    @discardableResult
    func add(
        kind: GraphicTool,
        color: Color,
        width: Double,
        opacity: Double,
        after afterID: UUID? = nil
    ) -> UUID? {
        guard kind.supportsColor && kind.supportsWidth else { return nil }
        let value = SavedDrawingTool(
            id: UUID(),
            kindRawValue: kind.rawValue,
            colorHex: Self.canonicalColorHex(color.hexRGB()),
            width: Self.canonicalWidth(width),
            opacity: Self.canonicalOpacity(opacity)
        )
        if let afterID,
           let index = tools.firstIndex(where: { $0.id == afterID }) {
            tools.insert(value, at: index + 1)
        } else {
            tools.append(value)
        }
        persist()
        return value.id
    }
'''
        updated = self._replace_once(original, old, new)
        return self._write_if_changed(path, original, updated)

    def _patch_content_toolbar(self) -> bool:
        path = self.source_root / "Views" / "ContentView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        state_anchor = "    @StateObject private var savedTools = SavedDrawingToolStore()\n"
        if "editingSavedToolID" not in text and state_anchor in text:
            text = text.replace(
                state_anchor,
                state_anchor + "    @State private var editingSavedToolID: UUID?\n",
                1,
            )

        if "ND_TOOL_POPUP_MIGRATION4" not in text:
            start_marker = "                // ND_DYNAMIC_SAVED_TOOLS_V1\n"
            end_marker = '                toolButton(.eraser, systemImage: "eraser")\n'
            start = text.find(start_marker)
            end = text.find(end_marker, start if start >= 0 else 0)
            if start >= 0 and end > start:
                block = '''                // ND_TOOL_POPUP_MIGRATION4
                ForEach(savedTools.tools) { saved in
                    Button {
                        applySavedTool(saved)
                        editingSavedToolID = saved.id
                    } label: {
                        Image(systemName: saved.kind == .highlighter ? "highlighter" : "pencil")
                            .symbolRenderingMode(.monochrome)
                            .font(.system(
                                size: CGFloat(min(max(16.0 + saved.width * 0.22, 17.0), 29.0)),
                                weight: saved.width >= 40 ? .black
                                    : saved.width >= 24 ? .bold
                                    : saved.width >= 12 ? .semibold
                                    : saved.width >= 5 ? .medium
                                    : .regular
                            ))
                            .foregroundStyle(Color(hex: saved.colorHex).opacity(saved.opacity))
                            .frame(width: 34, height: 28)
                            .background(
                                isSavedToolActive(saved) ? Color.accentColor.opacity(0.18) : Color.clear,
                                in: RoundedRectangle(cornerRadius: 7)
                            )
                    }
                    .buttonStyle(.plain)
                    .popover(
                        isPresented: Binding(
                            get: { editingSavedToolID == saved.id },
                            set: { presented in
                                if !presented && editingSavedToolID == saved.id {
                                    editingSavedToolID = nil
                                }
                            }
                        ),
                        arrowEdge: .top
                    ) {
                        savedToolEditor(saved)
                    }
                }

'''
                text = text[:start] + block + text[end:]

        color_control = '''                if tool.supportsColor {
                    ColorPicker("Color", selection: toolColorBinding, supportsOpacity: false)
                        .labelsHidden()
                        .frame(width: 30)
                }

'''
        width_control = '''                if tool.supportsWidth {
                    CompactThicknessSlider(value: $pencil.width, range: 0.5...60, step: 0.5)
                        .frame(width: 108, height: 24)
                }

'''
        opacity_control = '''                if tool.supportsColor {
                    Slider(value: $toolOpacity, in: 0.05...1.0, step: 0.05)
                        .frame(width: 88)
                        .help("Opacity")
                }

'''
        text = text.replace(color_control, "").replace(width_control, "").replace(opacity_control, "")

        if "private func savedToolEditor(" not in text:
            anchor = "    /// Applies one persistent toolbar drawing tool.\n"
            editor = '''    /// Edits one Pencil/Highlighter configuration in a dedicated popup.
    @ViewBuilder
    private func savedToolEditor(_ saved: SavedDrawingTool) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: saved.kind == .highlighter ? "highlighter" : "pencil")
                Text(saved.kind == .highlighter ? "Highlighter" : "Pencil")
                    .font(.headline)
                Spacer()
            }

            ColorPicker("Color", selection: toolColorBinding, supportsOpacity: false)

            VStack(alignment: .leading, spacing: 4) {
                Text("Thickness")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Slider(value: $pencil.width, in: 0.5...60, step: 0.5)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Transparency")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Slider(
                    value: Binding(
                        get: { 1.0 - toolOpacity },
                        set: { toolOpacity = 1.0 - $0 }
                    ),
                    in: 0.0...0.95,
                    step: 0.05
                )
            }

            HStack {
                Button {
                    if let newID = savedTools.add(
                        kind: saved.kind,
                        color: pencil.color,
                        width: pencil.width,
                        opacity: toolOpacity,
                        after: saved.id
                    ) {
                        editingSavedToolID = newID
                    }
                } label: {
                    Label("Add after current", systemImage: "plus")
                }
                .buttonStyle(.borderedProminent)

                Button("Change current") {
                    savedTools.update(
                        id: saved.id,
                        kind: saved.kind,
                        color: pencil.color,
                        width: pencil.width,
                        opacity: toolOpacity
                    )
                }
                .buttonStyle(.bordered)
            }

            Divider()
            Text("Saved \(saved.kind == .highlighter ? "highlighters" : "pencils")")
                .font(.caption)
                .foregroundStyle(.secondary)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(savedTools.tools.filter { $0.kind == saved.kind }) { other in
                        Button {
                            applySavedTool(other)
                            editingSavedToolID = other.id
                        } label: {
                            Image(systemName: other.kind == .highlighter ? "highlighter" : "pencil")
                                .foregroundStyle(Color(hex: other.colorHex).opacity(other.opacity))
                                .frame(width: 32, height: 28)
                                .background(
                                    other.id == saved.id ? Color.accentColor.opacity(0.16) : Color.clear,
                                    in: RoundedRectangle(cornerRadius: 7)
                                )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            Button("Delete current tool", role: .destructive) {
                savedTools.remove(id: saved.id)
                editingSavedToolID = nil
            }
        }
        .padding(18)
        .frame(minWidth: 360)
        .onAppear {
            applySavedTool(saved)
        }
    }

'''
            text = self._replace_once(text, anchor, editor + anchor)

        return self._write_if_changed(path, original, text)

    def _patch_canvas_selection(self) -> bool:
        path = self.source_root / "Views" / "PencilCanvasView.swift"
        if not path.is_file():
            return False
        original = path.read_text(encoding="utf-8")
        text = original

        text = text.replace(
            "        moveHandle.backgroundColor = .systemBlue\n",
            "        moveHandle.backgroundColor = UIColor.systemGray3.withAlphaComponent(0.72)\n",
            1,
        )
        text = text.replace(
            "        moveHandle.layer.borderColor = UIColor.white.cgColor\n",
            "        moveHandle.layer.borderColor = UIColor.systemGray5.cgColor\n",
            1,
        )
        text = text.replace(
            "        let moveWidth = 46.0 / scale\n        let moveHeight = 24.0 / scale\n",
            "        let moveWidth = 34.0 / scale\n        let moveHeight = 18.0 / scale\n",
            1,
        )
        text = text.replace(
            "y: max(moveHeight / 2, bounds.minY - 16.0 / scale)",
            "y: max(moveHeight / 2, bounds.minY - 13.0 / scale)",
            1,
        )

        # A stroke path point is local to PKStroke.transform. Testing the raw
        # local point after a previous move/resize can select the wrong stroke.
        text = text.replace(
            "if pointInPolygon(point.location, polygon: lassoPoints) {",
            "if pointInPolygon(point.location.applying(stroke.transform), polygon: lassoPoints) {",
            1,
        )

        if "ND_MIGRATION4_PRESERVE_STROKE_THICKNESS" not in text:
            helper_anchor = '''        /// Applies one uniform transform to only the selected stroke indices while the opposite corner stays fixed.
        private func applyResize(
'''
            helper = '''        // ND_MIGRATION4_PRESERVE_STROKE_THICKNESS
        /// Applies only geometry to a stroke while preserving each PencilKit control-point size.
        private func strokeByApplyingGeometryTransform(
            _ stroke: PKStroke,
            transform: CGAffineTransform
        ) -> PKStroke {
            let points = stroke.path.map { point in
                PKStrokePoint(
                    location: point.location.applying(stroke.transform).applying(transform),
                    timeOffset: point.timeOffset,
                    size: point.size,
                    opacity: point.opacity,
                    force: point.force,
                    azimuth: point.azimuth,
                    altitude: point.altitude
                )
            }
            let path = PKStrokePath(
                controlPoints: points,
                creationDate: Date()
            )
            return PKStroke(
                ink: stroke.ink,
                transform: .identity,
                path: path
            )
        }

'''
            text = self._replace_once(text, helper_anchor, helper + helper_anchor)

            old_resize = '''            var selectedDrawing = PKDrawing(strokes: selectedStrokes)
            selectedDrawing.transform(using: transform)
            var allStrokes = session.originalDrawing.strokes
            for (offset, index) in validIndices.enumerated() where offset < selectedDrawing.strokes.count {
                allStrokes[index] = selectedDrawing.strokes[offset]
            }
'''
            new_resize = '''            let selectedDrawing = PKDrawing(
                strokes: selectedStrokes.map {
                    strokeByApplyingGeometryTransform($0, transform: transform)
                }
            )
            var allStrokes = session.originalDrawing.strokes
            for (offset, index) in validIndices.enumerated() where offset < selectedDrawing.strokes.count {
                allStrokes[index] = selectedDrawing.strokes[offset]
            }
'''
            # There is also a translation-only selectedDrawing transform in the
            # move path. Replace only the resize occurrence by anchoring on the
            # scaled transform immediately before it.
            scaled_anchor = '''            let transform = CGAffineTransform(translationX: fixed.x, y: fixed.y)
                .scaledBy(x: scale, y: scale)
                .translatedBy(x: -fixed.x, y: -fixed.y)

''' + old_resize
            scaled_new = '''            let transform = CGAffineTransform(translationX: fixed.x, y: fixed.y)
                .scaledBy(x: scale, y: scale)
                .translatedBy(x: -fixed.x, y: -fixed.y)

''' + new_resize
            text = self._replace_once(text, scaled_anchor, scaled_new)

        return self._write_if_changed(path, original, text)
