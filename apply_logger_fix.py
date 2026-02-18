#!/usr/bin/env python3
"""
Patch: Fix logger namespaces in scrapers
========================================
Problem: emmamason_smart_scraper.py, emmamason_algolia_v5_1.py, coleman.py
         use bare logging.getLogger("name") instead of the project's
         get_logger("name") from app.modules.logger.
         As a result their log messages never reach the 'repricer.*' hierarchy
         and are silently dropped — errors become invisible in log files.

Fix: replace the module-level logger line in each file so messages propagate
     correctly through the repricer logging hierarchy.

Usage (run from project root):
    python apply_logger_fix.py
    python apply_logger_fix.py --dry-run   # preview only, no writes
"""

import re
import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path

# ── Patch definitions ─────────────────────────────────────────────────────────
# Each entry: (file_path, old_pattern, new_line, import_to_add)
PATCHES = [
    {
        "file": Path("app/scrapers/emmamason_smart_scraper.py"),
        "old_logger": r'^logger\s*=\s*logging\.getLogger\(["\']emmamason_smart["\']\)',
        "new_logger": 'logger = get_logger("emmamason_smart")',
        "import_anchor": "from .emmamason_algolia_v5_1 import",
        "import_line": "from ..modules.logger import get_logger",
    },
    {
        "file": Path("app/scrapers/emmamason_algolia_v5_1.py"),
        "old_logger": r'^logger\s*=\s*logging\.getLogger\(["\']emmamason_algolia["\']\)',
        "new_logger": 'logger = get_logger("emmamason_algolia")',
        "import_anchor": "^import logging",
        "import_line": "from ..modules.logger import get_logger",
    },
    {
        "file": Path("app/scrapers/coleman.py"),
        "old_logger": r'^logger\s*=\s*logging\.getLogger\(["\']coleman["\']\)',
        "new_logger": 'logger = get_logger("coleman")',
        "import_anchor": "^import logging",
        "import_line": "from ..modules.logger import get_logger",
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"


def ok(msg: str)   -> None: print(f"{GREEN}[OK]{RESET}  {msg}")
def warn(msg: str) -> None: print(f"{YELLOW}[!]{RESET}   {msg}")
def err(msg: str)  -> None: print(f"{RED}[X]{RESET}   {msg}")
def info(msg: str) -> None: print(f"{CYAN}[i]{RESET}   {msg}")


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = path.with_suffix(f".py.backup_{stamp}")
    shutil.copy2(path, dst)
    return dst


def apply_patch(patch: dict, dry_run: bool) -> bool:
    """Apply a single patch. Returns True on success."""
    file_path: Path = patch["file"]

    print(f"\n── {file_path} {'(DRY RUN)' if dry_run else ''}")

    if not file_path.exists():
        err(f"File not found: {file_path}")
        return False

    src = file_path.read_text(encoding="utf-8")

    # ── 1. Check / add import ────────────────────────────────────────────────
    import_line: str = patch["import_line"]
    if import_line in src:
        info(f"Import already present: {import_line}")
    else:
        anchor = patch["import_anchor"]
        # Find first line matching anchor and insert import after it
        lines = src.splitlines(keepends=True)
        inserted = False
        for i, line in enumerate(lines):
            if re.match(anchor, line):
                lines.insert(i + 1, import_line + "\n")
                inserted = True
                break
        if not inserted:
            err(f"Could not find anchor '{anchor}' to insert import")
            return False
        src = "".join(lines)
        ok(f"Will add import: {import_line}")

    # ── 2. Replace logger line ───────────────────────────────────────────────
    old_pattern: str = patch["old_logger"]
    new_line: str    = patch["new_logger"]

    if re.search(old_pattern, src, flags=re.MULTILINE):
        src_new = re.sub(old_pattern, new_line, src, count=1, flags=re.MULTILINE)
        ok(f"Will replace logger → {new_line}")
    elif new_line in src:
        ok(f"Logger already correct — no change needed")
        return True
    else:
        warn(f"Logger pattern not found — file may have been modified already")
        return True

    # ── 3. Write ─────────────────────────────────────────────────────────────
    if dry_run:
        info("Dry run — skipping write")
        return True

    bak = backup(file_path)
    ok(f"Backup created: {bak.name}")

    file_path.write_text(src_new, encoding="utf-8")
    ok(f"File updated: {file_path}")
    return True


def verify(patches: list) -> None:
    """Print a quick verification summary after patching."""
    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}")
    for patch in patches:
        path: Path = patch["file"]
        if not path.exists():
            err(f"{path}: not found")
            continue
        src = path.read_text(encoding="utf-8")
        has_import = patch["import_line"] in src
        has_logger = patch["new_logger"] in src
        old_present = bool(re.search(patch["old_logger"], src, re.MULTILINE))

        status = (
            f"{GREEN}[OK]{RESET}"
            if (has_import and has_logger and not old_present)
            else f"{RED}[FAIL]{RESET}"
        )
        print(f"{status} {path}")
        print(f"       import   : {'present' if has_import else 'MISSING'}")
        print(f"       logger   : {'correct' if has_logger else 'MISSING'}")
        if old_present:
            print(f"       {RED}old logger still present{RESET}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Fix logger namespaces in scrapers")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    # Must run from project root
    if not Path("app/scrapers").is_dir():
        err("Run this script from the project root directory (where app/ lives)")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("LOGGER NAMESPACE FIX")
    print(f"{'='*60}")
    if args.dry_run:
        warn("DRY RUN mode — no files will be modified")

    success = all(apply_patch(p, dry_run=args.dry_run) for p in PATCHES)

    if not args.dry_run:
        verify(PATCHES)

    print(f"\n{'='*60}")
    if success:
        ok("All patches applied successfully!")
        if not args.dry_run:
            print()
            info("Next steps:")
            print("  1. git add app/scrapers/emmamason_smart_scraper.py")
            print("         app/scrapers/emmamason_algolia_v5_1.py")
            print("         app/scrapers/coleman.py")
            print('  2. git commit -m "fix: use get_logger() for correct log propagation"')
            print("  3. git push  →  pull on server  →  restart service")
    else:
        err("Some patches failed — check output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
