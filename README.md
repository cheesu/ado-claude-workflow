# ADO Claude Workflow Toolkit

## 이게 뭔가요?

Azure DevOps 작업(work item)을 Claude Code와 Cursor로 처리할 때, **작업 픽업부터 코드 구현, 리뷰, Draft PR 생성까지 전 과정을 자동화**해주는 워크플로우 설정 모음입니다.

Claude Code와 Cursor에 설치하면 AI가 단순한 코딩 도우미를 넘어, ADO 작업 관리와 Git 흐름까지 일관되게 처리하는 자동화 파이프라인으로 동작합니다.

이 툴킷 자체는 Claude나 Cursor 애플리케이션이 아니라, **그 도구들이 읽는 설정·명령 파일의 모음**입니다. `install.sh`로 원하는 프로젝트에 설치해서 사용합니다.

---

## 뭘 할 수 있나요?

### 작업 시작 자동화 (`pickup`)
```
"일해라" 또는 "pickup"
```
- 내 ADO 할당 작업 목록 조회
- 작업 선택 후 상태를 `In Progress`로 변경
- 올바른 베이스 브랜치에서 작업 브랜치 자동 생성
- 작업 내용을 분석해 구현 계획서 작성

### 구현 자동화
- 계획서를 바탕으로 AI가 코드 직접 수정
- 단순 UI 변경은 빠른 경로(light), 로직 변경은 정밀 경로(standard)로 자동 분기
- `yarn lint` + `yarn tsc --noEmit` 검증 자동 실행

### 작업 완료 자동화 (`finish`)
```
"마무리" 또는 "finish"
```
- 변경 diff 기반 리뷰 자동 실행
- 검증 결과 요약 후 사용자 최종 승인 요청
- 커밋 메시지 포맷 자동 적용
- 브랜치 push 및 Draft PR 생성

### 안전 게이트 (항상 동작)
- 실수로 건드리면 안 되는 경로(`src/pages`, `src/shared` 등) 편집 차단
- `git reset --hard`, `git push --force` 등 파괴적 명령 차단
- 사용자 확인 없이 커밋·push·PR 생성 차단

---

## 도구별 지원 범위

| 기능 | Claude Code | Cursor |
|---|---|---|
| ADO work item 조회/상태 변경 | ✅ | ✅ (라우팅만) |
| 브랜치 생성 자동화 | ✅ | ❌ |
| 코드 구현 + 검증 | ✅ | ✅ |
| 커밋/push/PR 자동화 | ✅ | ❌ |
| 안전 게이트(훅) | ✅ | ❌ |

> Claude Code는 전체 자동화 파이프라인을 지원합니다.
> Cursor는 ADO 조회와 커밋 메시지 형식 가이드를 지원합니다.

---

## 어떻게 동작하나요?

### 전체 흐름

