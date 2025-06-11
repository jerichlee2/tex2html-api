#!/usr/bin/env bash
#
# new-entry.sh — create a LaTeX stub *and*
#   • update posts.js      in the site repo
#   • commit .tex file     in the tex2html-api repo
# ────────────────────────────────────────────────────────────────
set -euo pipefail

### ─── 0. REPO LOCATIONS  ───────────────────────────────────────
SITE_REPO="$HOME/Documents/jerich"             # ← front-end repo
API_REPO="$HOME/Documents/tex2html-api"        # ← clone of https://github.com/jerichlee2/tex2html-api

### ─── functions ────────────────────────────────────────────────
slugify() {                                # $1 -> filesystem-safe slug
  printf '%s\n' "$1" |
    tr '[:upper:]' '[:lower:]' |
    tr -s '[:space:]' '-'      |
    tr -cd '[:alnum:]-_'       |
    sed -e 's/^-*//' -e 's/-*$//'   # trim leading/trailing -
}
jsonify_tags() {                          # csv → ["a","b",…]
  local IFS=',' arr json='['
  read -ra arr <<<"$1"
  for t in "${arr[@]}"; do
    t=$(xargs <<<"$t") && [[ -n $t ]] && json+="\"$t\","
  done
  printf '%s]\n' "${json%,}"
}

### ─── 1. PROMPTS ───────────────────────────────────────────────
read -rp "Enter the class name: "  CLASS
CLASS_SLUG=$(slugify "$CLASS")          # e.g. "Mathematics of Guitar Strings"
read -rp "Title:  "                TITLE
read -rp "Topic:  "                TOPIC
read -rp "Tags (comma-separated): " TAGS

### ─── 2. CREATE FILE UNDER SITE_REPO  (so you can edit locally)─
DATE_MMDD=$(date +%m-%d)
DATE_ISO=$(date +%Y-%m-%d)
DATE_HUM=$(date +"%B %d, %Y")

SITE_CLASS_DIR="$SITE_REPO/classes/$CLASS_SLUG"
mkdir -p "$SITE_CLASS_DIR"

FOLDER="$DATE_MMDD"; i=1
while [[ -d $SITE_CLASS_DIR/$FOLDER ]]; do
  FOLDER="$DATE_MMDD.$i"; ((i++))
done
mkdir "$SITE_CLASS_DIR/$FOLDER"

TEX_FILENAME="$(slugify "$TITLE").tex"
SITE_TEX="$SITE_CLASS_DIR/$FOLDER/$TEX_FILENAME"

cat <<EOL > "$SITE_TEX"
\documentclass[12pt]{article}

% Packages
\usepackage[margin=1in]{geometry}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{xcolor}
\usepackage{import}
\usepackage{xifthen}
\usepackage{pdfpages}
\usepackage{transparent}
\usepackage{listings}
\usepackage{tikz}
\usepackage{physics}
\usepackage{siunitx}
\usepackage{booktabs}
\usepackage{cancel}
  \usetikzlibrary{calc,patterns,arrows.meta,decorations.markings}


\DeclareMathOperator{\Log}{Log}
\DeclareMathOperator{\Arg}{Arg}

\lstset{
    breaklines=true,         % Enable line wrapping
    breakatwhitespace=false, % Wrap lines even if there's no whitespace
    basicstyle=\ttfamily,    % Use monospaced font
    frame=single,            % Add a frame around the code
    columns=fullflexible,    % Better handling of variable-width fonts
}

\newcommand{\incfig}[1]{%
    \def\svgwidth{\columnwidth}
    \import{./Figures/}{#1.pdf_tex}
}
\theoremstyle{definition} % This style uses normal (non-italicized) text
\newtheorem{solution}{Solution}
\newtheorem{proposition}{Proposition}
\newtheorem{problem}{Problem}
\newtheorem{lemma}{Lemma}
\newtheorem{theorem}{Theorem}
\newtheorem{remark}{Remark}
\newtheorem{note}{Note}
\newtheorem{definition}{Definition}
\newtheorem{example}{Example}
\newtheorem{corollary}{Corollary}
\theoremstyle{plain} % Restore the default style for other theorem environments
%

% Theorem-like environments
% Title information
\title{$TITLE}
\author{Jerich Lee}
\date{\today}

\begin{document}

\maketitle

\end{document}
EOL
echo "✔  Created LaTeX stub  →  $SITE_TEX"

### ─── 3. UPDATE posts.js IN SITE REPO ──────────────────────────
POSTS_JS="$SITE_REPO/posts.js"
if [[ -f $POSTS_JS ]]; then
  TAGS_JSON=$(jsonify_tags "$TAGS")
  ENTRY="  { date:\"$DATE_ISO\", title:\"$TITLE\", category:\"$TOPIC\", \
class:\"$CLASS\", folder:\"$FOLDER\", tags:$TAGS_JSON },"
  tmp=$(mktemp)
  awk -v new="$ENTRY" '
      /^[[:space:]]*];[[:space:]]*$/ { print new }
      { print }
  ' "$POSTS_JS" >"$tmp" && mv "$tmp" "$POSTS_JS"
  echo "✔  Appended entry to posts.js"
else
  echo "⚠  posts.js not found at $POSTS_JS — skipped JavaScript update."
fi

### ─── 4. COPY & COMMIT .TEX FILE INTO API REPO ────────────────
API_CLASS_DIR="$API_REPO/classes/$CLASS_SLUG/$FOLDER"
mkdir -p "$API_CLASS_DIR"
cp "$SITE_TEX" "$API_CLASS_DIR/"

echo "📂  Committing to tex2html-api…"
(
  cd "$API_REPO"
  git add "classes/$CLASS_SLUG/$FOLDER/$TEX_FILENAME"
  if ! git diff --cached --quiet; then
    git commit -m "Add $CLASS diary entry: $TITLE ($DATE_ISO)"
    git push
    echo "✔  Pushed to tex2html-api."
  else
    echo "ℹ  No changes to commit in tex2html-api."
  fi
)

