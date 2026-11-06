#!/usr/bin/env python3
"""Set the manifest version and build dist/ft_homeassistant.zip.

Usage: python3 scripts/build_release.py X.Y.Z
"""

import json
import re
import sys
import zipfile
from pathlib import Path

DOMAIN = "ft_homeassistant"
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "custom_components" / DOMAIN


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
        sys.exit(__doc__)
    version = sys.argv[1]

    manifest_path = SRC / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = version
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    target = dist / f"{DOMAIN}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SRC.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                # Integration files at the zip root, as HACS expects.
                zf.write(path, path.relative_to(SRC))
    print(f"Built {target.relative_to(ROOT)} for version {version}")


if __name__ == "__main__":
    main()
