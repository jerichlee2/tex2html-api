#!/usr/bin/env bash
#
# new-entry.sh — create a LaTeX stub *and*
#   • update posts.js        in the site repo  (jerich)
#   • commit / push site repo changes
#   • copy tex file to       tex2html‑api repo and push it
# ────────────────────────────────────────────────────────────────
set -euo pipefail

### ─── 0. REPO LOCATIONS  ───────────────────────────────────────
SITE_REPO="$HOME/Documents/jerich"             # front‑end / GitHub Pages repo
API_REPO="$HOME/Documents/tex2html-api"        # tex‑to‑html API repo

### ─── helper functions ─────────────────────────────────────────
slugify() {
  printf '%s\n' "$1" |
    tr '[:upper:]' '[:lower:]' |
    tr -s '[:space:]' '-' |
    tr -cd '[:alnum:]-_' |
    sed -e 's/^-*//' -e 's/-*$//'
}
jsonify_tags() {
  local IFS=',' arr json='['
  read -ra arr <<<"$1"
  for t in "${arr[@]}"; do
    t=$(xargs <<<"$t")
    [[ -n $t ]] && json+="\"$t\","
  done
  printf '%s]\n' "${json%,}"
}

### ─── 1. PROMPTS ───────────────────────────────────────────────
read -rp "Enter the class name: "  CLASS
CLASS_SLUG=$(slugify "$CLASS")
read -rp "Title:  "                TITLE
read -rp "Topic:  "                TOPIC
read -rp "Tags (comma-separated): " TAGS

### ─── 2. CREATE FILE UNDER SITE_REPO ───────────────────────────
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

cat <<EOF > "$SITE_TEX"
\\documentclass[12pt]{article}
...
\\end{document}
EOF
echo "✔  Created LaTeX stub  →  $SITE_TEX"

### ─── 3. UPDATE posts.js IN SITE_REPO ──────────────────────────
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

### ─── 5. COMMIT & PUSH CHANGES IN SITE_REPO (NEW) ─────────────
echo "📂  Committing to site repo (jerich)…"
(
  cd "$SITE_REPO"
  git add "posts.js" "classes/$CLASS_SLUG/$FOLDER/$TEX_FILENAME"
  if ! git diff --cached --quiet; then
    git commit -m "Add $CLASS entry: $TITLE ($DATE_ISO)"
    git push
    echo "✔  Pushed to jerich."
  else
    echo "ℹ  No changes to commit in jerich."
  fi
)

echo "✅  All done!"