"""Tests for the AppImage -> application-menu registration.

These drive install() against a temporary XDG data home rather than the
real one, so running the suite never touches the developer's own
application menu.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from duriancalc import desktop_integration as di


@pytest.fixture
def bundle(tmp_path: Path) -> tuple[Path, Path]:
    """A stand-in AppImage file and its mounted AppDir (with icon)."""
    appimage = tmp_path / "DurianCalc-x86_64.AppImage"
    appimage.write_bytes(b"not really an appimage")
    appdir = tmp_path / "mount"
    appdir.mkdir()
    (appdir / f"{di.APP_ID}.png").write_bytes(b"\x89PNG-pretend")
    return appimage, appdir


@pytest.fixture(autouse=True)
def no_system_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(di, "_system_entry_exists", lambda: False)
    monkeypatch.setattr(di, "_refresh_caches", lambda *a: None)


def entry_of(home: Path) -> Path:
    return home / "applications" / f"{di.APP_ID}.desktop"


def icon_of(home: Path) -> Path:
    return home / "icons" / "hicolor" / di.ICON_SIZE / "apps" / f"{di.APP_ID}.png"


def test_installs_entry_and_icon(tmp_path: Path, bundle: tuple[Path, Path]) -> None:
    appimage, appdir = bundle
    home = tmp_path / "data"

    assert di.install(appimage, appdir, data_home=home) is True

    text = entry_of(home).read_text()
    assert f"Exec={appimage}" in text
    assert f"Icon={di.APP_ID}" in text
    # Lowercase, matching the app_id -- see desktop_entry()'s comment.
    assert f"StartupWMClass={di.APP_ID}" in text
    assert "Keywords=" in text
    assert icon_of(home).read_bytes() == (appdir / f"{di.APP_ID}.png").read_bytes()


def test_second_run_is_a_no_op(tmp_path: Path, bundle: tuple[Path, Path]) -> None:
    appimage, appdir = bundle
    home = tmp_path / "data"

    assert di.install(appimage, appdir, data_home=home) is True
    assert di.install(appimage, appdir, data_home=home) is False


def test_repoints_exec_after_the_appimage_moves(
    tmp_path: Path, bundle: tuple[Path, Path]
) -> None:
    """The regression that motivated all of this: an entry left pointing
    at ~/Downloads after the AppImage was moved to ~/Apps."""
    appimage, appdir = bundle
    home = tmp_path / "data"
    di.install(appimage, appdir, data_home=home)

    moved = tmp_path / "Apps" / "DurianCalc-x86_64.AppImage"
    moved.parent.mkdir()
    appimage.rename(moved)

    assert di.install(moved, appdir, data_home=home) is True
    assert f"Exec={moved}" in entry_of(home).read_text()


def test_leaves_hand_written_entry_alone(tmp_path: Path, bundle: tuple[Path, Path]) -> None:
    appimage, appdir = bundle
    home = tmp_path / "data"
    entry = entry_of(home)
    entry.parent.mkdir(parents=True)
    mine = "[Desktop Entry]\nType=Application\nName=My Own DurianCalc\nExec=/somewhere/else\n"
    entry.write_text(mine)

    di.install(appimage, appdir, data_home=home)

    assert entry.read_text() == mine


def test_skips_when_a_system_entry_exists(
    tmp_path: Path, bundle: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    appimage, appdir = bundle
    home = tmp_path / "data"
    monkeypatch.setattr(di, "_system_entry_exists", lambda: True)

    assert di.install(appimage, appdir, data_home=home) is False
    assert not entry_of(home).exists()


def test_quotes_exec_paths_containing_spaces(tmp_path: Path, bundle: tuple[Path, Path]) -> None:
    _, appdir = bundle
    spaced = tmp_path / "My Apps"
    spaced.mkdir()
    appimage = spaced / "DurianCalc-x86_64.AppImage"
    appimage.write_bytes(b"x")
    home = tmp_path / "data"

    di.install(appimage, appdir, data_home=home)

    assert f'Exec="{appimage}"' in entry_of(home).read_text()


def test_plain_path_is_not_quoted(tmp_path: Path) -> None:
    assert di._quote_exec(Path("/home/admin/Apps/DurianCalc.AppImage")) == (
        "/home/admin/Apps/DurianCalc.AppImage"
    )


def test_install_if_appimage_no_ops_outside_a_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.delenv("APPDIR", raising=False)
    assert di.install_if_appimage() is False


def test_opt_out_env_var(monkeypatch: pytest.MonkeyPatch, bundle: tuple[Path, Path]) -> None:
    appimage, appdir = bundle
    monkeypatch.setenv("APPIMAGE", str(appimage))
    monkeypatch.setenv("APPDIR", str(appdir))
    monkeypatch.setenv("DURIANCALC_NO_DESKTOP_INTEGRATION", "1")
    assert di.install_if_appimage() is False