```
  User: "pickup"
        │
        ▼
 ┌─────────────────────────────────────────────────────┐
 │  Orchestrator  (Claude Code main session)           │
 │  1. Load guardrails (path / branch rules, ADO ctx)  │
 │  2. Query ADO -> show assigned work items           │
 │  3. User picks one -> ask for explicit confirmation │
 └──────────────────────┬──────────────────────────────┘
                        │  user confirms
                        ▼
 ┌─────────────────────────────────────────────────────┐
 │  Start Approval Token  (TTL 1h)                     │
 │  Hooks verify token before branch create /          │
 │  ADO status change                                  │
 └──────────────────────┬──────────────────────────────┘
                        │
                        ▼
 ┌─────────────────────────────────────────────────────┐
 │  Complexity Classifier                              │
 │  * UI-only change?       -> LIGHT mode              │
 │  * logic / state / API?  -> STANDARD mode           │
 └────────┬──────────────────────────┬─────────────────┘
          │ LIGHT                    │ STANDARD
          ▼                          ▼
 ┌────────────────┐     ┌─────────────────────────────┐
 │  Inline plan   │     │  planner-opus-4_6           │
 │  (max 10 lines)│     │  (subagent)                 │
 └───────┬────────┘     │  -> handoff.md (full plan)  │
         │              └──────────────┬──────────────┘
         └──────────────┬──────────────┘
                        │
                        ▼
 ┌─────────────────────────────────────────────────────┐
 │  implementer-sonnet  (subagent)                     │
 │  reads handoff.md -> modifies code                  │
 │  hooks block edits outside allowed paths            │
 │  yarn tsc --noEmit + yarn lint                      │
 └──────────────────────┬──────────────────────────────┘
                        │
                        ▼
 ┌─────────────────────────────────────────────────────┐
 │  Deterministic Preflight  (before Opus call)        │
 │  * branch pattern check                             │
 │  * forbidden path check                             │
 │  * type check + lint                                │
 └────────┬──────────────────────────┬─────────────────┘
          │ LIGHT (skip reviewer)    │ STANDARD
          ▼                          ▼
 ┌────────────────┐     ┌─────────────────────────────┐
 │  User confirm  │     │  reviewer-opus-4_6          │
 │  gate          │     │  (subagent)                 │
 └───────┬────────┘     │  diff review -> verdict     │
         │              └──────────────┬──────────────┘
         └──────────────┬──────────────┘
                        │  user final approval
                        ▼
 ┌─────────────────────────────────────────────────────┐
 │  Finish Approval Token  (TTL 2h)                    │
 │  Hooks verify token before commit / push / PR       │
 └──────────────────────┬──────────────────────────────┘
                        │
                        ▼
 ┌──────────────────────────────────────────────────────┐
 │  git commit -> git push -> az repos pr create (Draft)│
 └──────────────────────────────────────────────────────┘
```

### 3개의 AI 에이전트

| 에이전트 | 모델 | 역할 |
|---|---|---|
| `planner-opus-4_6` | claude-opus-4-6 | 작업 내용 분석, 코드베이스 탐색, 구현 계획서 작성 |
| `implementer-sonnet` | claude-sonnet-4-6 | 계획서 실행, 코드 수정, 검증 |
| `reviewer-opus-4_6` | claude-opus-4-6 | diff 기반 리뷰, 커밋·PR 준비 여부 판단 |

> Light 경로에서는 planner와 reviewer를 건너뛰어 Opus 호출 비용을 절감합니다.

### 4개의 안전 훅

| 훅 | 시점 | 차단 대상 |
|---|---|---|
| `ado_protect_paths.py` | 파일 편집 전 | 금지 경로(`src/pages`, `src/shared` 등) 수정 시도 |
| `ado_guard_shell.py` | 셸 명령 실행 전 | 파괴적 git 명령, 미승인 브랜치 생성, 미승인 커밋·push |
| `ado_guard_mcp_ado.py` | ADO MCP 호출 전 | 미승인 work item 상태 변경, 브랜치 생성, PR 생성 |
| `ado_after_edit_context.py` | 파일 편집 후 | (차단 아님) 검증 필요 리마인더 1회 주입 |

### 세션 로그 분석기

작업 완료 후 `ado_session_log.py`를 실행하면 해당 작업에서 에이전트가 소비한 토큰과 API 호출 횟수를 분석해 `.claude/logs/tasks/{taskNumber}_{날짜}.md`에 기록합니다.

```bash
# 가장 최근 세션 자동 탐색 후 로그 파일에 기록
python3 .claude/hooks/scripts/ado_session_log.py analyze \
  --task-number 70123 \
  --auto-session \
  --write-log

# 세션 ID를 직접 지정
python3 .claude/hooks/scripts/ado_session_log.py analyze \
  --task-number 70123 \
  --session-id <sessionId>
```

출력 예시:

```
| agent            | input  | output | cache_read | cache_create | API calls |
|------------------|--------|--------|------------|--------------|-----------|
| planner          | 12.3K  |  2.1K  |    45.0K   |     8.0K     |     8     |
| implementer      | 34.5K  |  5.6K  |   120.0K   |    22.0K     |    24     |
| reviewer         |  8.1K  |  1.2K  |    30.0K   |     5.0K     |     5     |
| **total**        | 54.9K  |  8.9K  |   195.0K   |    35.0K     |    37     |
```

