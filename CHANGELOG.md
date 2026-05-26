# Changelog

ADO Claude Workflow Toolkit의 변경 히스토리.

이 툴킷은 `[레포명]` 레포의 `[제품코드]` 제품 frontend Claude Code 워크플로우에서 추출·일반화된 것으로,
아래 히스토리는 원본 프로젝트에서의 변경 이력을 승계한다.

> **원본 구조**: ADO 조직(`{{ADO_ORG}}`) 하위에 **ADO 프로젝트**(`{{ADO_PROJECT}}`)가 있고,
> 그 아래 **모노레포**(`{{REPO_ROOT}}`)가 있으며, 레포 내에서 제품별로 **브랜치·디렉토리**(`{{PRODUCT_CODE}}`)가
> 구분되는 형태. 즉 `ADO 프로젝트 > 레포 > 제품코드` 3단계 계층 구조.

**작성 규칙**
- 에이전트/스킬/훅/설정 파일을 수정할 때마다 항목 추가.
- 날짜는 `YYYY-MM-DD` 형식.
- `변경 파일`, `변경 내용`, `변경 이유`, `리스크 검토` 필수 기재.
- 항목은 최신순(위가 최신).

---

## 2026-05-26

### 툴킷 독립 추출 — [제품코드] 전용 → 범용 파라미터화

**변경 파일**
- `templates/.claude/agents/planner-opus-4_6.md` (신규)
- `templates/.claude/agents/implementer-sonnet.md` (신규)
- `templates/.claude/agents/reviewer-opus-4_6.md` (신규)
- `templates/.claude/skills/ado-guardrails/SKILL.md` (신규, 구 `[제품코드]-frontend-guardrails`)
- `templates/.claude/skills/ado-pickup-task/SKILL.md` (신규, 구 `[제품코드]-ado-pickup-task`)
- `templates/.claude/skills/ado-finish-task/SKILL.md` (신규, 구 `[제품코드]-ado-finish-task`)
- `templates/.claude/skills/pickup/SKILL.md` (신규)
- `templates/.claude/skills/finish/SKILL.md` (신규)
- `templates/.claude/skills/tasks/SKILL.md` (신규)
- `templates/.claude/hooks/scripts/ado_protect_paths.py` (신규, 구 `[제품코드]_protect_paths.py`)
- `templates/.claude/hooks/scripts/ado_guard_shell.py` (신규, 구 `[제품코드]_guard_shell.py`)
- `templates/.claude/hooks/scripts/ado_guard_mcp_ado.py` (신규, 구 `[제품코드]_guard_mcp_ado.py`)
- `templates/.claude/hooks/scripts/ado_after_edit_context.py` (신규, 구 `[제품코드]_after_edit_context.py`)
- `templates/.claude/hooks/scripts/ado_start_approval.py` (신규, 구 `[제품코드]_start_approval.py`)
- `templates/.claude/hooks/scripts/ado_finish_approval.py` (신규, 구 `[제품코드]_finish_approval.py`)
- `templates/.claude/settings.local.template.json` (신규, 구 `settings.local.json`)
- `templates/.cursor/rules/ado_local_router.mdc` (신규, 구 `[제품코드]_ado_local_router.mdc`)
- `templates/.cursor/rules/commit_pr_guide.mdc` (신규, 구 `frontend_commit_pr_guide.mdc`)
- `install.sh` (신규)
- `workflow.config.example.json` (신규)
- `README.md` (신규)

**변경 내용**

1. **범용 파라미터화**: 파일 전체에서 [제품코드] 전용 하드코딩 값을 `{{PLACEHOLDER}}` 형식으로 치환
   - `[제품코드]` → `{{PRODUCT_CODE}}`
   - `FE` → `{{SCOPE_CODE}}`
   - `[ADO 조직명]` → `{{ADO_ORG}}`
   - `[ADO 프로젝트명]` → `{{ADO_PROJECT}}`
   - `product/[제품코드]/main` → `{{BASE_BRANCH}}`
   - `product/[제품코드]` → `{{BRANCH_PREFIX}}`
   - `src/products/[제품코드]` → `{{WORK_PATH}}`
   - `[레포 절대경로]` → `{{REPO_ROOT}}`
   - `[프론트엔드 절대경로]` → `{{FRONTEND_ROOT}}`

2. **훅 스크립트 경로 탈하드코딩**: `FRONTEND_ROOT`/`REPO_ROOT`를 `Path(__file__).resolve().parents[N]` 방식으로 변경 → 어떤 프로젝트에 설치해도 경로 재계산 불필요

3. **승인 토큰 파일명 변경**: `[제품코드]_start_approval.json` / `[제품코드]_finish_approval.json` → `ado_start_approval.json` / `ado_finish_approval.json`

4. **스킬/에이전트 이름 변경**: `[제품코드]-*` 접두사 제거, `ado-*` 접두사로 통일 (guardrails, pickup-task, finish-task)

