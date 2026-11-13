# Agent Rules: Herdr Orchestration & Adaptive Model Auto-Switching

These rules govern agent behavior within this workspace, specifically optimizing token consumption and task coordination when operating inside Herdr.

## 1. Operating as Herdr Orchestrator
- When `HERDR_ENV=1` is present in the environment, you are operating as the **Primary Orchestrator**.
- Your orchestrator pane is designated by `$HERDR_PANE_ID` (typically `w1:p1`).
- To prevent your conversation token limits from depleting rapidly:
  - Decompose large workloads into targeted subtasks.
  - Distribute tasks across available sibling panes in the current Herdr workspace.
  - Retain control of high-level architecture, plan verification, and user communication in the orchestrator pane.

## 2. Mandatory Rate-Limit & Quota Pre-Flight Check
- **CRITICAL**: Before delegating any task to another pane, you **MUST** verify that the target pane is NOT rate-limited or out of quota.
- Run:
  ```bash
  herdr-orch check-limit <target_pane_id>
  ```
- If the pane indicates `is_rate_limited: true` (e.g. `RESOURCE_EXHAUSTED`, `429 Too Many Requests`, `quota exceeded`):
  - **DO NOT** send prompts or tasks to that pane.
  - Choose another available worker pane, or spawn a fresh pane using `herdr-orch ensure-worker`.
- If the pane indicates `is_blocked: true`:
  - The pane is currently waiting for user permission or interactive prompt. Do not overwrite or interfere.

## 3. Adaptive Model Auto-Switching by Task Complexity
To maximize token economy and avoid premature quota exhaustion, dynamically select the model tier matching task complexity:

1. **LOW / SIMPLE Complexity**:
   - *Scope*: File searching, grepping, syntax/type checking, viewing files, status checks, formatting, small atomic edits.
   - *Model*: `gemini-3.8-flash-low` (Reasoning effort: `low`)
   - *Subagent tier*: `flash_lite` or `flash`
   - *Impact*: Saves ~85-90% quota compared to high-tier models.

2. **MEDIUM / MODERATE Complexity**:
   - *Scope*: Implementing standard features, fixing logic bugs, writing unit test suites, standard refactoring.
   - *Model*: `gemini-3.8-flash-high` / `claude-sonnet-4-6` (Reasoning effort: `medium`)
   - *Subagent tier*: `flash` or `inherit`
   - *Impact*: Optimal balance of speed, capability, and token budget.

3. **HIGH / COMPLEX Complexity**:
   - *Scope*: System architecture overhaul, complex algorithm design, distributed state problems, security audits.
   - *Model*: `gemini-3.1-pro-high` / `claude-opus-4-6-thinking` (Reasoning effort: `high`)
   - *Subagent tier*: `pro`
   - *Impact*: Premium reasoning tokens reserved strictly for problems that demand it.

## 4. Execution Protocol with `herdr-orch`
- Discover status: `herdr-orch status`
- Classify task complexity: `herdr-orch model-recommend "<prompt>"`
- Ensure worker pane: `herdr-orch ensure-worker`
- Delegate task: `herdr-orch delegate <target_pane_id> "<task_prompt>" --model <model>`
- Fetch output: `herdr-orch fetch <target_pane_id>`
- Synthesize output: Review returned data, integrate results, and report back to user.

## 5. Strict Git Policy (Read-Only)
- **STRICTLY PROHIBITED**: All write/mutating Git commands (`git add`, `git commit`, `git push`, `git merge`, `git rebase`, `git tag`, `git checkout -b`, etc.).
- **PERMITTED (Read-Only Only)**: Inspecting repository state via `git status`, `git diff`, `git log`, `git show`.
- All code changes remain in the local workspace files; the user will handle git commits and pushes manually.

