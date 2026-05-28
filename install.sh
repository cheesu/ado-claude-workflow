#!/usr/bin/env bash
# install.sh — ADO Claude Workflow Toolkit installer
#
# Usage:
#   ./install.sh --config workflow.config.json [--dry-run]
#
# Or pass values directly:
#   ./install.sh \
#     --target /path/to/frontend \
#     --product-code MY-PRODUCT \
#     --scope-code FE \
#     --ado-org your-org \
#     --ado-project YOUR_PROJECT \
#     --repo-root /path/to/repo \
#     --work-path "src/products/my-product" \
#     --base-branch "product/my-product/main" \
#     --branch-prefix "product/my-product" \
#     --forbidden-paths "src/pages,src/shared"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/templates"

# ── defaults ──────────────────────────────────────────────────────────────────
PRODUCT_CODE=""
SCOPE_CODE="FE"
ADO_ORG=""
ADO_PROJECT=""
REPO_ROOT=""
FRONTEND_ROOT=""
WORK_PATH=""
BASE_BRANCH=""
BRANCH_PREFIX=""
FORBIDDEN_PATHS=""
DRY_RUN=false
CONFIG_FILE=""

# ── argument parsing ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)          CONFIG_FILE="$2"; shift 2 ;;
    --target)          FRONTEND_ROOT="$2"; shift 2 ;;
    --product-code)    PRODUCT_CODE="$2"; shift 2 ;;
    --scope-code)      SCOPE_CODE="$2"; shift 2 ;;
    --ado-org)         ADO_ORG="$2"; shift 2 ;;
    --ado-project)     ADO_PROJECT="$2"; shift 2 ;;
    --repo-root)       REPO_ROOT="$2"; shift 2 ;;
    --work-path)       WORK_PATH="$2"; shift 2 ;;
    --base-branch)     BASE_BRANCH="$2"; shift 2 ;;
    --branch-prefix)   BRANCH_PREFIX="$2"; shift 2 ;;
    --forbidden-paths) FORBIDDEN_PATHS="$2"; shift 2 ;;
    --dry-run)         DRY_RUN=true; shift ;;
    --help|-h)
      echo "Usage: ./install.sh --config workflow.config.json [--dry-run]"
      echo ""
      echo "Or pass values directly:"
      echo "  ./install.sh \\"
      echo "    --target /path/to/frontend \\"
      echo "    --product-code MY-PRODUCT \\"
      echo "    --scope-code FE \\"
      echo "    --ado-org your-org \\"
      echo "    --ado-project YOUR_PROJECT \\"
      echo "    --repo-root /path/to/repo \\"
      echo "    --work-path \"src/products/my-product\" \\"
      echo "    --base-branch \"product/my-product/main\" \\"
      echo "    --branch-prefix \"product/my-product\" \\"
      echo "    --forbidden-paths \"src/pages,src/shared\""
      echo ""
      echo "Options:"
      echo "  --config           Path to workflow.config.json (JSON with all fields)"
      echo "  --target           Absolute path to the frontend root directory"
      echo "  --product-code     Product identifier (e.g. MY-PRODUCT)"
      echo "  --scope-code       Scope tag for commit messages (default: FE)"
      echo "  --ado-org          Azure DevOps organization name"
      echo "  --ado-project      Azure DevOps project name"
      echo "  --repo-root        Absolute path to the git repo root"
      echo "  --work-path        Relative path within frontend for product code (e.g. src/products/my-product)"
      echo "  --base-branch      Base branch name (e.g. product/my-product/main)"
      echo "  --branch-prefix    Work branch prefix (e.g. product/my-product)"
      echo "  --forbidden-paths  Comma-separated relative paths to block edits (e.g. src/pages,src/shared)"
      echo "  --dry-run          Print resolved config without writing any files"
      exit 0
      ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ── load from config file if provided ─────────────────────────────────────────
