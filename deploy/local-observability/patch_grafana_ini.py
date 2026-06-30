#!/usr/bin/env python3
"""Idempotently set a few keys in grafana.ini (preserving the rest of the file).

Grafana's brew service reads a fixed --config path, so to enable anonymous access +
iframe embedding + our provisioning dir we patch that ini in place. We do targeted
line edits (uncomment/replace the key inside its [section], else append) so comments
and every other default stay intact.

Usage: patch_grafana_ini.py <path-to-grafana.ini> <provisioning-dir>
"""
from __future__ import annotations

import re
import sys


def set_key(lines: list[str], section: str, key: str, value: str) -> list[str]:
    out: list[str] = []
    in_section = False
    done = False
    sec_re = re.compile(r"^\s*\[(.+?)\]\s*$")
    key_re = re.compile(rf"^\s*;?\s*{re.escape(key)}\s*=", re.IGNORECASE)
    for line in lines:
        m = sec_re.match(line)
        if m:
            # leaving a section we were in without having set the key -> insert it now
            if in_section and not done:
                out.append(f"{key} = {value}\n")
                done = True
            in_section = m.group(1).strip().lower() == section.lower()
        elif in_section and not done and key_re.match(line):
            out.append(f"{key} = {value}\n")
            done = True
            continue
        out.append(line)
    if in_section and not done:  # section was the last in the file
        out.append(f"{key} = {value}\n")
        done = True
    if not done:  # section never appeared -> append section + key
        out.append(f"\n[{section}]\n{key} = {value}\n")
    return out


def main() -> int:
    ini_path, provisioning_dir = sys.argv[1], sys.argv[2]
    with open(ini_path, encoding="utf-8") as fh:
        lines = fh.readlines()

    edits = [
        ("server", "http_port", "3000"),
        ("auth.anonymous", "enabled", "true"),
        ("auth.anonymous", "org_role", "Viewer"),
        ("security", "allow_embedding", "true"),
        ("security", "cookie_samesite", "none"),
        ("paths", "provisioning", provisioning_dir),
    ]
    for section, key, value in edits:
        lines = set_key(lines, section, key, value)

    with open(ini_path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    print(f"patched {ini_path}: anonymous+embedding on, provisioning -> {provisioning_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
