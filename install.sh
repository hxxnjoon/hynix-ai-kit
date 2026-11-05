#!/usr/bin/env bash
# hynix-ai-kit 설치기
#
#   bash install.sh                 현재 폴더(과제 루트)에 설치
#   bash install.sh --target DIR    지정한 과제 루트에 설치
#   bash install.sh --user          과제 폴더를 건드리지 않고 ~/.agents 아래에 설치
#   bash install.sh --check [--user] [--target DIR]   설치 상태 확인
#   bash install.sh --force         내용이 다른 기존 hk-* 스킬을 덮어씀
#
# 과제 폴더에서 바뀌는 것 (프로젝트 설치):
#   AGENTS.md          기존 내용 보존, 하네스 블록만 추가 또는 갱신 (원본은 .hk/AGENTS.md.orig)
#   .agents/skills/    hk-* 스킬 7개
#   .hk/               도구, 템플릿
#   TASK.md, DECISIONS.md   없을 때만 템플릿 복사
set -euo pipefail

KIT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$PWD"
MODE="project"
CHECK=0
FORCE=0
SKILLS=(hk-start hk-data hk-design hk-build hk-verify hk-handoff hk-wrap)
BEGIN="<!-- hynix-ai-kit:begin -->"

while [ $# -gt 0 ]; do
  case "$1" in
    --user) MODE="user" ;;
    --check) CHECK=1 ;;
    --force) FORCE=1 ;;
    --target) shift; TARGET="$(cd -- "$1" && pwd)" ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 64 ;;
  esac
  shift
done

say()  { printf '  %s\n' "$*"; }
fail() { printf '중단: %s\n' "$*" >&2; exit 1; }

if [ "$MODE" = "user" ]; then
  SKILL_DEST="$HOME/.agents/skills"
  HK_DEST="$HOME/.agents/hynix-ai-kit"
else
  [ "$TARGET" != "$KIT_DIR" ] || fail "키트 폴더 자체에는 설치하지 않습니다. 과제 루트에서 실행하세요."
  SKILL_DEST="$TARGET/.agents/skills"
  HK_DEST="$TARGET/.hk"
fi

# ---------- 확인 모드 ----------
if [ "$CHECK" = 1 ]; then
  bad=0
  for s in "${SKILLS[@]}"; do
    if [ -f "$SKILL_DEST/$s/SKILL.md" ] && cmp -s "$KIT_DIR/.agents/skills/$s/SKILL.md" "$SKILL_DEST/$s/SKILL.md"; then
      say "OK    스킬 $s"
    else
      say "FAIL  스킬 $s ($SKILL_DEST/$s)"; bad=1
    fi
  done
  for f in profile.py metrics.py preflight.py; do
    if cmp -s "$KIT_DIR/tools/$f" "$HK_DEST/tools/$f"; then say "OK    도구 $f"; else say "FAIL  도구 $f"; bad=1; fi
  done
  if [ "$MODE" = "project" ]; then
    if grep -qF "$BEGIN" "$TARGET/AGENTS.md" 2>/dev/null; then say "OK    AGENTS.md 하네스 블록"; else say "FAIL  AGENTS.md 하네스 블록 없음"; bad=1; fi
    [ ! -f "$TARGET/AGENTS.override.md" ] || say "WARN  AGENTS.override.md가 있어 AGENTS.md보다 우선합니다"
  else
    cmp -s "$KIT_DIR/AGENTS.md" "$HK_DEST/AGENTS.md" && say "OK    규칙 파일 $HK_DEST/AGENTS.md" || { say "FAIL  규칙 파일"; bad=1; }
  fi
  [ "$bad" = 0 ] && echo "설치 확인 완료" || echo "설치에 문제가 있습니다"
  exit "$bad"
fi

# ---------- 쓰기 권한 ----------
probe_parent="$( [ "$MODE" = user ] && echo "$HOME" || echo "$TARGET" )"
if ! ( tmp="$(mktemp "$probe_parent/.hk-probe.XXXXXX" 2>/dev/null)" && rm -f "$tmp" ); then
  if [ "$MODE" = project ]; then
    fail "과제 폴더에 쓰기 권한이 없습니다: $TARGET → bash install.sh --user 로 다시 실행하세요."
  else
    fail "홈 폴더에 쓰기 권한이 없습니다. README의 '설치 없이 쓰기'를 따르세요."
  fi
fi