각 에이전트별로 탐색(Explore) → 구현(Implement) → 검증(Verify) 3단계로 분류해 단계별 토큰 사용량도 확인할 수 있습니다.

---

## 설치 전 준비

### 필수

**Python 3.8+**
```bash
python3 --version
```

**Claude Code CLI**
```bash
claude --version
```

**Azure CLI + DevOps 확장**
```bash
# macOS
brew install azure-cli
az extension add --name azure-devops
az login
az devops configure --defaults organization=https://dev.azure.com/{your-org}

# Windows
winget install Microsoft.AzureCLI
az extension add --name azure-devops
az login
az devops configure --defaults organization=https://dev.azure.com/{your-org}
```

### MCP 서버 (Claude Code에서 ADO 자동화 사용 시 필수)

**Azure DevOps MCP 서버** 설치 및 `~/.claude/settings.json`에 등록  
**Serena MCP 서버** 설치 및 등록 (코드 심볼 탐색에 사용)

> MCP 서버 설치 방법은 각 서버의 공식 문서를 참고하세요.

### 선택

**Cursor IDE** — Cursor 룰 기능을 사용하려면 필요

---

## 설치 방법

### 1. 설정 파일 준비

```bash
cd ado-claude-workflow
cp workflow.config.example.json workflow.config.json
```

`workflow.config.json`을 열어 값을 채웁니다.

```json
{
  "product_code": "MY-PRODUCT",
  "scope_code": "FE",
  "ado_org": "your-org",
  "ado_project": "YOUR_PROJECT",
  "repo_root": "/절대경로/your-repo",
  "frontend_root": "/절대경로/your-repo/frontend",
  "work_path": "src/products/my-product",
  "base_branch": "product/my-product/main",
  "branch_prefix": "product/my-product",
  "forbidden_paths": ["src/pages", "src/shared"]
}
```

| 항목 | 예시 | 설명 |
|------|------|------|
| `product_code` | `MY-PRODUCT` | 커밋/PR 접두사에 쓰이는 제품 코드 |
| `scope_code` | `FE` | 스코프 코드 (BE, FE 등) |
| `ado_org` | `your-org` | Azure DevOps 조직 이름 |
| `ado_project` | `MY_PROJECT` | Azure DevOps 프로젝트 이름 |
| `repo_root` | `/path/to/repo` | git 레포 루트 절대경로 |
| `frontend_root` | `/path/to/repo/frontend` | 프론트엔드 디렉토리 절대경로 |
| `work_path` | `src/products/my-product` | 제품 코드가 있는 상대경로 (편집 허용 영역) |
| `base_branch` | `product/my-product/main` | 작업 브랜치의 베이스가 되는 브랜치 |
| `branch_prefix` | `product/my-product` | 작업 브랜치명 앞에 붙는 접두사 |
| `forbidden_paths` | `["src/pages", "src/shared"]` | AI가 절대 편집하면 안 되는 경로 목록 |

### 2. 설치 실행

```bash
chmod +x install.sh

# 먼저 dry-run으로 확인
./install.sh --config workflow.config.json --dry-run

# 문제 없으면 실제 설치
./install.sh --config workflow.config.json
```

설치 스크립트가 자동으로 처리하는 것:
- `frontend/.claude/` 에 에이전트, 스킬, 훅 스크립트 복사
- `frontend/.cursor/rules/` 에 Cursor 룰 복사
- 모든 파일의 `{{PLACEHOLDER}}`를 실제 값으로 치환
- `settings.local.json` 생성 (훅 배선 포함)
- 훅 스크립트에 실행 권한 부여
- 상태 디렉토리(`state/`, `logs/tasks/`) 생성

### 3. `.gitignore` 설정

