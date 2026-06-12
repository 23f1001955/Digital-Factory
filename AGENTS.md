# CLAUDE.md — Digital Product Factory

Persistent instructions for any AI agent (Claude Code or similar) working in this repo. Read `PRD.md` first — it is the source of truth for architecture and scope. This file governs *how* to work, not *what* to build.

## Project Identity

- A **local CLI pipeline**, not a web app. Never add a server, frontend framework, auth system, or database server unless `PRD.md` is updated first to request it.
- Architecture is **DOE**: Directive (`cli/wizard.py`) → Orchestration (`orchestrator/`) → Execution (`agents/`). Don't blur these layers — agents never prompt the user; the wizard never calls an LLM; the orchestrator never contains product-specific logic (that lives in schemas + agents).
- The system is **schema-driven**. Product structure (which components exist, their dependencies, output paths) lives in `/schemas/*.json`, validated by Pydantic models in `orchestrator/models.py`. If you find yourself writing `if product_type == "research_pack":` in the orchestrator, stop — that branch belongs in a schema file.

## Hard Constraints

1. **No hardcoded secrets.** All keys (`ANTHROPIC_API_KEY`, `NOTION_API_KEY`, `NOTION_PARENT_PAGE_ID`) come from `.env`, loaded via `python-dotenv`. Always update `.env.example` when adding a new variable.
2. **Notion cannot create workspaces.** Any Notion code creates pages/databases as children of `NOTION_PARENT_PAGE_ID`. Never write code that assumes a "create workspace" endpoint exists — it doesn't.
3. **Renderer selection must degrade gracefully.** `renderers/antigravity_renderer.py`'s availability probe must never raise an unhandled exception — wrap it in try/except and return `False` on any uncertainty. Playwright is the guaranteed fallback and must be installable on demand (`python -m playwright install chromium`), not as a default `pip install` dependency for users who never render PDFs.
4. **One failed component ≠ one failed run.** The orchestrator catches per-agent exceptions, records `status: "failed"` + error message in `job_state.json` for that component, and continues with any components whose dependencies are still satisfied. Only abort the whole run if *all* remaining components depend (directly or transitively) on the failed one.
5. **Resumability.** Every agent must be idempotent given the same inputs — re-running a `"done"` component should be skippable. `job_state.json` is the single source of truth for what's been completed.
6. **No silent scope expansion.** If a task seems to require a new product type, new top-level dependency, or a new external service, stop and flag it rather than building it — `PRD.md` Section 11 (MVP definition) is the scope boundary for Phase 1.

## Coding Conventions

- Python 3.11+, type hints everywhere, `pydantic` v2 for all config/schema/state models.
- Agents are plain functions with a consistent signature:
  ```python
  def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
      ...
  ```
  `context` carries outputs of already-completed dependencies (file paths + loaded data as needed). `AgentResult` includes `status`, `output_path`, and `error: str | None`.
- Registry pattern: new agent = add one entry to `agents/registry.py`'s `AGENT_REGISTRY`. Never add new `if/elif` chains to the orchestrator for dispatch.
- Formatting: `black` + `ruff`. Run both before considering a task done.
- Tests: every new agent gets a `tests/test_agents.py` case with mocked external calls (LLM, Notion, Playwright) — no test should make a real network call.
- Logging: structured (`logging` module, JSON or key=value formatter), no `print()` outside `cli/wizard.py`. Never log API keys or full LLM prompts/responses at INFO level (DEBUG only, and redact keys regardless).

## Templates / Design System

- Templates live under `/templates/{product_type}/*.html.j2` + shared CSS in `/templates/shared/`.
- A template is not "done" when it renders without error — it's done when it matches the visual bar described in `PRD.md` §13 (named reference review). If asked to build a template, ask for or assume a specific visual reference (e.g., "Stripe-style report cover") rather than producing a default-looking HTML→PDF dump.
- Don't introduce a second CSS approach (e.g., Tailwind) without updating `PRD.md` — v1 uses plain CSS in `templates/shared/base.css` for simplicity and Playwright-render reliability.

## Workflow for Ambiguity

- If the wizard's question set in `PRD.md` §6 doesn't cover something a new feature needs, **add a wizard question** (Directive layer) rather than hardcoding a default or guessing — this system is explicitly designed to ask the user up front.
- If a schema file needs a new field, update the corresponding Pydantic model in the same change, and update `PRD.md` §5 if the field is structural (not just product-specific data).

## How to Use the Other Files

- `prompts/01_planning_prompt.md` — feed to a planning-mode agent to expand `PRD.md` into a full task-level blueprint before implementation starts (or before starting a new phase).
- `prompts/02_implementation_prompt.md` — feed to a build-mode agent along with the blueprint output to generate/extend the codebase.
- `prompts/03_review_prompt.md` — feed to an audit-mode agent against the current codebase + `PRD.md` before considering a phase complete.

Each prompt should be run with the **current** `PRD.md` and the current codebase state attached — they are not one-shot, they're meant to be re-run per phase.
