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
    re.compile(
        r"(?i)(discord[_-]?bot[_-]?token|discord[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{24,}['\"]"
    ),
    re.compile(r"://(?!(?:[^:@\s]+:)?\*\*\*@)[^:@\s]+:[^@\s]+@[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}"),
]

SAFE_SUBSTRINGS = [
    "REDACTED",
    "your_",
    "change-this",
    "fake_",
    "mock_",
    "test_",
    "example",
    "dummy",
    "placeholder",
    "***",
    "${",
]

TARGET_EXTENSIONS = (
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".env",
)

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    ".next",
    "dist",
    "build",
    "tests",
    ".pytest_cache",
}

violations = []
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not any(p in d for p in EXCLUDED_DIRS)]
    parts = set(root.replace("\\", "/").split("/"))
    if parts & EXCLUDED_DIRS:
        continue

    for file in files:
        is_target = (
            file.endswith(TARGET_EXTENSIONS) or file == "Dockerfile" or file.startswith(".env")
        )
        if not is_target:
            continue

        path = os.path.join(root, file)
        if file in ("package-lock.json", "tsconfig.tsbuildinfo", ".gitignore"):
            continue

        with open(path, encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                if any(s in line for s in SAFE_SUBSTRINGS):
                    continue
                for pat in secret_patterns:
                    if pat.search(line):
                        masked = re.sub(r"[a-zA-Z0-9_\-\.]{8,}", "[REDACTED]", line.strip())[:60]
                        violations.append(f"{path}:{idx}: {masked}")

if violations:
    print("Secrets detected:")
    for v in violations:
        print(v)
    sys.exit(1)

print("Secret scan passed: zero secrets found in codebase.")
