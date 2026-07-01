"""M2.3 — PAM session-content features (DATA, blueprint Part 2 / 19.3).

Aggregates parsed session commands (see ``data.connectors.iam_pam.command_parser``) into per-session
signals the L1 privileged rules read:

  * ``pam_command_velocity``     — commands in the session (burst = higher risk)
  * ``pam_tables_touched``       — distinct tables touched
  * ``pam_mass_select_export``   — a mass SELECT / SELECT INTO OUTFILE / dump / scp-out occurred
  * ``pam_ddl_chain``            — count of destructive/DDL statements (a chain is the concealment tell)
  * ``pam_config_change``        — an ALTER SYSTEM / SET GLOBAL / audit-config / GRANT change occurred

Parsing is cached per session and meant to run OFFLINE/batch so the online path stays fast.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from data.connectors.iam_pam.command_parser import CommandParser, ParsedCommand


@dataclass
class SessionFeatures:
    session_id: str
    command_velocity: int = 0
    tables_touched: int = 0
    mass_select_export: bool = False
    ddl_chain: int = 0
    config_change: bool = False
    parsed: list[ParsedCommand] = field(default_factory=list)

    def to_features(self) -> dict:
        """Flat online-feature dict (the keys the L1 PAM rules read via ctx.feat)."""
        return {
            "pam_command_velocity": self.command_velocity,
            "pam_tables_touched": self.tables_touched,
            "pam_mass_select_export": self.mass_select_export,
            "pam_ddl_chain": self.ddl_chain,
            "pam_config_change": self.config_change,
        }


class SessionCommandAnalyzer:
    def __init__(self, parser: CommandParser | None = None) -> None:
        self._parser = parser or CommandParser()
        self._cache: dict[str, SessionFeatures] = {}

    def analyze(self, session_id: str, commands: list[str]) -> SessionFeatures:
        if session_id in self._cache:
            return self._cache[session_id]
        parsed = [self._parser.parse(c) for c in commands]
        tables: set[str] = set()
        mass = False
        ddl = 0
        cfg = False
        for p in parsed:
            tables.update(p.tables_touched)
            mass = mass or p.is_export
            if p.is_ddl or p.is_destructive:
                ddl += 1
            cfg = cfg or p.is_config_change
        feats = SessionFeatures(
            session_id=session_id,
            command_velocity=len(parsed),
            tables_touched=len(tables),
            mass_select_export=mass,
            ddl_chain=ddl,
            config_change=cfg,
            parsed=parsed,
        )
        self._cache[session_id] = feats
        return feats


ANALYZER = SessionCommandAnalyzer()
