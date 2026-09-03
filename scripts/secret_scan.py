"""Pre-commit and CI automated regex secret scanner."""

import os
import re
import sys

secret_patterns = [
    re.compile(
        r"(?i)(api[_-]?key|access[_-]?token|secret[_-]?key|private[_-]?key|password)\s*[:=]\s*['\"][a-zA-Z0-9_\-\.]{20,}['\"]"
    ),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"sk-or-v1-[a-f0-9]{64}"),
]

violations = []
for root, dirs, files in os.walk("."):
    dirs[:] = [
        d
        for d in dirs
        if d not in (".git", ".venv", "node_modules", "__pycache__", ".next", "dist", "build")
    ]
    for file in files:
        if file.endswith(
            (
                ".py",
                ".json",
                ".yaml",
                ".yml",
                ".env.example",
                ".toml",
                ".ts",
                ".tsx",
                ".js",
                ".md",
            )
        ):
            path = os.path.join(root, file)
            # Skip test files and examples
            if "test" in path.lower() or "example" in path.lower():
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for idx, line in enumerate(f, 1):
                    for pat in secret_patterns:
                        if pat.search(line):
                            violations.append(f"{path}:{idx}: {line.strip()[:60]}")

if violations:
    print("Secrets detected:")
    for v in violations:
        print(v)
    sys.exit(1)

print("Secret scan passed: zero secrets found in codebase.")