5. **install.sh 추가**: `workflow.config.json`을 읽어 `{{PLACEHOLDER}}` 치환 후 타겟 프로젝트에 복사. macOS/Linux sed 양쪽 대응. forbidden paths는 Python으로 멀티라인 치환.

6. **cursor rules 통합**: `frontend_commit_pr_guide.md`(orphan)와 `frontend_commit_pr_guide.mdc` 두 파일을 단일 `commit_pr_guide.mdc`로 병합 — `.md` 전용 내용(기본 원칙, 타입 선택 기준, 예시)과 `.mdc` 전용 내용(PR 체크리스트, 스크린샷 섹션)을 통합

**변경 이유**

- 동일 워크플로우를 다른 제품([타 제품코드] 등) 또는 타 프로젝트에 재사용하기 위해 [레포명]/[제품코드] 특정 코드를 분리
- 시스템 설계(멀티 에이전트, 훅 게이트, 승인 토큰 패턴)를 독립적으로 버전 관리하고 공유하기 위함

**리스크 검토**

- 원본 [레포명] 프로젝트의 파일은 변경하지 않음 — 이 추출 작업은 새 디렉토리에만 영향
- 훅 스크립트의 상대경로 방식(`Path(__file__).parents[N]`)은 설치 위치가 항상 `frontend/.claude/hooks/scripts/`이므로 depth가 고정되어 안전
- `settings.local.json`은 `.gitignore` 대상이므로 commit_pr_guide.mdc와 달리 각 프로젝트에서 직접 관리

---

## 2026-04-30 (3) — 원본 프로젝트에서 승계

### WORKFLOW.md / MODEL_SPLIT.md — Light mode 경로 문서화

**변경 내용**

- `CLAUDE_CODE_WORKFLOW.md`: 복잡도 사전 분류 단계 추가, light/standard 분기 명시, finish 단계에 complexity_verdict.txt 확인 후 reviewer 스킵 분기 추가, Light → Standard 에스컬레이션 조건 추가
- `CLAUDE_CODE_MODEL_SPLIT.md`: light mode 전용 섹션 추가 (분류 흐름 다이어그램, 비용 효과 요약)

**변경 이유**

`ado-pickup-task/SKILL.md`에 light mode가 완전히 구현되어 있었으나, engineering 문서가 standard 파이프라인만 기술해 실제 동작과 불일치 상태였음.

**리스크**: 문서 변경만이며 실제 코드/훅/스킬 동작에는 영향 없음.

---

## 2026-04-30 (2) — 원본 프로젝트에서 승계

### 훅 방어 패턴 강화

**변경 내용**

- `ado_guard_shell.py`에 DESTRUCTIVE_PATTERNS 2개 추가: `git branch -D`, `git push <remote> :<refspec>`
- `branch_creation_uses_compound_git_chain()`에 `'\n' in effective_command` 조건 추가
- PreToolUse/PostToolUse 매처: `Edit|Write` → `Edit|Write|MultiEdit`

**변경 이유**

세션 리뷰 분석 결과 발견된 훅 공백 3건:
- `git branch -D`, `git push origin :브랜치` 가 DESTRUCTIVE_PATTERNS에 없어 차단 안 됨
- `MultiEdit` 도구가 매처에 없어 경로 보호 훅이 실행되지 않는 공백 존재
- 개행(`\n`)으로 연결된 compound command가 차단되지 않았음

**리스크**: DESTRUCTIVE_PATTERNS 정규식이 구체적이어서 정상 명령과 겹칠 가능성 없음.

---

## 2026-04-30 — 원본 프로젝트에서 승계

### planner — Tool usage rules 섹션 추가

**변경 내용**

`planner-opus-4_6.md`에 `## Tool usage rules` 섹션 신규 추가:
- Serena vs Grep 사용 기준 (심볼 검색은 Serena, raw 패턴만 Grep)
- 파일 읽기 규칙 (같은 파일 2회 Read 금지, 분할 Read 금지)
- 아이콘/prop 검증 규칙 (실사용 예시 1개 발견 시 탐색 종료)

**변경 이유**

세션 리뷰 분석 결과: planner가 94 turns 중 76% API를 소비. 주요 낭비 패턴:
- Grep으로 심볼 참조 검색 (Serena 대신) — ~8 turns
- 동일 파일 분할 Read 후 재Read — 4 turns
- 동일 경로 `get_symbols_overview` 4회 연속 — 3 turns
- 아이콘 실사용 예시 발견 후에도 PnP 내부 탐색 9회 반복 — 11 turns

기존 권고 수준 문구("Prefer Serena / whenever practical")는 planner가 무시 가능했음 → 강한 금지 규칙으로 대체.

**리스크**: Serena 빈 결과 시 Grep fallback 허용 조항 포함 → 낮음.

---

<!-- 새 항목 추가 시 이 주석 위에 작성 -->
