from pathlib import Path
import sys
import zipfile


EXCLUDED_PARTS = {
    ".idea",
    ".pytest_cache",
    "__pycache__",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def should_include(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return True


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    output = (
        Path(sys.argv[1]).expanduser().resolve()
        if len(sys.argv) > 1
        else project_root.parent / "nd_mind_mirror_project_release.zip"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(project_root.rglob("*")):
            if not path.is_file() or not should_include(path, project_root):
                continue
            archive.write(
                path,
                Path(project_root.name) / path.relative_to(project_root),
            )

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
