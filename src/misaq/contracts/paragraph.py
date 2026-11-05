from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Paragraph:
    index: int
    text: str
    page: int | None
    font_size: float | None = None
    bold_ratio: float = 0.0
    caps_ratio: float = 0.0
    left_indent: float = 0.0
    style_name: str | None = None
    list_label_text: str = ""
    in_table: bool = False
    is_heading_style: bool = False
    source_indexes: tuple[int, ...] = field(default_factory=tuple)
