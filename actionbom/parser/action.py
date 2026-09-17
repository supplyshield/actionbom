from __future__ import annotations

from typing import Dict, List, Optional

import yaml


def parse_action(text: str) -> Dict[str, Optional[List[str]]]:
    """Parse an action.yml/.yaml manifest and return its type and nested uses if any.

    Returns: { action_type: str, nested_uses: [str], name?: str, description?: str, author?: str, runs_image?: str }
    action_type ∈ { composite, node, docker, unknown }
    """
    data = yaml.safe_load(text) or {}
    runs = data.get("runs") or {}
    using = runs.get("using")
    action_type = "unknown"
    nested_uses: List[str] = []

    if isinstance(using, str):
        u = using.lower()
        if u == "composite":
            action_type = "composite"
            steps = runs.get("steps") or []
            for s in steps:
                if isinstance(s, dict):
                    v = s.get("uses")
                    if isinstance(v, str):
                        nested_uses.append(v)
        elif u in ("node12", "node16", "node20", "node", "node18"):
            action_type = "node"
        elif u == "docker":
            action_type = "docker"
        else:
            action_type = u

    meta = {
        "name": data.get("name"),
        "description": data.get("description"),
        "author": data.get("author"),
    }
    runs_image = None
    if action_type == "docker":
        img = runs.get("image")
        if isinstance(img, str):
            runs_image = img

    out: Dict[str, Optional[List[str]]] = {
        "action_type": action_type,
        "nested_uses": nested_uses,
        "name": meta.get("name"),
        "description": meta.get("description"),
        "author": meta.get("author"),
        "runs_image": runs_image,
    }
    return out