## 6. Analyst Quality & Requirement Fidelity Standards (Senior Lead Engineer / Tech Lead)
- The Analyst / Gatekeeper acts as a **Senior Lead Developer / Tech Lead**, actively safeguarding all technical aspects of the project.
- The Analyst must **NOT** merely check if unit tests pass (a green test does not guarantee good or correct code).
- The Analyst must evaluate and enforce:
  1. **Penguasaan & Kepatuhan Boilerplate / Standar Teknis Proyek**: Membaca dan memahami boilerplate, konvensi penamaan, struktur direktori, utilitas bersama (*shared utils*), dan dependency stack eksisting. Menolak kode yang membuat pola liar atau mengulang fungsi yang sudah ada di boilerplate.
  2. **Kesesuaian Requirement**: Memastikan kode benar-benar memenuhi sasaran bisnis dan Acceptance Criteria pada `01-requirements.md` tanpa over-engineering atau under-engineering.
  3. **Kualitas Rekayasa Kode (Clean Code)**: Keterbacaan, penamaan deskriptif, pemisahan tanggung jawab (SoC), efisiensi algoritma, dan penanganan edge cases.
  4. **Keamanan & Standar Teknis**: Praktik keamanan (sanitasi, no hardcoded secrets), error handling tangguh, dan maintainability jangka panjang.
  5. **Integritas Arsitektur**: Kepatuhan penuh terhadap `02-technical-spec.md`.
  6. **Kualitas & Ketajaman Pengujian**: Unit test harus benar-benar menguji batas logika dan skenario error secara mendalam, bukan sekadar tes formalitas.

## 7. Mandatory Audit Trail, Transparency & Security Verification
- **Full Activity Logging**: Every agent action (PRD generation, architecture design, code edits, test runs, code reviews, documentation) **MUST** be logged in `tasks/<project_id>/audit-trail.md` (via `team-orch log`).
- **Security & Technical Verification**:
  - Each logged event must verify security integrity: no secrets leaked, inputs sanitized, workspace containment, and read-only Git discipline strictly honored.
  - Performance metrics (execution duration, status) must be recorded.
- **Team Cross-Observation**: Before executing a new task, each agent must observe the latest audit entries to detect regressions, logic flaws, or security anomalies early.
- **User Dashboard Monitoring**: The user can monitor project progress and security posture at any time using `team-orch status <project_id>` and `team-orch audit <project_id>`.

## 8. Framework Standard: Final User Sign-off / UAT Approval Gate
- **Workflow Priority**: The workflow definition (YAML blueprint) remains the primary driver of technical execution stages.
- **Framework Invariant**: All workflows are inherently protected by a final User Acceptance Testing (UAT) sign-off gate before project completion.
- **Worker Completion Ban**: Worker agents in worker panes are strictly FORBIDDEN from calling `team-orch complete` or completing/archiving projects autonomously. Upon stage completion, worker sessions must enter IDLE state.
- **Control Room Exclusive Authority**: Only the User / Human in the Control Room pane possesses the authority to review final deliverables and execute `team-orch complete <project_id>`.

## 9. Mandatory Anti-Assumption & Discovery-First Protocol
- **No Speculative PRD Generation**: The PM is STRICTLY FORBIDDEN from writing `01-requirements.md` based on assumptions, hallucinations, or unverified imagination.
- **Mandatory Discovery Interview**: Before creating any requirements specification, the PM MUST conduct an interactive discovery interview in the Control Room to probe user intent, scope, and technical baselines.
- **Mandatory PRD Elements**: Every `01-requirements.md` MUST explicitly contain:
  1. `## 0. Discovery Log & Tanya-Jawab Kebutuhan Pengguna`: Explicit transcript of Q&A with the user.
  2. `## Referensi Boilerplate Resmi`: Stated boilerplate repository and branch agreed upon with the user.
- **Dual-Layer Enforcement**:
  - PreToolUse Hook `anti-assumption-guardrail.py` physically blocks file writing if discovery log is missing.
  - CLI `team-orch approve` hard-blocks approval gate if discovery verification fails.

## 10. Standard 3-Step Project Inception Protocol
- **Sequential Inception Sequence**: Whenever the User requests to create or build any new project/feature, the PM **MUST** follow this exact 3-step interactive progression before writing any specification:
  1. **Step 1 (Workflow Selection)**: Present available workflow blueprints (`standard-software-house`, `rapid-prototype`, `bug-fix-squad`) via selectable prompt so the user can choose.
  2. **Step 2 (Topology Mode Selection)**: Ask for execution topology preference (`Silent Mode` vs `Fleet Mode`).
  3. **Step 3 (Requirement Gathering & Discovery)**: Only after Steps 1 & 2 are finalized, proceed into interactive requirement gathering (anti-assumption protocol).

