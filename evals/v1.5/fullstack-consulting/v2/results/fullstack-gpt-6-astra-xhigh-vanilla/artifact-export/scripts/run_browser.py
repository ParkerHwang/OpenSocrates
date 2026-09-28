"""Start an isolated application and run the real browser workflow."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.support import App, ROOT

app = App()
try:
    app.start()
    result = subprocess.run(['node', 'tests/browser.cjs'], cwd=ROOT, env=os.environ | {'BASE_URL': app.url})
    raise SystemExit(result.returncode)
finally:
    app.close()
