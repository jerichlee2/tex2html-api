#!/usr/bin/env python3
"""
tex-to-html.py  —  LaTeX → HTML snippet (no outer page chrome)

Usage
=====
    python3 tex-to-html.py <input.tex>          # writes HTML fragment to stdout
    python3 tex-to-html.py <input.tex> dark.css # (optional) extra class hook

The output contains:
  <article class="post [EXTRA_CSS]">
      <header> …title / author / date… </header>
      …converted body…
  </article>

No <html>, <head>, sidebars, or scripts are included.
MathJax markup ($…$, $$…$$) is left as‑is; load MathJax once in your host page.
"""

from __future__ import annotations
import re, sys, html, pathlib
from datetime import datetime

# ───────────────────────── helper utilities ──────────────────────────
def escape_angle_brackets_in_math(s: str) -> str:
    """Escape < > inside LaTeX math so they survive HTML parsing."""
    return re.sub(r"(\$[^$]*\$|\$\$[^$]*\$\$)",
                  lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"),
                  s)

def tex_inline(text: str) -> str:
    """Very small inline‑tag subset."""
    subs = [
        (r"\\textbf\{(.*?)\}",   r"<strong>\1</strong>"),
        (r"\\textit\{(.*?)\}",   r"<em>\1</em>"),
        (r"\\emph\{(.*?)\}",     r"<em>\1</em>"),
        (r"\\underline\{(.*?)\}",r"<u>\1</u>"),
        (r"\\\\",                "<br>"),
    ]
    for pat, rep in subs:
        text = re.sub(pat, rep, text, flags=re.S)
    return html.escape(text, quote=False)

def list_to_html(env: str, block: str) -> str:
    tag = "ul" if env == "itemize" else "ol"
    items = re.findall(r"\\item\s+(.*?)(?=\\item|\\end{" + env + "})", block, re.S)
    lis = "".join(f"<li>{process(i.strip())}</li>" for i in items)
    return f"<{tag}>{lis}</{tag}>"

def process(tex: str) -> str:
    """Recursive one‑pass conversion of supported constructs."""
    out, i = [], 0
    env_pat = re.compile(r"\\begin\{(itemize|enumerate|verbatim)\}", re.S)
    while i < len(tex):
        m = env_pat.search(tex, i)
        if not m:
            out.append(tex_inline(tex[i:]))
            break
        out.append(tex_inline(tex[i:m.start()]))

        env = m.group(1)

        # ---------- fixed code starts here ----------
        end_m   = re.search(rf"\\end\{{{env}\}}", tex[m.end():], re.S)
        if not end_m:
            raise ValueError(f"Missing \\end{{{env}}}")

        end_abs = m.end() + end_m.end()        # absolute index in full string
        block   = tex[m.start():end_abs]
        # ---------- fixed code ends here ----------

        if env in ("itemize", "enumerate"):
            out.append(list_to_html(env, block))
        else:  # verbatim
            code = re.sub(r"\\begin{verbatim}|\\end{verbatim}",
                        "", block, flags=re.S)
            out.append(f"<pre>{html.escape(code)}</pre>")

        i = end_abs      # advance cursor to just after the \end{…}
        html_text = "".join(out)
        for pat, rep in [
            (r"\\section\{(.*?)\}",    r"<h2>\1</h2>"),
            (r"\\subsection\{(.*?)\}", r"<h3>\1</h3>"),
            (r"\\subsubsection\{(.*?)\}", r"<h4>\1</h4>"),
        ]:
            html_text = re.sub(pat, rep, html_text, flags=re.S)
        return html_text

# ───────────────────────── main converter ────────────────────────────
def convert(latex_path: pathlib.Path, extra_class: str = "") -> str:
    tex = latex_path.read_text(encoding="utf-8")

    # -------- metadata --------
    def grab(cmd):  # helper to extract single‑line commands
        m = re.search(rf"\\{cmd}\{{(.*?)\}}", tex, re.S)
        return m.group(1).strip() if m else ""

    title   = grab("title")
    author  = grab("author")
    date    = grab("date").replace("\\today",
              datetime.now().strftime("%B %d, %Y")) or ""

    header_parts = []
    if title:  header_parts.append(f"<h1>{html.escape(title)}</h1>")
    if author: header_parts.append(f"<h3>{html.escape(author)}</h3>")
    if date:   header_parts.append(f"<h4>{html.escape(date)}</h4>")
    header_html = "\n".join(header_parts)

    tex_body = tex.replace("\\maketitle", "TITLE_PLACEHOLDER")
    start = tex_body.find("\\begin{document}") + len("\\begin{document}")
    end   = tex_body.rfind("\\end{document}")
    if start < 0 or end < 0:
        raise ValueError("Missing \\begin{document} or \\end{document}")
    body_tex = tex_body[start:end].strip()

    html_body = process(body_tex).replace("TITLE_PLACEHOLDER", header_html)
    html_body = escape_angle_brackets_in_math(html_body)

    cls_attr = f"post {extra_class}".strip()
    return f'<article class="{cls_attr}">\n{html_body}\n</article>'

# ───────────────────────── CLI wrapper ───────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("Usage: python3 tex-to-html.py <input.tex> [extra_class]")

    tex_file   = pathlib.Path(sys.argv[1]).expanduser()
    extra_cls  = sys.argv[2] if len(sys.argv) == 3 else ""
    try:
        print(convert(tex_file, extra_cls))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)