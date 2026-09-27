"""Small ctypes wrapper around the system Hunspell library."""

from __future__ import annotations

import codecs
import ctypes
import ctypes.util
from pathlib import Path


class HunspellDictionary:
    """Load one Hunspell dictionary lazily and expose spell/suggest/add operations."""

    _FALLBACK_LIBRARIES = (
        "/usr/lib/x86_64-linux-gnu/libhunspell-1.7.so.0",
        "/usr/lib/libhunspell-1.7.so.0",
    )

    def __init__(self, aff_path: str | Path, dic_path: str | Path) -> None:
        self._aff_path = Path(aff_path)
        self._dic_path = Path(dic_path)
        self._library = self._load_library()
        self._configure_api()
        self._handle = self._library.Hunspell_create(
            str(self._aff_path).encode(),
            str(self._dic_path).encode(),
        )
        if not self._handle:
            raise RuntimeError(f"Could not load Hunspell dictionary: {self._dic_path}")
        raw_encoding = self._library.Hunspell_get_dic_encoding(self._handle)
        encoding = raw_encoding.decode("ascii", errors="replace") if raw_encoding else "UTF-8"
        try:
            self._encoding = codecs.lookup(encoding).name
        except LookupError:
            self._encoding = "utf-8"

    @classmethod
    def _load_library(cls):
        candidate = ctypes.util.find_library("hunspell-1.7")
        if candidate:
            try:
                return ctypes.CDLL(candidate)
            except OSError:
                pass
        for raw_path in cls._FALLBACK_LIBRARIES:
            path = Path(raw_path)
            if not path.exists():
                continue
            try:
                return ctypes.CDLL(str(path))
            except OSError:
                continue
        raise RuntimeError("Hunspell 1.7 library is not available")

    def _configure_api(self) -> None:
        lib = self._library
        lib.Hunspell_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.Hunspell_create.restype = ctypes.c_void_p
        lib.Hunspell_destroy.argtypes = [ctypes.c_void_p]
        lib.Hunspell_get_dic_encoding.argtypes = [ctypes.c_void_p]
        lib.Hunspell_get_dic_encoding.restype = ctypes.c_char_p
        lib.Hunspell_spell.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.Hunspell_spell.restype = ctypes.c_int
        list_pointer = ctypes.POINTER(ctypes.c_char_p)
        lib.Hunspell_suggest.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(list_pointer),
            ctypes.c_char_p,
        ]
        lib.Hunspell_suggest.restype = ctypes.c_int
        lib.Hunspell_free_list.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(list_pointer),
            ctypes.c_int,
        ]
        lib.Hunspell_add.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.Hunspell_add.restype = ctypes.c_int

    def _encode(self, word: str) -> bytes | None:
        try:
            return str(word).encode(self._encoding)
        except UnicodeEncodeError:
            return None

    def spell(self, word: str) -> bool:
        encoded = self._encode(word)
        if encoded is None or not self._handle:
            return False
        return bool(self._library.Hunspell_spell(self._handle, encoded))

    def suggest(self, word: str, limit: int = 8) -> list[str]:
        encoded = self._encode(word)
        if encoded is None or not self._handle:
            return []
        suggestions = ctypes.POINTER(ctypes.c_char_p)()
        count = self._library.Hunspell_suggest(
            self._handle,
            ctypes.byref(suggestions),
            encoded,
        )
        result: list[str] = []
        try:
            for index in range(max(int(count), 0)):
                raw = suggestions[index]
                if not raw:
                    continue
                value = raw.decode(self._encoding, errors="replace").strip()
                if value and value not in result:
                    result.append(value)
                if len(result) >= max(int(limit), 1):
                    break
        finally:
            if count > 0:
                self._library.Hunspell_free_list(
                    self._handle,
                    ctypes.byref(suggestions),
                    int(count),
                )
        return result

    def add(self, word: str) -> None:
        encoded = self._encode(word)
        if encoded is None or not self._handle:
            return
        self._library.Hunspell_add(self._handle, encoded)
    def close(self) -> None:
        if not getattr(self, "_handle", None):
            return
        self._library.Hunspell_destroy(self._handle)
        self._handle = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
