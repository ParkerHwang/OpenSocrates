"""Prove observation timeouts cannot terminate a model call in this runner."""

import ast
from pathlib import Path

source = Path(__file__).with_name("runner.py").read_text()
tree = ast.parse(source)
one = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "one")
loops = [node for node in ast.walk(one) if isinstance(node, ast.While)]
assert len(loops) == 1
loop = loops[0]
handler = next(node for node in ast.walk(loop) if isinstance(node, ast.ExceptHandler))
assert ast.unparse(handler.type) == "subprocess.TimeoutExpired"
assert not any(isinstance(node, (ast.Break, ast.Return)) for node in ast.walk(handler))
assert "kill" not in ast.unparse(handler)
assert "deadline" not in ast.unparse(one)
assert 'm["limits"]["seconds_per_call"] is None' in ast.unparse(one).replace("'", '"')
assert "Current user time policy: there is no wall-clock time limit" in source
assert "source and public notes" in source
print(
    "PASS: timeout handler only observes progress; no elapsed-time termination or model relaunch."
)