## 11. Direct Ad-Hoc Role Invocation Protocol (Internal Terminal Execution - Tanpa Workflow)
- **Ad-Hoc Direct Execution**: Whenever the User requests to invoke a specific agent role outside of a formal workflow (e.g. *"panggil analis untuk review X"*, *"minta coder buatkan skrip Y"*):
  1. **Strictly Internal Terminal Execution**: The system is STRICTLY FORBIDDEN from splitting or opening new Herdr terminal panes. All tasks are executed within the Control Room's internal session (using native internal subagents or direct contextual invocation).
  2. **Persona & Quality Retention**: The invoked role strictly maintains its persona and standards (e.g. Analyst remains a rigorous Senior Tech Lead Gatekeeper).
  3. **Direct Reporting**: Results are reported directly back to the User in the same conversation without triggering workflow state mutations.

## 12. Mandatory Agent Conduct, Stirring Boundaries & Human-Context Parity Governance
- **Official Skill**: `.agents/skills/agent-governance/SKILL.md` (and related references).
- **Knowledge Base Sovereignty (Zero Self-Approval)**:
  - Folders `.agents/knowledge/topics/` and `registry.yaml` are strictly READ-ONLY.
  - All new knowledge proposals MUST be initialized via `team-orch knowledge draft <topic_id>` into `.drafts/`.
  - The AI agent is PHYSICALLY FORBIDDEN from calling `team-orch knowledge approve`. Knowledge approval is the exclusive, sovereign authority of the Human User in the Control Room.
- **Tooling & CLI Discipline**:
  - Always execute tasks using the official tooling in `./cmd/` (`team-orch`, `herdr-orch`, `agy-auto`, `sync-boilerplates`).
  - No rogue scripts in workspace root (use `.agents/tasks/active/<project_id>/scratch/` for temporary debugging/seed scripts).
- **File-Driven Communication**:
  - Inter-agent delegation and handoffs MUST use `task-handoff.md` with minimalist 1-2 line terminal triggers. Never dump walls of text directly into terminal prompts.
- **Workspace Confinement & Stirring**:
  - Agents are restricted to writing inside `target_dir` (source code), active project task directories `.agents/tasks/active/<project_id>/`, and `.drafts/`.
  - Mutating Git commands (`git add`, `git commit`, `git push`, etc.) are strictly forbidden.
- **Human-Context Parity (Cognitive Alignment)**:
  - Agents must maintain cognitive and context parity with the user at all times.
  - No speculative PRDs without interactive Discovery interviews.
  - Decisions with architectural or business trade-offs must be escalated to the user.
  - Strict preservation of Human Sovereignty over the 3 core gates: Requirements Approval, Knowledge Approval, and Final UAT Complete.

## 13. 2-Domain Isolation & Multi-Domain Switch Guardrails
- **Strict Separation**: Base Domain contains zero institutional secrets, logos, internal URLs, or organization names. Company-specific templates, approvers, internal domains, and custom boilerplates belong exclusively in gitignored Specific Domain Packs (`.agents/domains/<domain_id>/` or `~/.gemini/team-orch/domains/<domain_id>/`).
- **Just-in-Time Domain Onboarding (`/grill-me`)**: When active domain is `base` on Day-1 and the user first requests a company-bound task, follow `.agents/skills/domain-onboarding/SKILL.md` to offer a concise interactive interview (`/grill-me` / `team-orch domain init <id> --interactive`) before proceeding—or confirm continuing cleanly in generic `base` mode.
- **Context Binding**: Always verify the active domain (`team-orch domain current`) matches the project's pinned `domain_id` (`project.yaml`) to prevent cross-domain context bleed and agent hallucination. Switch domains cleanly via `team-orch domain use <domain_id|base>`.





