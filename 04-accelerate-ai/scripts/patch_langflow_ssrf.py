#!/usr/bin/env python3
"""Build a Langflow-patched ADK compose file after pip install.

Stock `compose-lite.yml` only forwards a few LANGFLOW_* keys into the container.
This copies the installed ADK compose into `.adk/docker-compose.yml` (gitignored)
and adds LANGFLOW_SSRF_PROTECTION_ENABLED. `scripts/start_wxo.sh` points
`orchestrate server start --compose-file` at that copy, so a new
`pip install ibm-watsonx-orchestrate` is picked up on the next start.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ENV_KEY = "LANGFLOW_SSRF_PROTECTION_ENABLED"
COMPOSE_LINE = f"      {ENV_KEY}: ${{{ENV_KEY}:-false}}\n"
DOTENV_BLOCK = (
    f"\n# Allow Langflow API Request to call the host ops API on :8081 "
    f"(private Docker IPs).\n{ENV_KEY}=false\n"
)


def _stock_compose() -> Path:
    try:
        import ibm_watsonx_orchestrate
    except ImportError as exc:
        raise SystemExit(
            "ibm-watsonx-orchestrate is not installed in this environment. "
            "Activate the repo venv and run: pip install -r requirements.txt"
        ) from exc

    path = (
        Path(ibm_watsonx_orchestrate.__file__).resolve().parent
        / "developer_edition"
        / "resources"
        / "docker"
        / "compose-lite.yml"
    )
    if not path.is_file():
        raise SystemExit(f"ADK compose file not found: {path}")
    return path


def patched_compose_text(stock: str) -> str:
    if re.search(rf"^[ \t]+{re.escape(ENV_KEY)}:", stock, flags=re.M):
        return stock
    updated, n = re.subn(
        r"^([ \t]+LANGFLOW_AUTO_LOGIN:.*\n)",
        rf"\1{COMPOSE_LINE}",
        stock,
        count=1,
        flags=re.M,
    )
    if n != 1:
        raise SystemExit(
            "Could not find LANGFLOW_AUTO_LOGIN in the ADK compose file. "
            "The layout may have changed — add "
            f"{ENV_KEY} under the langflow service environment by hand."
        )
    return updated


def ensure_dotenv(path: Path) -> str:
    if not path.is_file():
        return "missing"
    text = path.read_text(encoding="utf-8")
    if re.search(rf"^{re.escape(ENV_KEY)}=", text, flags=re.M):
        return "already set"
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + DOTENV_BLOCK, encoding="utf-8")
    return "added"


def main() -> int:
    chapter = Path(__file__).resolve().parent.parent
    dest_dir = chapter / ".adk"
    dest = dest_dir / "docker-compose.yml"
    dest_dir.mkdir(parents=True, exist_ok=True)

    stock_path = _stock_compose()
    dest.write_text(
        patched_compose_text(stock_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    print(f"wrote: {dest}")
    print(f"source: {stock_path}")

    for name in (".env", ".env.example"):
        print(f"{ensure_dotenv(chapter / name)}: {chapter / name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
