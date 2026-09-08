from pathlib import Path

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu

from nd_mind_mirror.core.render.latex.profile.latex_preview_profile import (
    LatexPreviewProfileRegistry,
)
from nd_mind_mirror.core.settings.yaml.yaml_scalar_setting_writer import (
    YamlScalarSettingWriter,
)


class LatexPreviewProfileController:
    """Own Settings-menu profile selection, template editing, and Preview source state."""

    def __init__(self, window) -> None:
        self._window = window
        self._actions: dict[str, QAction] = {}
        self._load_menu: QMenu | None = None
        self._connect_renderer_state()
        self._install_settings_menu()
        self.reload_settings(refresh=True)

    def reload_settings(self, refresh: bool = False) -> None:
        settings = self._window._app_settings
        registry = settings.preview_latex_profile_registry()
        renderer = self._window._renderer
        renderer.configure_preview_profiles(
            active_profile=registry.active_profile,
            default_template_path=registry.template_path("default"),
            graph_template_path=registry.template_path("graph"),
            german_template_path=registry.template_path("german"),
            beamer_template_path=registry.template_path("beamer"),
        )
        self._configure_diagnostic_builder(registry)
        for key, action in self._actions.items():
            action.blockSignals(True)
            action.setChecked(key == registry.active_profile)
            action.blockSignals(False)
        if refresh:
            self._window._refresh_current_preview(immediate=True)

    def _connect_renderer_state(self) -> None:
        renderer = self._window._renderer
        renderer.cached_preview_available.connect(
            self._window._preview_panel.show_pdf
        )
        renderer.preview_source_empty.connect(self._show_rendering_message)

    def _install_settings_menu(self) -> None:
        settings_menu = self._find_settings_menu()
        if settings_menu is None:
            return

        default_action = getattr(
            self._window,
            "_edit_preview_template_action",
            None,
        )
        beamer_action = getattr(
            self._window,
            "_edit_beamer_preview_template_action",
            None,
        )
        reload_action = getattr(
            self._window,
            "_reload_settings_action",
            None,
        )

        if default_action is not None:
            default_action.setText("Edit Default preview template")
        if beamer_action is not None:
            beamer_action.setText("Edit Beamer preview template")

        graph_edit = QAction("Edit Graph preview template", self._window)
        graph_edit.triggered.connect(
            lambda: self._open_template("graph")
        )
        german_edit = QAction("Edit German preview template", self._window)
        german_edit.triggered.connect(
            lambda: self._open_template("german")
        )

        before = beamer_action or reload_action
        if before is not None:
            settings_menu.insertAction(before, graph_edit)
            settings_menu.insertAction(before, german_edit)
        else:
            settings_menu.addAction(graph_edit)
            settings_menu.addAction(german_edit)

        self._load_menu = QMenu("LaTeX Preview Load", settings_menu)
        group = QActionGroup(self._load_menu)
        group.setExclusive(True)
        for key in LatexPreviewProfileRegistry.keys():
            action = QAction(
                LatexPreviewProfileRegistry.label_for(key),
                self._load_menu,
            )
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, profile=key: (
                    self._activate_profile(profile) if checked else None
                )
            )
            group.addAction(action)
            self._load_menu.addAction(action)
            self._actions[key] = action

        if reload_action is not None:
            settings_menu.insertMenu(reload_action, self._load_menu)
        else:
            settings_menu.addMenu(self._load_menu)

    def _activate_profile(self, profile: str) -> None:
        profile = LatexPreviewProfileRegistry.normalize(profile)
        settings = self._window._app_settings
        try:
            YamlScalarSettingWriter(settings.settings_path).set_section_value(
                "preview",
                "latex_profile",
                profile,
            )
        except OSError as exc:
            self._window.statusBar().showMessage(
                f"Could not save LaTeX Preview load: {exc}",
                5000,
            )
            self.reload_settings(refresh=False)
            return

        if not settings.reload():
            self._window.statusBar().showMessage(
                settings.last_reload_error or "Could not reload settings.yaml.",
                5000,
            )
            return
        self.reload_settings(refresh=True)
        self._window.statusBar().showMessage(
            "LaTeX Preview load: "
            + LatexPreviewProfileRegistry.label_for(profile),
            3000,
        )

    def _open_template(self, profile: str) -> None:
        registry = self._window._app_settings.preview_latex_profile_registry()
        path = registry.template_path(profile)
        if not path.is_file():
            self._window.statusBar().showMessage(
                f"Preview template does not exist: {path}",
                5000,
            )
            return
        self._window._open_path(str(path))

    def _configure_diagnostic_builder(
        self,
        registry: LatexPreviewProfileRegistry,
    ) -> None:
        builder = getattr(self._window, "_latex_diagnostic_builder", None)
        if builder is None:
            return
        builder.configure(
            default_path=self._window._app_settings.search_default_path,
            template_path=registry.active_template_path,
            beamer_template_path=registry.template_path("beamer"),
        )

    def _show_rendering_message(self, source_path: str) -> None:
        name = Path(source_path).name if source_path else "LaTeX source"
        self._window._preview_panel.show_message(f"Rendering {name}…")

    def _find_settings_menu(self) -> QMenu | None:
        for action in self._window.menuBar().actions():
            if action.text().replace("&", "").strip() != "Settings":
                continue
            return action.menu()
        return None
