from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.window.main.main_window import MainWindow


class MindMirrorApplication(QApplication):
    @classmethod
    def run(cls, argv: list[str]) -> int:
        application = cls(argv)
        application.setApplicationName("nd_mind_mirror_project")
        application.setOrganizationName("nd_mind_mirror")

        window = MainWindow()
        window.show()

        return application.exec()
