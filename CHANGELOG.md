# Changelog

All notable changes to `nd_mind_mirror_project` are recorded here.

The project version in `pyproject.toml` is currently `0.31.10`. Until a version is explicitly bumped, changes are collected under **Unreleased** and grouped by date. Future project updates should update this file in the same change batch.

## [Unreleased]

### 2026-08-23

#### Added
- Draggable ordering for both the **Pinned** and **Open** tab rows.
- Persistent per-row tab ordering restored after application restart.
- Logical line-number gutters for YAML and generic text/code source editors in addition to LaTeX Source.
- `CHANGELOG.md` as the persistent update history for future project changes.

#### Changed
- README remains focused on the project's current capabilities, while chronological update history is maintained here.

### 2026-08-22

#### Added
- Two-row editor tabs: persistent pinned files above and ordinary currently open files below, with pinned files excluded from the ordinary row.
- Reverse SyncTeX navigation from an ordinary click in PDF Preview back to the corresponding LaTeX Source or Visual position.
- Logical source-line numbers that number each real source line once and do not number soft-wrapped continuation rows.
- Shared configurable source indentation: `Tab` indents and `Shift+Tab` outdents by `editor.tab_size`; shipped default is 3 spaces.
- F2 rename support for the selected Navigator file or folder.
- iPad lasso selection frame with four circular corner handles and proportional stroke resizing.

#### Changed
- LaTeX Auto Format uses the same configurable `editor.tab_size` setting as manual Tab/Shift+Tab indentation.
- Preview Auto Fit became content-aware and keeps the fitted content horizontally centered while Source/Visual synchronization changes the vertical location.
- Preview edit highlighting uses real vertical padding around the matched text instead of simulating padding with a thick border.

#### Fixed
- Pinned/Open proxy tabs map clicks and pin operations by canonical file path rather than hidden tab indexes.
- Only the actually active file is painted as selected across the two tab rows.
- Auto Fit no longer intentionally follows SyncTeX's horizontal text coordinate while Source/Visual scroll synchronization is active.
- iPad selection resizing no longer depends on `PKCanvasView.selection` or `PKStroke.id`, which are unavailable in some Swift Playgrounds SDKs.
- iPad bridge response handling covers the previously non-exhaustive Swift switch case.

---

Historical entries above were reconstructed from the recent project changes that preceded creation of this file. From this point onward, entries should be recorded at the time each update is applied.
