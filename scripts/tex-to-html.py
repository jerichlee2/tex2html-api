#!/usr/bin/env python3
"""
tex-to-html.py  –  LaTeX → *fragment* HTML (no <html> wrapper)

This version borrows the recursive environment handler from
“latex_to_html.py”, so it understands
  • nested enumerate / itemize (with [resume] etc.)
  • custom environments:  problem, solution, proof, lemma, proposition, theorem
  • verbatim / lstlisting / figure  …and passes math environments straight
    through ($$, $) for MathJax.

Usage (unchanged)
    python3 tex-to-html.py input.tex            >  fragment.html
    python3 tex-to-html.py input.tex dark.css   >  fragment.html
"""

from __future__ import annotations
import re, sys, html, pathlib
from datetime import datetime

# ───────────────────────── helpers ──────────────────────────
def escape_angle_brackets_in_math(s: str) -> str:
    return re.sub(
        r"(\${1,2})(.*?)(\1)",
        lambda m: f"{m.group(1)}{m.group(2).replace('<','&lt;').replace('>','&gt;')}{m.group(1)}",
        s,
        flags=re.S,
    )

def tex_escape(txt: str) -> str:
    return (txt.replace("&", "&amp;")
               .replace("<", "&lt;")
               .replace(">", "&gt;"))

# ────────────────── generic env extractor (nested-safe) ──────────────────
# ────────────────── generic env extractor (nested-safe) ──────────────────
def grab_env(tex: str, pos: int, env: str) -> tuple[str, int]:

    beg_pat = rf"\\begin\{{{env}\}}\s*(\[[^\]]*\])?"
    end_pat = rf"\\end\{{{env}\}}"
    token_re = re.compile(fr"{beg_pat}|{end_pat}", re.S)

    # Confirm we're sitting exactly on the opening tag and skip past it.
    m0 = re.match(beg_pat, tex[pos:], re.S)
    if not m0:
        raise ValueError(f"Expected \\begin{{{env}}} at index {pos}")
    depth = 1
    cursor = pos + m0.end()           # start scanning *after* the first tag

    while depth and cursor < len(tex):
        m = token_re.search(tex, cursor)
        if not m:
            raise ValueError(f"Missing \\end{{{env}}}")
        cursor = m.end()              # advance past this token
        depth += 1 if m.group(0).startswith("\\begin") else -1

    if depth != 0:
        raise ValueError(f"Missing \\end{{{env}}}")

    return tex[pos:cursor], cursor

# ────────────────── recursive LaTeX-to-HTML core ──────────────────
def render(tex: str, in_math=False) -> str:
    # strip comments (unescaped %), cheap.
    tex = re.sub(r"(?<!\\)%.*", "", tex)

    out, i = [], 0
    while i < len(tex):
        if tex.startswith("\\begin{", i):
            env = re.match(r"\\begin\{(\w+\*?)\}", tex[i:]).group(1)
            block, j = grab_env(tex, i, env)
            i = j
            inner = re.sub(rf"\\begin\{{{env}\}}(\[[^\]]*\])?|\\end\{{{env}\}}", "", block, flags=re.S)

            if env == "enumerate":
                out.append(list_env(inner, ordered=True))
            elif env == "itemize":
                out.append(list_env(inner, ordered=False))
            elif env == "verbatim":
                out.append(f"<pre>{tex_escape(inner)}</pre>")
            elif env == "lstlisting":
                out.append(f"<pre class='code-block'>{tex_escape(inner)}</pre>")
            elif env == "figure":
                out.append(handle_figure(inner))
                         # keep LaTeX for MathJax
            elif env in ("align", "align*", "equation", "equation*", "gather",
             "multline", "split"):
                out.append(f"$${block}$$")                       # keep math for MathJax

            elif env == "tabular":
                # extract the column spec and body
                spec_match = re.match(r"\\begin\{tabular\}\{([^}]*)\}", block, re.S)
                colspec = spec_match.group(1) if spec_match else ""
                tab_body = re.sub(r"\\begin\{tabular\}\{[^}]*\}|\\end\{tabular\}", "",
                                block, flags=re.S)
                out.append(tabular_to_html(colspec, tab_body))

            elif env == "table":
                # optional caption
                cap = re.search(r"\\caption\*?\{(.*?)\}", inner, re.S)
                caption_html = f"<figcaption>{render(cap.group(1))}</figcaption>" if cap else ""
                # find the (first) tabular inside and convert it
                tab_m = re.search(r"\\begin\{tabular\}.*?\\end\{tabular\}", inner, re.S)
                table_html = render(tab_m.group(0)) if tab_m else ""
                out.append(f"<figure>{table_html}{caption_html}</figure>")
            elif env in ("problem", "solution", "proof",
                         "lemma", "proposition", "theorem"):
                label = env.capitalize().rstrip("*") + "."
                body  = render(inner)
                qed   = "<div class='qed'>∎</div>" if env == "proof" else ""
                out.append(f"<div class='{env}'><strong>{label}</strong><br>{body}{qed}</div>")
            else:   # unknown env → recurse
                out.append(render(inner, in_math=in_math))
        else:
            # plain text or LaTeX command
            m_cmd = re.match(r"\\(\w+)(\*?)\{(.*?)\}", tex[i:], re.S)
            if m_cmd and not in_math:
                cmd, arg = m_cmd.group(1), m_cmd.group(3)
                if cmd == "section":
                    out.append(f"<h2>{html.escape(arg)}</h2>")
                elif cmd == "subsection":
                    out.append(f"<h3>{html.escape(arg)}</h3>")
                elif cmd == "subsubsection":
                    out.append(f"<h4>{html.escape(arg)}</h4>")
                elif cmd in ("textbf",):
                    out.append(f"<strong>{html.escape(arg)}</strong>")
                elif cmd in ("textit", "emph"):
                    out.append(f"<em>{html.escape(arg)}</em>")
                else:      # leave unrecognised command verbatim
                    out.append(tex_escape(m_cmd.group(0)))
                i += m_cmd.end()
            else:
                # consume until next backslash or end
                nxt = tex.find("\\", i+1)
                segment = tex[i:nxt if nxt != -1 else len(tex)]
                out.append(tex_escape(segment) if not in_math else segment)
                i = nxt if nxt != -1 else len(tex)

    return "".join(out)

