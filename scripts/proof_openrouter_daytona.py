"""
Tangible proof: MiniMax (OpenRouter) produces Python → Daytona sandbox runs it → stdout here.

Usage (from repo root, with .venv activated):
  pip install -r requirements-spike.txt
  copy .env.example .env   # set OPENROUTER_API_KEY and DAYTONA_API_KEY
  python scripts/proof_openrouter_daytona.py
  python scripts/proof_openrouter_daytona.py --mode chart   # matplotlib bar chart + PNG on disk
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from daytona import Daytona, DaytonaConfig

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
CHART_PNG = ARTIFACTS / "proof_chart.png"
REMOTE_CHART = "/home/daytona/aquamind_proof.png"

MODEL = "minimax/minimax-m2.5:free"


PROMPT_PRINT = (
    "Write a tiny Python 3 script for a live demo. "
    "Output ONLY valid Python source code—no markdown, no ``` fences, no commentary. "
    "The script must print exactly 4 lines to stdout:\n"
    "  Line 1: the text 'AquaMind sandbox proof'\n"
    "  Line 2: one short fact about water usage in buildings\n"
    "  Line 3: the integer 42\n"
    "  Line 4: the text 'OK'"
)

PROMPT_CHART = (
    "Write a minimal Python 3 script for a demo. "
    "Output ONLY valid Python source code—no markdown, no ``` fences, no explanation.\n"
    "Requirements:\n"
    "- import matplotlib.pyplot as plt\n"
    "- Bar chart: x-axis two labels '2026-05-01' and '2026-05-02'; bar heights 1200 and 1800.\n"
    "- Title exactly: AquaMind Artifact Test. Y-axis label: Liters.\n"
    f"- After plotting: plt.savefig('{REMOTE_CHART}', dpi=120, bbox_inches='tight'); "
    "plt.show(); plt.close()\n"
    "- Print one line to stdout: chart_saved"
)


def strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```\w*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def openrouter_chat(api_key: str, user_prompt: str) -> str:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=body,
        timeout=120.0,
    )
    r.raise_for_status()
    data = r.json()
    msg = data["choices"][0]["message"]
    return (msg.get("content") or "").strip()


def _summarize_charts(resp) -> None:
    arts = resp.artifacts
    if not arts or not arts.charts:
        print("\n--- Daytona chart artifacts: none (sandbox may lack matplotlib or plt.show did not emit a figure) ---")
        return
    print(f"\n--- Daytona parsed charts ({len(arts.charts)}) ---")
    for i, ch in enumerate(arts.charts):
        t = getattr(ch, "type", None) or getattr(ch, "chart_type", None)
        title = getattr(ch, "title", None)
        print(f"  [{i}] type={t} title={title!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description="MiniMax → OpenRouter → Daytona code_run proof")
    ap.add_argument(
        "--mode",
        choices=("print", "chart"),
        default="print",
        help="print=four-line stdout demo; chart=matplotlib bars + proof_chart.png",
    )
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    or_key = os.environ.get("OPENROUTER_API_KEY")
    dt_key = os.environ.get("DAYTONA_API_KEY")
    if not or_key:
        print("Missing OPENROUTER_API_KEY. Copy .env.example to .env and set it.", file=sys.stderr)
        return 2
    if not dt_key:
        print("Missing DAYTONA_API_KEY. Copy .env.example to .env and set it.", file=sys.stderr)
        return 2

    prompt = PROMPT_CHART if args.mode == "chart" else PROMPT_PRINT

    print(">>> Step 1: Prompting MiniMax via OpenRouter …\n")
    raw = openrouter_chat(or_key, prompt)
    print("--- Raw model output ---\n")
    print(raw)
    print("\n--- Code sent to sandbox ---\n")
    code = strip_code_fence(raw)
    print(code)

    cfg_kwargs: dict = {
        "api_key": dt_key,
        "api_url": os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api"),
    }
    if os.environ.get("DAYTONA_TARGET"):
        cfg_kwargs["target"] = os.environ["DAYTONA_TARGET"]

    print("\n>>> Step 2: Creating Daytona sandbox and running code_run …\n")
    daytona = Daytona(DaytonaConfig(**cfg_kwargs))
    sandbox = daytona.create()
    try:
        resp = sandbox.process.code_run(code, timeout=180)
        out = resp.result or ""
        print(f"sandbox_id={sandbox.id}")
        print(f"exit_code={resp.exit_code}")
        print("\n--- Sandbox stdout ---\n")
        print(out)

        if args.mode == "chart":
            _summarize_charts(resp)
            ARTIFACTS.mkdir(parents=True, exist_ok=True)
            try:
                png = sandbox.fs.download_file(REMOTE_CHART)
                CHART_PNG.write_bytes(png)
                print(f"\n--- Saved PNG locally ---\n{CHART_PNG.resolve()}")
            except Exception as e:
                print(f"\n--- PNG download failed ({e}) ---", file=sys.stderr)
                print(f"Expected file on sandbox: {REMOTE_CHART}", file=sys.stderr)

        if resp.exit_code != 0:
            print("\n(non-zero exit; model output may not be valid Python — try running again)", file=sys.stderr)
            return 1
    finally:
        sandbox.delete()

    print("\n>>> Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
