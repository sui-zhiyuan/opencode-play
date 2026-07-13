# AGENTS.md — opencode-play

## What this repo is

A knowledge workspace for technical Q&A on public-domain computer science topics (e.g., CPU cache internals, Linux io-uring, etc.). There is **no application code** here. Files may exist as rough notes but should not be treated as a codebase.

## Rules for agents

### Do NOT scan local files for answers
Questions in this workspace are about public CS knowledge. Local files are notes/scratch, not source code. Searching them is wasted effort.

### Answer from knowledge first; web-search second
- If you know the answer confidently, answer directly.
- If unsure, use `websearch_web_search_exa` or `webfetch` — do NOT use explore/librarian agents (those search codebases, not the web).
- Do NOT consult Oracle/Metis/Momus for factual CS questions — those are for architecture/debugging/planning of actual codebases.

### Keep it concise
No need for project-structure exploration, codebase assessment, or implementation phases. This is a Q&A workspace.

## Commands
- None. There is no build, test, lint, or deploy.
