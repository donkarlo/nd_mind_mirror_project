#!/usr/bin/env python3
"""Build and install the standalone Mind Mirror Android app over USB or wireless ADB."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANDROID_DIR = PROJECT_ROOT / "src" / "nd_mind_mirror" / "mobile" / "android"
APK_PATH = ANDROID_DIR / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
TECTONIC_LIBRARY_PATH = (
    ANDROID_DIR
    / "app"
    / "src"
    / "main"
    / "jniLibs"
    / "arm64-v8a"
    / "libtexslate_native.so"
)
STATE_PATH = Path.home() / ".config" / "nd_mind_mirror" / "android_installer.json"


def run(
    command: list[str],
    *,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(command), flush=True)
    result = subprocess.run(
        command,
        cwd=str(ANDROID_DIR) if command and command[0].endswith("gradlew") else None,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if capture and result.stdout:
        print(result.stdout.rstrip())
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}.")
    return result


def load_state() -> dict[str, str]:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return {str(key): str(value) for key, value in data.items()}
    except (OSError, ValueError, TypeError):
        return {}


def save_state(state: dict[str, str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def ask(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def find_adb() -> Path:
    candidates = [
        Path.home() / "Android" / "Sdk" / "platform-tools" / "adb",
        Path("/usr/lib/android-sdk/platform-tools/adb"),
    ]
    system = shutil.which("adb")
    if system:
        candidates.append(Path(system))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise RuntimeError("Android SDK platform-tools/adb was not found.")


def connected_devices(adb: Path) -> list[str]:
    result = subprocess.run(
        [str(adb), "devices"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    devices: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def connect_wireless(adb: Path, state: dict[str, str]) -> None:
    host = ask("Phone IP address", state.get("phone_host", ""))
    port = ask("Wireless debugging connection port", state.get("phone_port", ""))
    if not host or not port:
        return

    state["phone_host"] = host
    state["phone_port"] = port
    run([str(adb), "connect", f"{host}:{port}"], check=False, capture=True)
    if connected_devices(adb):
        save_state(state)
        return

    answer = ask("Pair first? y/N", "N").lower()
    if answer not in {"y", "yes", "j", "ja"}:
        save_state(state)
        return

    pair_port = ask("Pairing port", state.get("pair_port", ""))
    pair_code = ask("6-digit pairing code")
    if not pair_port or not pair_code:
        return

    state["pair_port"] = pair_port
    run(
        [str(adb), "pair", f"{host}:{pair_port}", pair_code],
        check=False,
        capture=True,
    )
    port = ask("Wireless debugging connection port after pairing", port)
    state["phone_port"] = port
    run([str(adb), "connect", f"{host}:{port}"], check=False, capture=True)
    save_state(state)


def choose_device(devices: list[str], state: dict[str, str]) -> str:
    if len(devices) == 1:
        return devices[0]

    last = state.get("serial", "")
    print("Connected Android devices:")
    for index, serial in enumerate(devices, 1):
        suffix = " (last used)" if serial == last else ""
        print(f"  {index}. {serial}{suffix}")

    default_index = next(
        (index for index, serial in enumerate(devices, 1) if serial == last),
        1,
    )
    while True:
        try:
            return devices[int(ask("Device number", str(default_index))) - 1]
        except (ValueError, IndexError):
            print("Choose a valid device number.")


def prepare_android_sdk(adb: Path) -> None:
    sdk_root = adb.parent.parent
    local_properties = ANDROID_DIR / "local.properties"
    desired = f"sdk.dir={sdk_root}\n"
    try:
        current = local_properties.read_text(encoding="utf-8")
    except OSError:
        current = ""
    if current != desired:
        local_properties.write_text(desired, encoding="utf-8")


def build_apk() -> None:
    if not TECTONIC_LIBRARY_PATH.is_file():
        raise RuntimeError(
            "Embedded Tectonic library is missing. Run "
            "./scripts/android/build_native_tectonic.sh first."
        )
    gradlew = ANDROID_DIR / "gradlew"
    run([str(gradlew), ":app:assembleDebug", "--no-daemon"])
    if not APK_PATH.is_file():
        raise RuntimeError(f"APK was not created: {APK_PATH}")


def main() -> int:
    state = load_state()
    state.pop("server_url", None)
    adb = find_adb()
    prepare_android_sdk(adb)
    build_apk()

    run([str(adb), "start-server"], check=False, capture=True)
    devices = connected_devices(adb)
    if not devices:
        connect_wireless(adb, state)
        devices = connected_devices(adb)
    if not devices:
        raise RuntimeError("No authorized Android device is connected.")

    serial = choose_device(devices, state)
    run([str(adb), "-s", serial, "install", "-r", str(APK_PATH)])
    state["serial"] = serial
    save_state(state)
    print(f"Mind Mirror Android installed on {serial}.")
    print("The app runs standalone and does not require Ubuntu after installation.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
