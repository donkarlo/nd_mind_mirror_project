"""Centralize the remaining runtime extensions for editor performance and selection bookmarks.

The application is class/controller based. This module is the single compatibility
layer for behaviors that still need to adapt legacy classes at startup; keeping
those adaptations here prevents migration-specific and one-off patch modules from
stacking independently.
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QImage

from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
from nd_mind_mirror.ui.editor.generic.generic_text_editor import GenericTextEditor
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.yaml.yaml_editor import YamlEditor
from nd_mind_mirror.ui.panel.preview.preview_panel import PreviewPanel
from nd_mind_mirror.ui.preview.latex.latex_preview import LatexPreview
from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import SelectablePdfView
from nd_mind_mirror.ui.window.main.visual_persian_font_core import VisualPersianFontController


def _int_setting(
    settings: YamlSettings,
    section: str,
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(settings._get(section, key, default=default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


class EditorRuntimeExtensions:
    """Install the one remaining legacy adaptation layer exactly once."""

    _installed = False

    @classmethod
    def install(cls) -> None:
        if cls._installed:
            return
        cls._configure_persian_font_defaults()
        cls._install_source_layout_settings()
        cls._install_preview_render_settings()
        cls._installed = True

    @staticmethod
    def _configure_persian_font_defaults() -> None:
        """Use the same Persian fallback order as the shipped settings."""
        VisualPersianFontController.DEFAULT_FONT_FAMILY = "Noto Sans Arabic"
        VisualPersianFontController._FALLBACK_FAMILIES = (
            "Noto Sans Arabic",
            "Noto Naskh Arabic",
            "Vazirmatn",
            "DejaVu Sans",
        )

    @staticmethod
    def _install_source_layout_settings() -> None:
        """Apply one configurable debounce to incremental source relayout."""
        for editor_class in (LatexEditor, GenericTextEditor, YamlEditor):
            original_apply: Callable = editor_class.apply_settings

            def apply_settings(editor, app_settings, _original=original_apply) -> None:
                _original(editor, app_settings)
                timer = getattr(editor, "_block_layout_timer", None)
                if timer is not None:
                    timer.setInterval(
                        _int_setting(
                            app_settings,
                            "editor",
                            "source_layout_update_debounce_ms",
                            40,
                            0,
                            1000,
                        )
                    )

            editor_class.apply_settings = apply_settings

    @classmethod
    def _configure_pdf_view(
        cls,
        pdf_view: SelectablePdfView,
        settings: YamlSettings,
    ) -> None:
        """Apply bounded PDF zoom and a cheaper manual-Fit raster scan."""
        minimum_percent = _int_setting(
            settings, "preview", "min_zoom_percent", 20, 5, 100
        )
        maximum_percent = _int_setting(
            settings,
            "preview",
            "max_zoom_percent",
            500,
            minimum_percent,
            1200,
        )
        pdf_view._MIN_ZOOM = minimum_percent / 100.0
        pdf_view._MAX_ZOOM = maximum_percent / 100.0
        pdf_view._nd_fit_raster_width_px = _int_setting(
            settings, "preview", "fit_raster_width_px", 480, 160, 2400
        )
        pdf_view._nd_fit_raster_sample_step_px = _int_setting(
            settings, "preview", "fit_raster_sample_step_px", 4, 1, 16
        )
        pdf_view._rendered_bounds_cache.clear()
        root = pdf_view.rootObject()
        if root is None:
            return
        root.setProperty("minSafeZoomScale", float(pdf_view._MIN_ZOOM))
        root.setProperty("maxSafeZoomScale", float(pdf_view._MAX_ZOOM))
        try:
            current = float(root.property("zoomScale"))
        except (TypeError, ValueError):
            current = 1.0
        root.setProperty(
            "zoomScale",
            max(pdf_view._MIN_ZOOM, min(current, pdf_view._MAX_ZOOM)),
        )

    @classmethod
    def _install_preview_render_settings(cls) -> None:
        """Use settings-driven limits without allocating large Fit textures."""

        def rendered_bounds(
            pdf_view,
            page_index: int,
            page_width_points: float,
            page_height_points: float,
        ):
            if page_width_points <= 0 or page_height_points <= 0:
                return None
            cache_key = (str(pdf_view._fit_document_path or ""), int(page_index))
            if cache_key in pdf_view._rendered_bounds_cache:
                return pdf_view._rendered_bounds_cache[cache_key]
            try:
                width = max(
                    int(getattr(pdf_view, "_nd_fit_raster_width_px", 480)), 1
                )
                step = max(
                    int(getattr(pdf_view, "_nd_fit_raster_sample_step_px", 4)), 1
                )
                height = max(
                    1,
                    int(round(width * page_height_points / page_width_points)),
                )
                image = pdf_view._fit_document.render(
                    int(page_index), QSize(width, height)
                )
                if image.isNull():
                    return None
                image = image.convertToFormat(QImage.Format.Format_RGBA8888)
                width, height = image.width(), image.height()
                data = bytes(image.constBits())
                stride = image.bytesPerLine()
                min_x, max_x = width, -1
                for y in range(0, height, step):
                    row = y * stride
                    for x in range(0, width, step):
                        offset = row + x * 4
                        red, green, blue, alpha = data[offset : offset + 4]
                        if alpha >= 8 and (
                            red < 248 or green < 248 or blue < 248
                        ):
                            min_x = min(min_x, x)
                            max_x = max(max_x, x)
                if max_x < min_x:
                    pdf_view._rendered_bounds_cache[cache_key] = None
                    return None
                scale = page_width_points / float(width)
                result = (
                    min_x * scale,
                    min((max_x + step) * scale, page_width_points),
                )
                pdf_view._rendered_bounds_cache[cache_key] = result
                return result
            except Exception:
                pdf_view._rendered_bounds_cache[cache_key] = None
                return None

        SelectablePdfView._rendered_ink_x_bounds_points = rendered_bounds

        def set_default_zoom_percent(preview, percent: int | float) -> None:
            minimum = float(preview._pdf_view._MIN_ZOOM) * 100.0
            maximum = float(preview._pdf_view._MAX_ZOOM) * 100.0
            preview._default_zoom_percent = max(
                minimum, min(float(percent), maximum)
            )
            if preview._current_pdf_path is not None and not preview._fit_active:
                preview._pdf_view.set_zoom_percent(preview._default_zoom_percent)

        LatexPreview.set_default_zoom_percent = set_default_zoom_percent

        original_panel_apply: Callable = PreviewPanel.apply_settings

        def panel_apply(panel, *args, **kwargs) -> None:
            original_panel_apply(panel, *args, **kwargs)
            settings = getattr(panel.window(), "_app_settings", None)
            if not isinstance(settings, YamlSettings):
                return
            cls._configure_pdf_view(panel._preview._pdf_view, settings)
            panel._nd_min_zoom_percent = int(
                round(panel._preview._pdf_view._MIN_ZOOM * 100)
            )
            panel._nd_max_zoom_percent = int(
                round(panel._preview._pdf_view._MAX_ZOOM * 100)
            )
            panel._zoom_edit.setToolTip(
                "PDF zoom percentage "
                f"({panel._nd_min_zoom_percent}% to {panel._nd_max_zoom_percent}%)"
            )

        PreviewPanel.apply_settings = panel_apply

        def apply_zoom_edit(panel) -> None:
            raw = panel._zoom_edit.text().strip().rstrip("%").strip()
            try:
                percent = int(round(float(raw)))
            except ValueError:
                percent = int(round(float(panel._preview._default_zoom_percent)))
            minimum = int(getattr(panel, "_nd_min_zoom_percent", 20))
            maximum = int(getattr(panel, "_nd_max_zoom_percent", 500))
            percent = max(minimum, min(percent, maximum))
            panel._zoom_edit.setText(f"{percent}%")
            panel._preview.set_zoom_percent(percent)

        PreviewPanel._apply_zoom_edit = apply_zoom_edit
