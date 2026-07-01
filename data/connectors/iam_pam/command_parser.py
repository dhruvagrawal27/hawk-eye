"""M2.3 — PAM session-content command parser (CyberArk/BeyondTrust session logs).

Turns a recorded privileged-session command STRING into structured signal: is it SQL / OS / config,
which tables it touched, whether it is a mass SELECT / export, and whether it is destructive DDL.
This lifts insider detection from 1-hop ("a privileged session happened") to 2-hop ("what they ran
in it"). Dependency-light (regex only), operates ONLY on already-recorded command text — NO
keylogging, consistent with the pam-shim contract (commands stored as opaque strings).

SCAFFOLD: real CyberArk/BeyondTrust session content needs the vendor feed; this parses the synthetic
command strings the pam-shim records today.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Leading SQL verbs we care about.
_SQL_VERBS = {
    "select", "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "merge", "copy",
}
_DDL_VERBS = {"drop", "alter", "create", "truncate", "grant", "revoke"}
_DESTRUCTIVE = {"drop", "delete", "truncate"}
# OS/shell exfil-ish commands (the pam-shim records these verbatim).
_OS_EXPORT = {"scp", "sftp", "rsync", "tar", "gzip", "curl", "wget", "mysqldump", "pg_dump", "expdp"}
_OS_VERBS = _OS_EXPORT | {"rm", "cp", "mv", "cat", "chmod", "chown", "rotate_secret", "drop_database"}
# config/control-plane changes.
_CONFIG_TOKENS = ("alter system", "set global", "set persist", "audit", "log_", "disable_logging")

_TABLE_AFTER = re.compile(r"\b(?:from|into|update|join|table)\s+([a-zA-Z_][\w.]*)", re.IGNORECASE)
_LIMIT = re.compile(r"\blimit\s+(\d+)", re.IGNORECASE)
_ROWS = re.compile(r"\b(\d{3,})\s+rows?\b", re.IGNORECASE)
_EXPORT_SQL = re.compile(r"\b(into\s+outfile|copy\b.*\bto\b|select\s+\*\s+from)\b", re.IGNORECASE)


@dataclass
class ParsedCommand:
    raw: str
    kind: str = "unknown"          # sql | os | config | unknown
    verb: str = ""                 # leading verb, lower-cased
    tables_touched: list[str] = field(default_factory=list)
    rowcount: int | None = None    # parsed row hint (LIMIT n / "N rows"), if any
    is_export: bool = False        # mass SELECT / SELECT INTO OUTFILE / dump / scp-out
    is_ddl: bool = False           # drop/alter/create/truncate/grant/revoke
    is_destructive: bool = False   # drop/delete/truncate
    is_config_change: bool = False # ALTER SYSTEM / SET GLOBAL / audit-config

    def to_dict(self) -> dict:
        return {
            "raw": self.raw, "kind": self.kind, "verb": self.verb,
            "tables_touched": list(self.tables_touched), "rowcount": self.rowcount,
            "is_export": self.is_export, "is_ddl": self.is_ddl,
            "is_destructive": self.is_destructive, "is_config_change": self.is_config_change,
        }


class CommandParser:
    """Parse a single recorded session command string into a :class:`ParsedCommand`."""

    def parse(self, command: str, dialect: str = "auto") -> ParsedCommand:  # noqa: ARG002
        raw = (command or "").strip()
        low = raw.lower()
        if not raw:
            return ParsedCommand(raw=raw)
        first = re.split(r"\s+", low, maxsplit=1)[0]

        is_config = any(tok in low for tok in _CONFIG_TOKENS)
        if first in _SQL_VERBS or _TABLE_AFTER.search(low):
            return self._parse_sql(raw, low, first, is_config)
        if first in _OS_VERBS:
            return self._parse_os(raw, low, first, is_config)
        if is_config:
            return ParsedCommand(raw=raw, kind="config", verb=first, is_config_change=True)
        return ParsedCommand(raw=raw, kind="unknown", verb=first)

    def _parse_sql(self, raw: str, low: str, verb: str, is_config: bool) -> ParsedCommand:
        tables = sorted({m.group(1).lower() for m in _TABLE_AFTER.finditer(low)})
        rc = _LIMIT.search(low) or _ROWS.search(low)
        rowcount = int(rc.group(1)) if rc else None
        is_export = bool(_EXPORT_SQL.search(low)) or verb == "copy"
        return ParsedCommand(
            raw=raw, kind="sql", verb=verb, tables_touched=tables, rowcount=rowcount,
            is_export=is_export,
            is_ddl=verb in _DDL_VERBS,
            is_destructive=verb in _DESTRUCTIVE,
            is_config_change=is_config or verb in {"grant", "revoke", "alter"},
        )

    def _parse_os(self, raw: str, low: str, verb: str, is_config: bool) -> ParsedCommand:
        rc = _ROWS.search(low)
        return ParsedCommand(
            raw=raw, kind="os", verb=verb,
            rowcount=int(rc.group(1)) if rc else None,
            is_export=verb in _OS_EXPORT,
            is_destructive=verb in {"rm", "drop_database"},
            is_config_change=is_config or verb == "rotate_secret",
        )


PARSER = CommandParser()


def parse_command(command: str) -> ParsedCommand:
    return PARSER.parse(command)
