#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

import httpx


DEFAULT_INCLUDE = [
    "MEMORY.md",
    "memory/**/*.md",
    "USER.md",
    "AGENTS.md",
    "SOUL.md",
]


def iter_files(root: Path, patterns: list[str]):
    seen = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file() and path not in seen:
                seen.add(path)
                yield path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--api", default=os.environ.get("LLMWIKI_API_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--token", default=os.environ.get("LLMWIKI_TOKEN", ""))
    ap.add_argument("--kb-name", default="Workspace Brain")
    args = ap.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"}
    root = Path(args.workspace).resolve()

    with httpx.Client(base_url=args.api, headers=headers, timeout=60) as client:
        kb = client.post("/v1/knowledge-bases", json={"name": args.kb_name, "description": "Workspace memory compiled into LLM Wiki raw sources."})
        if kb.status_code not in (200, 201):
            raise SystemExit(f"failed to create KB: {kb.status_code} {kb.text}")
        kb_data = kb.json()
        kb_id = kb_data["id"]
        print(f"KB {kb_data['slug']} {kb_id}")

        count = 0
        for path in iter_files(root, DEFAULT_INCLUDE):
            rel = path.relative_to(root).as_posix()
            content = path.read_text(encoding="utf-8")
            filename = path.name
            parent = "/" if "/" not in rel else "/" + rel.rsplit("/", 1)[0] + "/"
            res = client.post(
                f"/v1/knowledge-bases/{kb_id}/documents/note",
                json={"filename": filename, "path": parent, "content": content},
            )
            if res.status_code not in (200, 201):
                raise SystemExit(f"failed to upload {rel}: {res.status_code} {res.text}")
            count += 1
            print(f"uploaded {rel}")

        print(f"Uploaded {count} files into KB {kb_data['slug']}")


if __name__ == "__main__":
    main()
