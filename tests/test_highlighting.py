import importlib.util
from pathlib import Path
import sys


spec = importlib.util.spec_from_file_location(
    "documentation_highlighting",
    Path(__file__).parents[1] / "netbox_documentation" / "highlighting.py",
)
highlighting = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = highlighting
spec.loader.exec_module(highlighting)


def test_highlights_markdown_fence_with_language():
    result = highlighting.highlight_code_blocks('<pre><code class="language-python">def f():\n    return 1\n</code></pre>')
    assert 'class="doc-hl" data-lang="Python"' in result
    assert '<span class="k">def</span>' in result


def test_highlights_tinymce_code_sample_and_keeps_escaping():
    result = highlighting.highlight_code_blocks('<pre class="language-markup"><code>&lt;b onclick="x"&gt;hi&lt;/b&gt;</code></pre>')
    assert 'data-lang="HTML"' in result
    assert "<b" not in result.replace("<span", "")
    assert "&lt;" in result


def test_plain_text_and_unknown_language_stay_untouched():
    for block in ('<pre class="language-none">interface Gi0/1</pre>', '<pre><code class="language-unknownlang">x</code></pre>'):
        assert highlighting.highlight_code_blocks(block) == block
