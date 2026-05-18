# AGENTS.md

## Codex project guidance

- This repository uses the DevolaFlow skill installed at `.agents/skills/devola-flow/`.
- For multi-step engineering tasks, feature work, refactors, bug fixes, migrations, audits, documentation work, and performance work, consider invoking the `$devola-flow` skill.
- Prefer structured workflows: detect task type, plan, implement, review, test, refine, and report.
- Before making risky or broad changes, summarize the intended workflow and affected files.
- After code changes, run the most relevant available tests or explain why tests could not be run.
