"""Server-side syntax highlighting of code blocks in rendered documents (VS Code-like colours).

Runs on already sanitised HTML: the code text is unescaped, re-tokenised by Pygments and
re-escaped, so only Pygments' own <span class="..."> markup is added.
"""
import html
import re

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

_PRE = re.compile(r"<pre(?P<attrs>[^>]*)>(?:<code(?P<code_attrs>[^>]*)>)?(?P<body>.*?)(?:</code>)?</pre>", re.S)
_LANGUAGE = re.compile(r'class="[^"]*\b(?:lang|language)-(?P<name>[\w+#.-]+)')
_BR = re.compile(r"<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")

# Language names used by TinyMCE's code sample plugin and common Markdown fences.
_ALIASES = {
    "markup": "html", "shell": "bash", "sh": "bash", "ps": "powershell", "ps1": "powershell",
    "yml": "yaml", "js": "javascript", "ts": "typescript", "py": "python",
}
_PLAIN = {"none", "plaintext", "text", "plain", "txt"}
_FORMATTER = HtmlFormatter(nowrap=True)


def _lexer(name, code):
    if name:
        name = _ALIASES.get(name.lower(), name.lower())
        if name in _PLAIN:
            return None
        try:
            return get_lexer_by_name(name)
        except ClassNotFound:
            return None
    # No language given: only trust a confident guess, otherwise leave the block plain.
    try:
        lexer = guess_lexer(code)
    except ClassNotFound:
        return None
    return lexer if lexer.analyse_text(code) >= 0.5 else None


def _replace(match):
    language = _LANGUAGE.search((match.group("attrs") or "") + (match.group("code_attrs") or ""))
    code = html.unescape(_TAG.sub("", _BR.sub("\n", match.group("body")))).rstrip("\n")
    lexer = _lexer(language.group("name") if language else None, code)
    if lexer is None:
        return match.group(0)
    highlighted = highlight(code, lexer, _FORMATTER).rstrip("\n")
    label = html.escape(lexer.name, quote=True)
    return f'<pre class="doc-hl" data-lang="{label}"><code>{highlighted}</code></pre>'


def highlight_code_blocks(value):
    return _PRE.sub(_replace, value)
