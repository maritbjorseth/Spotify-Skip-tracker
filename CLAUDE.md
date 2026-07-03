# CLAUDE.md

## Stack

Backend: Python, Flask, PostgreSQL — `/spotify_skip_tracker`
Frontend: React, TypeScript, Tailwind, React Query, i18next — `/frontend`

## Rules

One logical change per task.
Do not refactor unrelated code.
Do not introduce new features unless explicitly requested.
Never hardcode translated strings. All user-facing text must use i18next.
Keep changes as small as possible.
Always explain the plan before modifying code.

## Verification

Never consider a task complete before verification.

Commands:
- Backend: `pytest`
- Frontend: `cd frontend && npm run build` (for typesjekk/bygg)

Whenever possible:
- run relevant tests
- verify the complete frontend → API → database flow
- explain if verification cannot be performed
