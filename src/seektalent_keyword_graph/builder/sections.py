from __future__ import annotations

HEADING_TYPES = {
    "岗位职责": "responsibility",
    "工作职责": "responsibility",
    "任职要求": "requirement",
    "岗位要求": "requirement",
    "加分项": "preferred",
    "优先条件": "preferred",
}


def split_sections(text: str) -> list[dict]:
    sections: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for heading, section_type in HEADING_TYPES.items():
            prefix = f"{heading}："
            if line.startswith(prefix):
                sections.append({"section_type": section_type, "text": line[len(prefix) :].strip()})
                break
        else:
            sections.append({"section_type": "other", "text": line})
    return sections