if [[ -n "$CONFIG_FILE" ]]; then
  if ! command -v python3 &>/dev/null; then
    echo "Error: python3 required to parse config file." >&2; exit 1
  fi
  read_cfg() { python3 -c "import json,sys; d=json.load(open('$CONFIG_FILE')); print(d.get('$1',''))" 2>/dev/null; }

  [[ -z "$PRODUCT_CODE" ]]  && PRODUCT_CODE="$(read_cfg product_code)"
  [[ -z "$SCOPE_CODE" ]]    && SCOPE_CODE="$(read_cfg scope_code)"
  [[ -z "$ADO_ORG" ]]       && ADO_ORG="$(read_cfg ado_org)"
  [[ -z "$ADO_PROJECT" ]]   && ADO_PROJECT="$(read_cfg ado_project)"
  [[ -z "$REPO_ROOT" ]]     && REPO_ROOT="$(read_cfg repo_root)"
  [[ -z "$FRONTEND_ROOT" ]] && FRONTEND_ROOT="$(read_cfg frontend_root)"
  [[ -z "$WORK_PATH" ]]     && WORK_PATH="$(read_cfg work_path)"
  [[ -z "$BASE_BRANCH" ]]   && BASE_BRANCH="$(read_cfg base_branch)"
  [[ -z "$BRANCH_PREFIX" ]] && BRANCH_PREFIX="$(read_cfg branch_prefix)"
  [[ -z "$FORBIDDEN_PATHS" ]] && FORBIDDEN_PATHS="$(python3 -c "
import json; d=json.load(open('$CONFIG_FILE'))
paths = d.get('forbidden_paths', [])
print(','.join(paths))
" 2>/dev/null)"
fi

# ── validation ─────────────────────────────────────────────────────────────────
errors=()
[[ -z "$PRODUCT_CODE" ]]  && errors+=("--product-code is required")
[[ -z "$ADO_ORG" ]]       && errors+=("--ado-org is required")
[[ -z "$ADO_PROJECT" ]]   && errors+=("--ado-project is required")
[[ -z "$REPO_ROOT" ]]     && errors+=("--repo-root is required")
[[ -z "$FRONTEND_ROOT" ]] && errors+=("--target (frontend_root) is required")
[[ -z "$WORK_PATH" ]]     && errors+=("--work-path is required")
[[ -z "$BASE_BRANCH" ]]   && errors+=("--base-branch is required")
[[ -z "$BRANCH_PREFIX" ]] && errors+=("--branch-prefix is required")

