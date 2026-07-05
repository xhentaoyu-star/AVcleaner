from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_no_external_icon_cdn_references() -> None:
    files = [
        ROOT / "avcleaner" / "templates" / "index.html",
        ROOT / "avcleaner" / "static" / "app.js",
        ROOT / "avcleaner" / "static" / "styles.css",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    forbidden = [
        "cdn.jsdelivr",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "tabler-icons.io",
        "@tabler/icons",
    ]
    for marker in forbidden:
        assert marker not in combined


def test_icons_are_loaded_from_local_sprite() -> None:
    html = (ROOT / "avcleaner" / "templates" / "index.html").read_text(encoding="utf-8")

    assert "/static/icons.svg#icon-" in html
    assert "http://www.w3.org/2000/svg" not in html
