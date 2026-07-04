from __future__ import annotations

from avcleaner.models import FileSnapshot, ScanItem
from avcleaner.rules import is_junk_file
from avcleaner.scanner import classify_extension


def scan_item(name: str, *, size: int = 1) -> ScanItem:
    extension = "." + name.rsplit(".", 1)[1]
    return ScanItem(
        id="item",
        path=name,
        relative_path=name,
        name=name,
        stem=name[: -len(extension)],
        extension=extension,
        size=size,
        mtime=0.0,
        kind=classify_extension(extension),
        snapshot=FileSnapshot(size=size, created_ns=1, modified_ns=1, fingerprint="test"),
    )


def test_sidecar_extensions_are_classified() -> None:
    assert classify_extension(".srt") == "sidecar"
    assert classify_extension(".ass") == "sidecar"
    assert classify_extension(".ssa") == "sidecar"
    assert classify_extension(".vtt") == "sidecar"
    assert classify_extension(".jpg") == "sidecar"
    assert classify_extension(".jpeg") == "sidecar"
    assert classify_extension(".png") == "sidecar"
    assert classify_extension(".webp") == "sidecar"
    assert classify_extension(".nfo") == "sidecar"


def test_sidecar_files_are_not_junk_by_default_even_when_empty() -> None:
    for name in ["ABP-123.srt", "ABP-123.ass", "ABP-123.jpg", "ABP-123.nfo"]:
        is_junk, reason = is_junk_file(scan_item(name, size=0), custom_keywords=[], trash_zero_byte=True)

        assert is_junk is False
        assert reason == ""


def test_sidecar_custom_junk_keyword_is_explicit_junk_rule() -> None:
    is_junk, reason = is_junk_file(scan_item("ABP-123.badpromo.srt"), custom_keywords=["badpromo"], trash_zero_byte=True)

    assert is_junk is True
    assert reason == "custom_junk_keyword"
