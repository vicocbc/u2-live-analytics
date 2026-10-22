# SPEC-08 · Portfolio packaging

Owner: data-analyst (findings, write-up) · dashboard-designer (visual assets) · vini (final review, publishing)

## README.md structure

1. One-line pitch and a hero screenshot (Overview page).
2. Three findings, each one sentence with a number and a small screenshot.
3. Architecture diagram (Mermaid from `docs/architecture.md`) and stack: Fabric Lakehouse, PySpark, Direct Lake, Power BI (PBIP/TMDL/PBIR), GitHub Actions.
4. Data model diagram (star schema).
5. Engineering decisions worth discussing in an interview: snapshot vs. incremental Bronze, song mapping strategy, deterministic surrogate keys, no fact-to-fact relationship, secrets handling.
6. Data quality: checks, known limitations with numbers (unrecorded setlists, unmapped songs).
7. How to reproduce: prerequisites, API keys, steps, expected run time.
8. Credits: setlist.fm and MusicBrainz (with links and licence/terms notes), every image from
   `docs/design/images/credits.csv` (title, author, licence, link), no affiliation with U2.
9. Built with Claude Code: how the agents, skills and specs were used (short; links to `.claude/`).

## Other assets

- `docs/img/`: page screenshots (PNG, 1280 px wide), one GIF of a drill-through (optional).
- `docs/data-dictionary.md`: every Gold column and every measure with description (generated from specs + TMDL descriptions).
- Short write-up (LinkedIn/Medium draft in `docs/post.md`, in Portuguese and English) built around the three findings.

## Acceptance criteria

- A reviewer understands what the project does and sees the report within the first screen of the README.
- No secrets, data extracts or copyrighted images in the repo; every image is freely licensed and credited.
- All links in the README work.
