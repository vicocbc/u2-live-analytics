---
name: pbir-report
description: How to read and edit the rpt_u2_live Power BI report in PBIR (Power BI enhanced report format) safely — folder layout, pages, visuals, theme, and the copy-then-modify workflow with Power BI Desktop checks. Use for any report page or visual work in U2 Live Analytics.
---

# PBIR report

PBIR is the default report format in Power BI Desktop and the service; the report is saved inside a Power BI
Project (`.pbip`). Each page and each visual is its own JSON file. No MCP server edits reports, so you work on
these files and push them to the workspace with the Fabric CLI.

The report is live-connected to `sm_u2_live` in the workspace (`definition.pbir` uses a connection, not a local
model path). Vini created it in Desktop as `fabric/rpt_u2_live.pbip` + `fabric/rpt_u2_live.Report/` (T-31).

## Layout

```
fabric/rpt_u2_live.Report/
  definition.pbir                 # points to the semantic model
  definition/
    report.json                   # report-level settings, theme reference
    version.json
    pages/
      pages.json                  # page order, active page
      <pageName>/
        page.json                 # displayName, size, background, filters
        visuals/
          <visualName>/visual.json  # position (x, y, z, width, height), visual type, query (fields), formatting
  StaticResources/RegisteredResources/u2-theme.json
```

Every JSON file declares a `$schema` URL. Keep it; it tells you which properties are valid. When unsure about a
property, fetch the schema it points to instead of guessing.

## Workflow

0. **Pull first:** `git pull`, and make sure *Source control* shows no uncommitted change on `rpt_u2_live` (if it does,
   Vini commits it from the portal before you start).
   If Vini has the `.pbip` open in Desktop, ask him to close it before you edit files.
1. **Copy, then modify.** Start from a visual of the same type that Vini created in Desktop (or one already in the
   folder). Copy its folder, give it a new stable name (`p01_top_songs_bar`), change position, fields and formatting.
2. **Field references** use the semantic model names exactly: `Entity` = table name, `Property` = column or measure name.
   Check them against `fabric/sm_u2_live.SemanticModel/definition/tables/*.tmdl` (or ask the Power BI modeling MCP to list them).
3. **Positions** snap to the 8 px grid from `u2-design-system`; canvas 1280 × 720.
4. **Formatting** comes from the theme first; per-visual overrides only when the theme cannot express it.
5. **Validate JSON** (parse every file you touched) before pushing.
6. **Hand over through Git:** propose the commit; when Vini asks, commit and push; he then runs
   *Source control → Update all* in the workspace. Never `fab import` the report (it conflicts with Git).
7. **Check**: Vini opens the report in the service or the `.pbip` in Desktop; if a visual shows an error, read the
   message, fix the JSON, commit and update again.
8. Never edit `.pbi/` cache files.

## Naming

Pages: `p01_overview` … `p09_about` (folder names); display names are the finding-style titles.
Visuals: `p<page>_<subject>_<type>`, lowercase, stable across edits.

## Alt text and tab order

Set `altText` on every data visual (one sentence: what it shows). Set tab order top-left to bottom-right.

## Lessons from T-32 (generated PBIR)

- Conditional-format gradients: inside `FillRule.linearGradient2`, colours are raw `{"Literal": {"Value": "'#hex'"}}` (no `expr` wrapper); with `expr` the matrix silently renders nothing.
- Field parameters in a well: put the default field in `projections` and add `"fieldParameters": [{"parameterExpr": <param column>, "index": 0, "length": 1}]` to the same role.
- Scatter X/Y must be measures (or unsummarised numeric columns); a date column with Min fails.
- **No report-level measures** (since 2026-10-26): Power BI *Publish to web* rejects a report that has any. Every
  measure a visual uses lives in `sm_u2_live`, presentation helpers too (HTML blocks, `<name> · <visual>` wrappers,
  titles, colours, rank measures), in display folder `Report\pNN <page>` (SPEC-05 "Report-support measures (Publish
  to web)"). Field refs are plain model refs (`SourceRef: {"Entity": <home table>}`, never `Schema: "extension"`);
  `definition/reportExtensions.json` stays absent. For a new page, write the measure request (name, home table, DAX
  intent, format) for the data-analyst, wait until it exists in the model, then reference it.
- Verify without Desktop: Power BI REST `ExportTo` PDF (PNG export is disabled on this tenant) and scan the PDF text for visual error messages.
