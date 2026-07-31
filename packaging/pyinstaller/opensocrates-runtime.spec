# PyInstaller build-only spec for the Codex-selector prototype runtime.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


ROOT = Path(SPECPATH).resolve().parents[1]
SOURCE_ENTRY = ROOT / "src" / "opensocrates" / "__main__.py"
ENTRY = ROOT / "packaging" / "pyinstaller" / "runtime_entry.py"
if not SOURCE_ENTRY.is_file():
    raise SystemExit("runtime entry point is not present: src/opensocrates/__main__.py")
if not ENTRY.is_file():
    raise SystemExit(
        "PyInstaller runtime wrapper is not present: packaging/pyinstaller/runtime_entry.py"
    )


datas = []
for relative in (
    "schemas/v1",
    "content/compiled-content.bundle.json",
    "content/compiled-reasoning-content.bundle.json",
    "content/locales",
):
    source = ROOT / relative
    if source.is_file():
        datas.append((str(source), str(Path(relative).parent)))
    elif source.is_dir():
        datas.append((str(source), relative))
    else:
        raise SystemExit(f"required runtime data is not present: {relative}")


# The selector adapter imports the SDK dynamically from its isolated boundary,
# so static analysis alone cannot guarantee that its complete package closure
# reaches the onedir artifact. Collect the SDK, platform-matched CLI runtime,
# and Pydantic's native core explicitly from the native build environment.
#
# Pydantic itself is intentionally *not* collected recursively: its standard
# PyInstaller hook adds every public, deprecated, v1, experimental, and mypy
# module. That build-only surface both duplicates the modules Analysis reaches
# through the SDK and harms cold launcher startup. The local hook supplies the
# dynamic public imports while Analysis follows their real runtime closure; it
# omits only v1 and mypy. Distribution metadata remains present for
# version-aware SDK behavior.
# PyInstaller does not cross-compile these assets: a native build must use the
# matching locked wheel, and the resulting artifact still requires platform,
# signing, and clean-host verification before any release claim.
sdk_datas = list(copy_metadata("pydantic"))
sdk_binaries = []
sdk_hiddenimports = []
for package_name in ("openai_codex", "codex_cli_bin", "pydantic_core"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    sdk_datas.extend(package_datas)
    sdk_binaries.extend(package_binaries)
    sdk_hiddenimports.extend(package_hiddenimports)


a = Analysis(
    [str(ENTRY)],
    pathex=[str(ROOT / "src"), str(ROOT)],
    binaries=sdk_binaries,
    datas=datas + sdk_datas,
    hiddenimports=sorted(set(sdk_hiddenimports)),
    hookspath=[str(Path(SPECPATH).resolve())],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["ast_serialize", "librt", "mypy", "pydantic.mypy", "pydantic.v1.mypy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="opensocrates-runtime",
    exclude_binaries=True,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
bundle = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="opensocrates-runtime",
)