if [[ ${#errors[@]} -gt 0 ]]; then
  echo "Error: missing required values:" >&2
  for e in "${errors[@]}"; do echo "  $e" >&2; done
  echo "" >&2
  echo "Run ./install.sh --help or copy workflow.config.example.json → workflow.config.json" >&2
  exit 1
fi

# ── generate forbidden prefixes list for protect_paths.py ─────────────────────
build_forbidden_list() {
  local paths="$1"
  local result=""
  IFS=',' read -ra parts <<< "$paths"
  for part in "${parts[@]}"; do
    part="$(echo "$part" | xargs)"  # trim
    if [[ -n "$part" ]]; then
      # Convert "src/pages" → "FRONTEND_ROOT / 'src' / 'pages',"
      local py_parts=""
      IFS='/' read -ra segments <<< "$part"
      for seg in "${segments[@]}"; do
        py_parts+=" / '$seg'"
      done
      result+="  FRONTEND_ROOT${py_parts},\n"
    fi
  done
  echo -e "$result"
}

FORBIDDEN_PREFIXES_LIST="$(build_forbidden_list "$FORBIDDEN_PATHS")"

# ── summary ───────────────────────────────────────────────────────────────────
echo ""
echo "ADO Claude Workflow — Install"
echo "──────────────────────────────"
echo "  product_code   : $PRODUCT_CODE"
echo "  scope_code     : $SCOPE_CODE"
echo "  ado_org        : $ADO_ORG"
echo "  ado_project    : $ADO_PROJECT"
echo "  repo_root      : $REPO_ROOT"
echo "  frontend_root  : $FRONTEND_ROOT"
echo "  work_path      : $WORK_PATH"
echo "  base_branch    : $BASE_BRANCH"
echo "  branch_prefix  : $BRANCH_PREFIX"
echo "  forbidden_paths: $FORBIDDEN_PATHS"
echo ""
$DRY_RUN && echo "[DRY RUN — no files will be written]" && echo ""

# ── install ────────────────────────────────────────────────────────────────────
if ! $DRY_RUN; then
  # Copy templates
  cp -r "$TEMPLATES_DIR/.claude" "$FRONTEND_ROOT/"
  cp -r "$TEMPLATES_DIR/.cursor" "$FRONTEND_ROOT/"

  # Substitute placeholders in all template files
  # macOS sed requires '' after -i; Linux sed requires nothing — handle both
  SED_INPLACE=(-i '')
  if sed --version &>/dev/null 2>&1; then
    SED_INPLACE=(-i)  # GNU sed
  fi

  # Escape special chars for sed replacement values
  esc() { printf '%s\n' "$1" | sed 's/[&/\]/\\&/g'; }

  ESCAPED_PRODUCT_CODE="$(esc "$PRODUCT_CODE")"
  ESCAPED_SCOPE_CODE="$(esc "$SCOPE_CODE")"
  ESCAPED_ADO_ORG="$(esc "$ADO_ORG")"
  ESCAPED_ADO_PROJECT="$(esc "$ADO_PROJECT")"
  ESCAPED_REPO_ROOT="$(esc "$REPO_ROOT")"
  ESCAPED_FRONTEND_ROOT="$(esc "$FRONTEND_ROOT")"
  ESCAPED_WORK_PATH="$(esc "$WORK_PATH")"
  ESCAPED_BASE_BRANCH="$(esc "$BASE_BRANCH")"
  ESCAPED_BRANCH_PREFIX="$(esc "$BRANCH_PREFIX")"

  find "$FRONTEND_ROOT/.claude" "$FRONTEND_ROOT/.cursor" -type f | while read -r file; do
    sed "${SED_INPLACE[@]}" \
      -e "s|{{PRODUCT_CODE}}|$ESCAPED_PRODUCT_CODE|g" \
      -e "s|{{SCOPE_CODE}}|$ESCAPED_SCOPE_CODE|g" \
      -e "s|{{ADO_ORG}}|$ESCAPED_ADO_ORG|g" \
      -e "s|{{ADO_PROJECT}}|$ESCAPED_ADO_PROJECT|g" \
      -e "s|{{REPO_ROOT}}|$ESCAPED_REPO_ROOT|g" \
      -e "s|{{FRONTEND_ROOT}}|$ESCAPED_FRONTEND_ROOT|g" \
      -e "s|{{WORK_PATH}}|$ESCAPED_WORK_PATH|g" \
      -e "s|{{BASE_BRANCH}}|$ESCAPED_BASE_BRANCH|g" \
      -e "s|{{BRANCH_PREFIX}}|$ESCAPED_BRANCH_PREFIX|g" \
      "$file"
  done

  # Substitute multiline forbidden prefixes list in protect_paths.py.
  # We write the replacement value to a temp file to avoid shell-quoting issues
  # (heredoc expansion and triple-quoted strings break when the value contains
  # single quotes or backslashes).
  PROTECT_SCRIPT="$FRONTEND_ROOT/.claude/hooks/scripts/ado_protect_paths.py"
  if [[ -n "$FORBIDDEN_PREFIXES_LIST" ]]; then
    TMPFILE="$(python3 -c "import tempfile, os; f=tempfile.NamedTemporaryFile(delete=False); print(f.name)")"
    printf '%s' "$FORBIDDEN_PREFIXES_LIST" > "$TMPFILE"
    python3 - "$PROTECT_SCRIPT" "$TMPFILE" <<'PYEOF'
import sys, pathlib
script_path = pathlib.Path(sys.argv[1])
replacement = pathlib.Path(sys.argv[2]).read_text(encoding='utf-8')
content = script_path.read_text(encoding='utf-8')
content = content.replace('{{FORBIDDEN_PREFIXES_LIST}}', replacement)
script_path.write_text(content, encoding='utf-8')
PYEOF
    rm -f "$TMPFILE"
  fi

  # Generate settings.local.json from template
  cp "$FRONTEND_ROOT/.claude/settings.local.template.json" \
     "$FRONTEND_ROOT/.claude/settings.local.json"
  rm "$FRONTEND_ROOT/.claude/settings.local.template.json"

  # Create state directory
  mkdir -p "$FRONTEND_ROOT/.claude/state"
  mkdir -p "$FRONTEND_ROOT/.claude/logs/tasks"

  # Make scripts executable
  chmod +x "$FRONTEND_ROOT/.claude/hooks/scripts/"*.py

  echo "Installed to $FRONTEND_ROOT"
  echo ""
  echo "Next steps:"
  echo "  1. Review $FRONTEND_ROOT/.claude/settings.local.json"
  echo "     Add any project-specific Bash permissions you need."
  echo "  2. Add .claude/settings.local.json to .gitignore (it contains local paths)."
  echo "  3. Commit .claude/ and .cursor/ to your repo."
  echo "  4. Install the Azure DevOps MCP server and Serena MCP server."
  echo "  5. Try: 'pickup' to start your first task."
fi