def list_env(inner: str, *, ordered: bool) -> str:
    tag = "ol" if ordered else "ul"
    items = re.split(r"\\item", inner)[1:]  # first split is before first \item
    items_html = "".join(f"<li>{render(it.strip())}</li>" for it in items)
    return f"<{tag}>{items_html}</{tag}>"

def handle_figure(inner: str) -> str:
    img   = re.search(r"\\includegraphics\[.*?\]\{(.*?)\}", inner, re.S)
    cap   = re.search(r"\\caption\{(.*?)\}", inner, re.S)
    imgsrc = html.escape(img.group(1).strip()) if img else ""
    caption= html.escape(cap.group(1).strip()) if cap else ""
    cap_html = f"<figcaption>{caption}</figcaption>" if caption else ""
    return (f"<figure><img src='{imgsrc}' alt='{caption}' "
            "style='max-width:100%;height:auto;'>"
            f"{cap_html}</figure>")

# ────────────────── table helpers ────────────────────────────
def tabular_to_html(spec: str, body: str) -> str:
    # Split rows on \\  (strip trailing spaces and \hline's)
    rows = []
    for raw in re.split(r"\\\\", body):
        line = raw.strip()
        if not line or line == r"\hline":
            continue
        line = line.replace(r"\hline", "")
        rows.append([cell.strip() for cell in line.split("&")])

    # First row = header if every cell contains \textbf or has bold tag
    header_html = ""
    if all(re.search(r"\\textbf|<strong>", c) for c in rows[0]):
        header_cells = [f"<th>{render(c)}</th>" for c in rows.pop(0)]
        header_html = "<thead><tr>" + "".join(header_cells) + "</tr></thead>"

    body_html = "<tbody>" + "".join(
        "<tr>" + "".join(f"<td>{render(c)}</td>" for c in r) + "</tr>"
        for r in rows
    ) + "</tbody>"

    return f"<table>{header_html}{body_html}</table>"

# ────────────────── public convert() function ──────────────────
def convert(latex_path: pathlib.Path, extra_class: str="") -> str:
    tex = latex_path.read_text(encoding="utf-8")

    # metadata
    md = {k: re.search(rf"\\{k}\{{(.*?)\}}", tex, re.S)
              for k in ("title","author","date")}
    title  = md["title"].group(1).strip()  if md["title"]  else ""
    author = md["author"].group(1).strip() if md["author"] else ""
    date   = (md["date"].group(1).replace("\\today",
             datetime.now().strftime("%B %d, %Y")).strip()
             if md["date"] else "")

    header = "".join([
        f"<h1>{html.escape(title)}</h1>"   if title  else "",
        f"<h3>{html.escape(author)}</h3>"  if author else "",
        f"<h4>{html.escape(date)}</h4>"    if date   else ""
    ])

    tex_body = tex.replace("\\maketitle", "TITLE_PLACEHOLDER")
    start = tex_body.find("\\begin{document}") + len("\\begin{document}")
    end   = tex_body.rfind("\\end{document}")
    if start < 0 or end < 0:
        raise ValueError("Missing \\begin{document} / \\end{document}")
    body_tex = tex_body[start:end].strip()

    html_body = render(body_tex).replace("TITLE_PLACEHOLDER", header)
    html_body = escape_angle_brackets_in_math(html_body)

    cls_attr = f"post {extra_class}".strip()
    return f'<article class="{cls_attr}">\n{html_body}\n</article>'

# ────────────────── CLI wrapper (unchanged) ──────────────────
if __name__ == "__main__":
    if len(sys.argv) not in (2,3):
        sys.exit("Usage: tex-to-html.py input.tex [extra_class]")
    try:
        print(convert(pathlib.Path(sys.argv[1]), sys.argv[2] if len(sys.argv)==3 else ""))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)