#!/usr/bin/env python3
"""Governance document generator (PLATFORM-36, blueprint Part 27.1/28.1/29.2/19.6).

Takes the policy/regulatory Markdown source docs (governance/docs/*.md), stamps each with its
seeded **approval record** (date / resolution id / signatories) from the governance DB, renders
to governance/docs/out/ (Markdown always; PDF via WeasyPrint when available), and writes an
index. `make governance-docs`. MOCK: the approvals are seeded human/legal acts.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE.parent / "db"))
import models as m  # noqa: E402

# source filename -> (table, filter) used to fetch the approval header
DOC_APPROVALS = {
    "ai-policy.md": ("policies", {"policy_type": "ai_policy"}),
    "dpia.md": ("dpia", {}),
    "dpo-appointment.md": ("dpia", {}),
    "lawful-basis-map.md": ("policies", {"policy_type": "lawful_basis"}),
    "breach-notification.md": ("policies", {"policy_type": "breach"}),
    "transparency-notice.md": ("policies", {"policy_type": "transparency"}),
}


def _approval_header(filename: str, session) -> str:
    spec = DOC_APPROVALS.get(filename)
    if not spec:
        return ""
    table, filt = spec
    model = m.TABLE_MODELS.get(table)
    if model is None:
        return ""
    row = (
        session.query(model).filter_by(**filt).first()
        if filt
        else session.query(model).first()
    )
    if row is None:
        return ""
    if table == "policies":
        return (
            f"> **APPROVAL RECORD (seeded MOCK)** — Approved by **{row.approved_by}** on "
            f"**{row.approval_date}** · Resolution **{row.resolution_id}** · status "
            f"`{row.status}`.\n\n"
        )
    if table == "dpia":
        return (
            f"> **APPROVAL RECORD (seeded MOCK)** — DPIA **{row.name}**, DPO **{row.dpo}**, "
            f"approved **{row.approval_date}**, status `{row.status}`.\n\n"
        )
    return ""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    session = m.get_session()
    sources = sorted(p for p in HERE.glob("*.md") if p.parent == HERE)
    if not sources:
        print(
            "No source docs in governance/docs/ yet (PLATFORM-36 content). Nothing to render."
        )
        return 0

    try:
        from weasyprint import HTML  # optional
        import markdown as md

        have_pdf = True
    except Exception:
        have_pdf = False

    rendered = []
    for src in sources:
        header = _approval_header(src.name, session)
        body = header + src.read_text()
        out_md = OUT / src.name
        out_md.write_text(body)
        rendered.append(src.name)
        if have_pdf:
            try:
                html = md.markdown(body, extensions=["tables", "fenced_code"])
                HTML(string=html).write_pdf(str(OUT / (src.stem + ".pdf")))
            except Exception:
                pass

    index = "# Hawk-Eye — Governance Document Index (PLATFORM-36)\n\n"
    index += f"Generated {len(rendered)} documents (Markdown{' + PDF' if have_pdf else ''}).\n\n"
    for name in rendered:
        index += f"- [{name}](./{name})\n"
    (OUT / "index.md").write_text(index)
    print(
        f"Rendered {len(rendered)} governance docs -> {OUT.relative_to(HERE.parents[1])}"
        f"{' (with PDF)' if have_pdf else ' (md only; install weasyprint for PDF)'}"
    )
    for n in rendered:
        print(f"  {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
