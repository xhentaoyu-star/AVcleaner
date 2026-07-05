# AVcleaner UI Design System

This document keeps the local desktop UI consistent across future edits.

## References

- Icons: Tabler Icons regular outline, vendored as a minimal local subset.
- Layout reference: compact Windows utility style with clear command bars, dense tables, and restrained panels.
- Implementation: Jinja2 templates, Alpine-free vanilla helpers in `avcleaner/static/app.js`, and CSS in `avcleaner/static/styles.css`.

## Visual Tokens

- Primary: teal `#0f766e`.
- Neutral text: dark slate `#111827`, secondary slate `#64748b`.
- Surface: white and soft neutral panels.
- Border: `#dbe3ea`.
- Success: green.
- Warning: amber.
- Danger/blocking: red.
- Radius: 8px for cards and controls, smaller when density matters.
- Focus: visible teal outline with offset.

## Components

- `.app-shell`: page container and main spacing.
- `.topbar`: app title, version, mode badge, and primary navigation.
- `.nav-tabs`: top-level tab navigation.
- `.workflow-card`: command area for folder, preview mode, analyze, and status.
- `.command-bar`: one-line command surface that wraps cleanly.
- `.segmented-control`: rule/AI preview selector.
- `.summary-grid` and `.summary-card`: compact metric cards with icons and counts.
- `.review-layout`: responsive two-pane review workbench.
- `.review-table`: compact visible plan table.
- `.detail-panel`: full detail/debug context for the focused row.
- `.icon-btn`, `.btn-primary`, `.btn-secondary`: consistent actions.
- `.badge`, `.badge-warning`, `.badge-danger`, `.badge-success`, `.badge-muted`: status labels.
- `.toast-stack`: local feedback messages.
- `.empty-state`: compact empty content with icon, title, and one-line explanation.

## Review Workbench Rules

- Wide screens use a two-pane grid: table/list left, detail panel right.
- The grid must use `minmax()` and `clamp()` rather than fixed percentage columns.
- Narrow screens stack the table and detail panel.
- Visible table columns stay compact: checkbox, status, original filename, editable final filename, source, review summary, actions.
- Review summary is capped to one or two lines. Full paths, trace, raw codes, LLM reason, sidecar metadata, and debug JSON belong only in `.detail-panel`.
- Focusing a row for detail is separate from selecting it for execution.

## Settings Rules

- Settings use a subnav: LLM, Rules, Import/Export, Diagnostics.
- Only one settings section should be visually dominant at a time.
- Save settings remains a primary action.
- Raw JSON stays collapsed by default.
- Secrets and raw provider payloads must never be displayed.
