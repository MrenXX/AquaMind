"""Minimal Daytona SDK smoke test. Set DAYTONA_API_KEY (see .env.example)."""

import os

from dotenv import load_dotenv
from daytona import Daytona, DaytonaConfig

load_dotenv()

api_key = os.environ.get("DAYTONA_API_KEY")
if not api_key:
    raise SystemExit("Set DAYTONA_API_KEY in the environment or .env")

config = DaytonaConfig(api_key=api_key)
daytona = Daytona(config)

sandbox = daytona.create()
try:
    response = sandbox.process.code_run('print("Hello World from code!")')
    if response.exit_code != 0:
        print(f"Error: {response.exit_code} {response.result}")
    else:
        print(response.result)
finally:
    sandbox.delete()
