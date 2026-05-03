import re

from bs4 import BeautifulSoup, NavigableString, Tag


NOISE_TAGS = {"script", "style", "noscript", "svg", "iframe", "canvas", "template"}
STRUCTURAL_NOISE_TAGS = {"header", "footer", "nav", "aside"}

NOISE_ATTRIBUTE_PATTERNS = [
    "cookie",
    "cookies",
    "consent",
    "gdpr",
    "privacy",
    "terms",
    "policy",
    "modal",
    "popup",
    "pop-up",
    "newsletter",
    "subscribe",
    "social",
    "breadcrumb",
]

NOISE_TEXT_PATTERNS = [
    "accept all cookies",
    "accept cookies",
    "manage preferences",
    "cookie preferences",
    "cookie settings",
    "we use cookies",
    "we collect cookies",
    "privacy policy",
    "terms and conditions",
    "all rights reserved",
]

LINE_DROP_PATTERNS = [
    "accept all cookies",
    "accept cookies",
    "manage preferences",
    "cookie preferences",
    "cookie settings",
    "privacy policy",
    "terms and conditions",
    "all rights reserved",
    "copyright",
]


def _attr_text(tag):
    if getattr(tag, "attrs", None) is None:
        return ""

    values = []
    for name in ["id", "class", "aria-label", "role", "data-testid", "data-test", "data-cookie"]:
        value = tag.get(name)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    return " ".join(values).lower()


def _looks_like_noise_block(tag):
    attr_text = _attr_text(tag)
    if attr_text and any(pattern in attr_text for pattern in NOISE_ATTRIBUTE_PATTERNS):
        return True

    text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).lower()
    if not text:
        return False
    if any(pattern in text for pattern in NOISE_TEXT_PATTERNS):
        return True
    return False


def decompose_noise(soup):
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()

    for tag in soup.find_all(STRUCTURAL_NOISE_TAGS):
        tag.decompose()

    for tag in list(soup.find_all(True)):
        if tag.parent is None or getattr(tag, "attrs", None) is None:
            continue
        if tag.name in {"html", "body", "main", "article", "section"}:
            continue
        if _looks_like_noise_block(tag):
            tag.decompose()


def _append_line(lines, value):
    text = re.sub(r"[ \t]+", " ", value or "").strip()
    if text:
        lines.append(text)


def _walk(node, lines):
    if isinstance(node, NavigableString):
        _append_line(lines, str(node))
        return
    if not isinstance(node, Tag):
        return

    name = node.name.lower()
    if name in {"h1", "h2", "h3", "h4"}:
        level = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}[name]
        _append_line(lines, f"{level} {node.get_text(' ', strip=True)}")
        return
    if name == "li":
        _append_line(lines, f"- {node.get_text(' ', strip=True)}")
        return
    if name in {"p", "div", "section", "article", "main", "blockquote"}:
        text = node.get_text(" ", strip=True)
        if text and not any(child.name in {"p", "div", "section", "article", "main", "h1", "h2", "h3", "h4", "li"} for child in node.find_all(recursive=False) if isinstance(child, Tag)):
            _append_line(lines, text)
            return

    for child in node.children:
        _walk(child, lines)


def _clean_lines(lines):
    cleaned = []
    previous = None
    for raw_line in lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        lowered = line.lower()
        if any(pattern in lowered for pattern in LINE_DROP_PATTERNS):
            continue
        if line == previous:
            continue
        cleaned.append(line)
        previous = line
    return cleaned


def html_to_context_text(html, max_chars=5000):
    """Converts HTML into cleaned readable full-body context text."""
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    decompose_noise(soup)

    root = soup.body or soup
    lines = []
    _walk(root, lines)
    text = "\n".join(_clean_lines(lines))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) > max_chars:
        truncated = text[:max_chars].rsplit("\n", 1)[0].strip()
        return truncated or text[:max_chars].strip()
    return text
