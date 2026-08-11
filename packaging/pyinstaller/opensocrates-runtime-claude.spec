# PyInstaller build-only spec for the Claude-selector runtime.

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


# Claude selection delegates to the authenticated `claude` executable.  It
# never imports or starts the Codex SDK/CLI, so this host-specific artifact
# carries only Pydantic's native closure.  The source project retains the
# locked Codex dependencies for the separate Codex runtime build.
sdk_datas = list(copy_metadata("pydantic"))
sdk_binaries = []
sdk_hiddenimports = []
for package_name in ("pydantic_core",):
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
    excludes=[
        "ast_serialize",
        "codex_cli_bin",
        "librt",
        "mypy",
        "openai_codex",
        "pydantic.mypy",
        "pydantic.v1.mypy",
    ],
    noarchive=False,
)
# PyInstaller recognizes the Codex worker's literal distribution-version
# checks even though the Claude profile never imports those distributions.
# Remove the automatically discovered metadata along with the excluded code so
# the host package contains no misleading Codex dependency surface.
a.datas = [
    item
    for item in a.datas
    if not str(item[0]).startswith(("openai_codex-", "openai_codex_cli_bin-"))
]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
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
