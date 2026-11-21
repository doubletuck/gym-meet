# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture
Gym Meet is an application for managing mens and womens elite artistic gymnastics competition events, participants and results. 

### Backend
The backend service is in the `backend` directory.

The backend service is a Spring Boot 4 and Java 25 application. The data is stored in a Postgres database and versioned using Flyway.

### Frontend
The frontend user interface is in the `frontend` directory.

The frontend user interface is a React, TypeScript and Vite application, built with React Router 8 (as a single-page app for now), TanStack Query and Tailwind CSS. It reads results from the backend's public read API (`/api/**`); its types are generated from the backend's OpenAPI spec (`npm run api:types`). See `frontend/README.md`.

## Tests

- When adding a new capability, relevant tests should be added.
- When modifying capability, impacted tests should be updated accordingly.
- All test must run successfully.

### Backend Testing
Tests are found in `backend/src/test/java/`. Run them with `mvn -q test` from `backend/`.

### Frontend Testing
Tests sit beside the code they test (`*.test.ts(x)` under `frontend/app/`). Run them with `npm test` from `frontend/`, and `npm run typecheck` to check types.

## Competition results data

Results PDFs are parsed into import CSVs under `data/<year>/<event>/`, which the importer (`doubletuck.meet.importer`, see `backend/docs/import-process.md`) loads into the database. Use the `parse-results` skill (`.claude/skills/parse-results/`) for any new results document. Parsers live in `backend/tools/results-parsing/` (one per meet, sharing `common.py`).

## Documentation

If changes to the code changes, then any documentation that refers to the changed code should be updated so that the documentation is accurate.

| document | description |
| --- | --- |
| backend/docs/data-model.md | The class structures that form and contain the data. |
| backend/docs/import-file-model.md | The columns and descriptions of the CSV files (SCORES, JUDGES, PARTICIPANTS, SUMMARY, EVENT) used to import competition data. |
| backend/docs/import-process.md | How the importer loads those CSV files into the database: running it, session and athlete matching rules, and the checks it reports. |
| backend/docs/instructions-results-parsing.md | How results PDFs are turned into those CSV files: techniques, required checks, conventions, and notes per source format. |
| backend/docs/development-setup.md | Setting up the local development environment. |
| backend/docs/development-run.md | Running the backend locally, and importing results. |
| backend/docs/api/api-event.md | The Event API: listing events, an event's sessions, and creating or changing events. |
| backend/docs/api/api-session.md | The Session API: a session's results as published. |
| backend/docs/api/api-athlete.md | The Athlete API: athlete search and an athlete's career. |
| frontend/README.md | Running, testing and the layout of the front end. |


