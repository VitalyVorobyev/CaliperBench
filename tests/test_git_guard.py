import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "guard", Path(__file__).parents[1] / "scripts/check_repository.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_guard():
    assert guard.problem("docs/readme.md", b"plain text") is None
    for path, data in [
        ("image.PNG", b"not an image"),
        ("data/labels.json", b"{}"),
        ("x.json", b"\x00"),
        ("x.md", b"x" * 1_000_001),
        (".env", b"key=value"),
        ("private/code.py", b"print(1)"),
    ]:
        assert guard.problem(path, data)
