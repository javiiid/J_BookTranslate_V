import re
import unicodedata
from html.parser import HTMLParser


RTL_LANGUAGES = {"FA", "AR", "UR", "HE", "PS", "SD"}


def text_direction(text, fallback="ltr"):
    text = re.sub(r"https?://\S+|\b[\w.+-]+@[\w.-]+\b", "", text)
    rtl = sum(unicodedata.bidirectional(char) in {"R", "AL"} for char in text)
    ltr = sum(unicodedata.bidirectional(char) == "L" for char in text)
    if not rtl and not ltr:
        return fallback
    return "rtl" if rtl > ltr else "ltr"


def has_rtl(text):
    return any(unicodedata.bidirectional(char) in {"R", "AL"} for char in text)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "head"}:
            self.hidden += 1
        if tag in {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "head"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")
        if tag in {"td", "th"}:
            self.parts.append("\t")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def html_text(value):
    parser = PlainText()
    parser.feed(str(value or ""))
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())