echo "hynix-ai-kit 설치 ($MODE) → $( [ "$MODE" = user ] && echo "$HOME/.agents" || echo "$TARGET" )"

# ---------- 스킬 ----------
mkdir -p "$SKILL_DEST"
for s in "${SKILLS[@]}"; do
  src="$KIT_DIR/.agents/skills/$s"
  dst="$SKILL_DEST/$s"
  if [ -e "$dst" ] && ! diff -rq "$src" "$dst" >/dev/null 2>&1; then
    if [ "$FORCE" = 1 ]; then rm -rf "$dst"; else
      fail "$dst 가 이미 있고 내용이 다릅니다. 확인 후 --force 로 덮어쓰세요."
    fi
  fi
  if [ -e "$dst" ]; then say "유지  스킬 $s (동일)"; else cp -R "$src" "$dst"; say "설치  스킬 $s"; fi
done

# ---------- 도구와 템플릿 ----------
mkdir -p "$HK_DEST/tools" "$HK_DEST/templates"
cp "$KIT_DIR"/tools/*.py "$HK_DEST/tools/"
cp "$KIT_DIR"/templates/*.md "$HK_DEST/templates/"
( cd "$KIT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo unknown ) > "$HK_DEST/VERSION"
say "설치  도구 3종, 템플릿 4종 → $HK_DEST"

if [ "$MODE" = user ]; then
  cp "$KIT_DIR/AGENTS.md" "$HK_DEST/AGENTS.md"
  say "설치  규칙 → $HK_DEST/AGENTS.md (과제 폴더는 바꾸지 않음)"
  cat <<EOF

다음 단계: 같은 과제 폴더에서 Codex 새 세션을 열고 첫 메시지로 보내세요.
  ~/.agents/hynix-ai-kit/AGENTS.md를 이 세션 작업 규칙으로 따라줘(과제 안내가 우선).
  도구는 ~/.agents/hynix-ai-kit/tools, 템플릿은 ~/.agents/hynix-ai-kit/templates에 있어.
  기록 문서를 과제 폴더에 쓸 수 없으면 대화에 출력해줘. 먼저 \$hk-start 해줘.
EOF
  exit 0
fi

# ---------- AGENTS.md 병합 ----------
python3 - "$KIT_DIR/AGENTS.md" "$TARGET/AGENTS.md" "$HK_DEST" <<'PY'
import os, sys
kit, dst, hk = sys.argv[1:4]
block = open(kit, encoding="utf-8").read().strip() + "\n"
B, E = "<!-- hynix-ai-kit:begin -->", "<!-- hynix-ai-kit:end -->"
if not os.path.exists(dst):
    open(dst, "w", encoding="utf-8").write(block)
    print("  생성  AGENTS.md")
    sys.exit()
cur = open(dst, encoding="utf-8").read()
orig = os.path.join(hk, "AGENTS.md.orig")
if B in cur and E in cur:
    head, rest = cur.split(B, 1)
    tail = rest.split(E, 1)[1]
    new = head + block.strip() + tail
    print("  갱신  AGENTS.md 하네스 블록 (기존 내용 보존)")
else:
    if not os.path.exists(orig):
        open(orig, "w", encoding="utf-8").write(cur)
    new = cur.rstrip() + "\n\n" + block
    print("  추가  AGENTS.md 끝에 하네스 블록 (원본은 .hk/AGENTS.md.orig, 기존 내용이 우선)")
open(dst, "w", encoding="utf-8").write(new)
PY
[ ! -f "$TARGET/AGENTS.override.md" ] || say "주의  AGENTS.override.md가 있어 AGENTS.md보다 우선합니다. 내용을 확인하세요."

# ---------- 기록 템플릿 ----------
for f in TASK.md DECISIONS.md; do
  if [ -e "$TARGET/$f" ]; then say "유지  $f (이미 있음)"; else cp "$KIT_DIR/templates/$f" "$TARGET/$f"; say "생성  $f"; fi
done

git -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  && say "git   저장소 확인" \
  || say "git   저장소가 아닙니다. 과제 안내에 문제가 없으면 'git init'을 고려하세요 (작업 이력이 평가에 쓰임)."

cat <<'EOF'

다음 단계: 같은 과제 폴더에서 Codex 새 세션을 열고 /skills 로 hk-* 7개가 보이는지 확인한 뒤
  $hk-start
스킬이 보이지 않으면: "AGENTS.md를 따르고 .agents/skills/hk-start/SKILL.md를 읽고 진행해"
EOF
