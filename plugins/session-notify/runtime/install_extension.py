#!/usr/bin/env python3
"""Build and install (or remove) the VS Code WSL extension that tracks terminals.

Run it from a VS Code integrated terminal (it needs the live VS Code connection of the `code` CLI):

  install_extension.py              # build the .vsix and install it
  install_extension.py --uninstall  # remove it
  install_extension.py --build-only # only write dist/*.vsix
"""

import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
EXTENSION_DIR = HERE / "extension"
DIST = HERE / "dist"


def build_vsix() -> Path:
    manifest = json.loads((EXTENSION_DIR / "package.json").read_text(encoding="utf-8"))
    name, version, publisher = manifest["name"], manifest["version"], manifest["publisher"]
    engine = manifest["engines"]["vscode"]
    DIST.mkdir(exist_ok=True)
    output = DIST / f"{name}-{version}.vsix"
    vsixmanifest = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">'
        f'<Metadata><Identity Language="en-US" Id="{name}" Version="{version}" Publisher="{publisher}"/>'
        f'<DisplayName>{manifest["displayName"]}</DisplayName>'
        f'<Description xml:space="preserve">{manifest["description"]}</Description>'
        "<Tags/><Categories>Other</Categories><GalleryFlags>Public</GalleryFlags>"
        f'<Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="{engine}"/></Properties>'
        '</Metadata><Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>'
        "<Dependencies/><Assets>"
        '<Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>'
        "</Assets></PackageManifest>"
    )
    content_types = (
        '<?xml version="1.0"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="json" ContentType="application/json"/>'
        '<Default Extension="js" ContentType="application/javascript"/>'
        '<Default Extension="vsixmanifest" ContentType="text/xml"/></Types>'
    )
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("extension.vsixmanifest", vsixmanifest)
        z.writestr("[Content_Types].xml", content_types)
        for file in ("package.json", "extension.js"):
            z.write(EXTENSION_DIR / file, f"extension/{file}")
    return output


def extension_id() -> str:
    manifest = json.loads((EXTENSION_DIR / "package.json").read_text(encoding="utf-8"))
    return f"{manifest['publisher']}.{manifest['name']}"


def find_code_cli() -> tuple[str, dict[str, str]]:
    """Locate a `code` CLI that is connected to a live VS Code window."""
    server = Path.home() / ".vscode-server"
    binaries = list(server.glob("bin/*/bin/remote-cli/code"))
    binaries += list(server.glob("cli/servers/*/server/bin/remote-cli/code"))
    binaries.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    on_path = shutil.which("code")
    if on_path:
        binaries.insert(0, Path(on_path))
    sockets = sorted(
        Path(f"/run/user/{os.getuid()}").glob("vscode-ipc-*.sock"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    envs = [os.environ.copy()] + [{**os.environ, "VSCODE_IPC_HOOK_CLI": str(s)} for s in sockets]
    for binary in binaries:
        for env in envs:
            try:
                result = subprocess.run(
                    [str(binary), "--list-extensions"], env=env, capture_output=True, text=True, timeout=15
                )
            except (OSError, subprocess.SubprocessError):
                continue
            if result.returncode == 0:
                return str(binary), env
    raise SystemExit(
        "No live VS Code WSL connection found. Open this folder in VS Code (Remote - WSL) and run this "
        "script from its integrated terminal."
    )


def main() -> None:
    if "--build-only" in sys.argv:
        print(build_vsix())
        return
    code, env = find_code_cli()
    if "--uninstall" in sys.argv:
        subprocess.run([code, "--uninstall-extension", extension_id()], env=env, check=False)
        return
    vsix = build_vsix()
    subprocess.run([code, "--install-extension", str(vsix), "--force"], env=env, check=True)
    print("Installed. Run 'Developer: Reload Window' in each open VS Code WSL window to activate it.")


if __name__ == "__main__":
    main()
