# Runtime-specific replacement for PyInstaller's broad Pydantic hook.
#
# The SDK imports these public names from ``pydantic``. Pydantic resolves them
# through package ``__getattr__``, which static analysis cannot follow, while
# the modules' normal imports give Analysis the remaining runtime closure.
# Do not use PyInstaller's package-wide recursion; the v1 compatibility and
# static-type-checker branches are excluded below.

hiddenimports = [
    "pydantic.config",
    "pydantic.fields",
    "pydantic.main",
    "pydantic.root_model",
]

# ``pydantic.__init__`` also imports its entire public surface behind
# ``TYPE_CHECKING``. Preserve the reachable v2 surface because SDK response
# validation may enter it dynamically, but omit the separately maintained v1
# compatibility package and static-type checker plugin. Neither can run the
# selector's RPC models and they pull build-only tooling into the artifact.
excludedimports = [
    "pydantic.v1",
    "pydantic.mypy",
]