설치 후 아래 항목을 `.gitignore`에 추가하세요.

```gitignore
# ADO workflow — 로컬 전용 파일
frontend/.claude/settings.local.json
frontend/.claude/state/
frontend/.claude/logs/
```

에이전트, 스킬, 훅 스크립트(`.claude/agents/`, `.claude/skills/`, `.claude/hooks/`)는 팀 공유 목적으로 커밋해도 됩니다.

### 4. 동작 확인

Claude Code를 프론트엔드 디렉토리에서 열고 아래를 입력해보세요.

```
tasks
```
→ 내 ADO 할당 작업 목록이 나오면 정상입니다.

---

## 사용 방법

| 명령 | 동작 |
|------|------|
| `tasks` | 내 ADO 할당 작업 목록만 조회 (상태 변경 없음) |
| `pickup` | 작업 선택 → 브랜치 생성 → 계획 → 구현까지 자동 진행 |
| `finish` | 리뷰 → 검증 → 사용자 승인 → 커밋 → push → Draft PR |
| `session review` | 완료된 작업의 세션 리뷰 리포트 생성 |

각 단계에서 사용자 확인을 요청하며, 명시적 승인 없이 상태 변경이나 커밋은 일어나지 않습니다.

### 세션 리뷰 리포트

작업이 끝난 뒤 원할 때 실행해서 해당 세션을 분석합니다.

```
session review 70123
session review 70123 summary
session review
```

- 태스크 번호 생략 시 현재 브랜치에서 자동 추론
- `summary` 옵션: 에이전트별 합계 + 주요 낭비 포인트만 (기본값은 턴별 상세 분석)
- 결과물: `.claude/docs/{taskNumber}_SESSION_REVIEW_REPORT.md`
- HTML 출력 원하면 `session review 70123 html` 추가

리포트에 포함되는 내용:

| 섹션 | 내용 |
|------|------|
| 전체 요약 | 에이전트별 API 호출 수, 토큰 비용, 비중 |
| Phase 별 분석 | 탐색 → 구현 → 검증 단계별 툴 호출과 토큰 소비 |
| 낭비 포인트 | 중복 탐색, 불필요한 반복 호출 등 구체적 지적 |
| 툴 사용 분류 | Grep/Bash 호출이 정당했는지, 심볼 검색으로 대체 가능했는지 |
| 개선 제안 | 다음 세션 플래너 프롬프트에 추가할 규칙 |
| 효율성 점수 | 에이전트별 10점 만점 평가 |

---

## 설치 후 구조

```
frontend/
├── .claude/
│   ├── agents/                    ← planner, implementer, reviewer 에이전트 정의
│   ├── skills/                    ← pickup, finish, tasks, session-review, ado-guardrails, 메인 플로우
│   ├── hooks/scripts/             ← 7개 Python 훅·유틸리티 스크립트
│   ├── state/                     ← 런타임 토큰·핸드오프 파일 (gitignore 대상)
│   └── settings.local.json        ← 훅 배선 + 권한 설정 (gitignore 대상)
└── .cursor/
    └── rules/
        ├── ado_local_router.mdc   ← ADO 작업 시작/조회/마무리 자연어 라우팅
        └── commit_pr_guide.mdc    ← 커밋/PR 메시지 형식 가이드
```

---

## 설치 체크리스트

```
[ ] Python 3.8+ 확인
[ ] Claude Code CLI 설치 확인
[ ] Azure CLI 설치 + az login
[ ] az extension add --name azure-devops
[ ] Azure DevOps MCP 서버 설치 및 등록
[ ] Serena MCP 서버 설치 및 등록
[ ] workflow.config.json 값 입력
[ ] ./install.sh --config workflow.config.json --dry-run 확인
[ ] ./install.sh --config workflow.config.json 실행
[ ] .gitignore에 settings.local.json, state/, logs/ 추가
[ ] Claude Code에서 "tasks" 입력해 ADO 조회 확인
```

---

## 라이선스

MIT
