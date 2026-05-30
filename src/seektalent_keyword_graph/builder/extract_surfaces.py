from __future__ import annotations

KNOWN_TERMS = [
    "Python",
    "Java",
    "Kubernetes",
    "k8s",
    "Spring Cloud",
    "React",
    "Vue",
    "AIGC",
]

BLOCKED_TERMS = {"腾讯", "阿里", "字节"}


def extract_surface_mentions(text: str) -> list[dict]:
    mentions: list[dict] = []
    for term in KNOWN_TERMS:
        if term in text and term not in BLOCKED_TERMS:
            mentions.append(
                {
                    "surface_text_raw": term,
                    "surface_text_norm": term.casefold(),
                    "mention_type": "tool" if term in {"Kubernetes", "k8s"} else "skill",
                    "confidence": 0.9,
                    "extractor_name": "rule_dictionary",
                    "extractor_version": "v1",
                }
            )
    return mentions
