"""Present hierarchical file-search results without filesystem I/O on the GUI thread."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStyle, QTreeWidget, QTreeWidgetItem


class SearchResultTreePresenter:
    """Build the search result tree from indexed metadata only."""

    def __init__(
        self,
        tree: QTreeWidget,
        hit_role: int,
        directory_role: int,
    ) -> None:
        self._tree = tree
        self._hit_role = hit_role
        self._directory_role = directory_role

    def populate(
        self,
        root_path: Path,
        paths: list[Path],
        directory_flags: dict[str, bool],
    ) -> None:
        """Replace the visible tree without touching the Dropbox filesystem."""
        self._tree.setUpdatesEnabled(False)
        previous_block_state = self._tree.blockSignals(True)

        try:
            self._tree.clear()
            if not paths:
                return

            root_label = root_path.name or str(root_path)
            root_item = QTreeWidgetItem([root_label])
            root_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                str(root_path),
            )
            root_item.setData(
                0,
                self._directory_role,
                True,
            )
            root_item.setIcon(
                0,
                self._tree.style().standardIcon(
                    QStyle.StandardPixmap.SP_DirIcon
                ),
            )
            self._tree.addTopLevelItem(root_item)

            nodes: dict[str, QTreeWidgetItem] = {
                str(root_path): root_item
            }
            result_paths = {
                str(path)
                for path in paths
            }

            for path in paths:
                try:
                    relative = path.relative_to(root_path)
                except ValueError:
                    continue

                parent_path = root_path
                parent_item = root_item
                parts = relative.parts

                for index, part in enumerate(parts):
                    current_path = parent_path / part
                    current_key = str(current_path)
                    item = nodes.get(current_key)

                    if item is None:
                        item = QTreeWidgetItem([part])
                        item.setData(
                            0,
                            Qt.ItemDataRole.UserRole,
                            current_key,
                        )

                        is_intermediate = index < len(parts) - 1
                        is_directory = directory_flags.get(
                            current_key,
                            is_intermediate,
                        )
                        item.setData(
                            0,
                            self._directory_role,
                            is_directory,
                        )
                        item.setIcon(
                            0,
                            self._tree.style().standardIcon(
                                QStyle.StandardPixmap.SP_DirIcon
                                if is_directory
                                else QStyle.StandardPixmap.SP_FileIcon
                            ),
                        )
                        parent_item.addChild(item)
                        parent_item.setExpanded(True)
                        nodes[current_key] = item

                    parent_item = item
                    parent_path = current_path

            for node_path, node_item in nodes.items():
                is_hit = node_path in result_paths
                node_item.setData(
                    0,
                    self._hit_role,
                    is_hit,
                )
                if is_hit:
                    font = node_item.font(0)
                    font.setBold(True)
                    node_item.setFont(0, font)

            root_item.setExpanded(True)
        finally:
            self._tree.blockSignals(previous_block_state)
            self._tree.setUpdatesEnabled(True)
