"""M03 versioned text projection of saved OCR HTML tables; raw OCR stays immutable."""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass(frozen=True)
class TextProjection:
    text: str = field(repr=False)
    profile: str


class TableTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if not self.hidden:
            if tag in {"tr", "table", "p", "div", "br"}:
                self.parts.append("\n")
            elif tag in {"td", "th"}:
                self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden:
            if tag in {"tr", "table", "p", "div"}:
                self.parts.append("\n")
            elif tag in {"td", "th"}:
                self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def project_ocr_text(text: str) -> TextProjection:
    if not re.search(r"<(?:table|tr|td|th)(?:\s|>)", text, re.IGNORECASE):
        return TextProjection(text, "ocr-text-identity-v1")
    parser = TableTextParser()
    parser.feed(text)
    parser.close()
    return TextProjection("".join(parser.parts), "ocr-html-visible-text-v1")
