"""Regenerate structural schemas; cross-field checks remain in Python models."""

import json
from pathlib import Path

from caliperbench.schema import Prediction, Request, Sample

root = Path(__file__).resolve().parents[1] / "schemas"
root.mkdir(exist_ok=True)
for model in (Request, Sample, Prediction):
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    (root / f"{model.__name__.lower()}.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
