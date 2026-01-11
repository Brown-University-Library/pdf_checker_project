# Plan: Display veraPDF Raw JSON

- Review `pdf_checker_project/AGENTS.md` before and after implementing this plan.

## Goal
Provide a minimal, reliable path for users to view the raw veraPDF JSON output for a PDF, starting from the upload flow and ending at the report UI.

## Current State (Relevant Spots)
- `pdf_checker_project/pdf_checker_app/views.py:139-147` runs veraPDF and calls `pdf_helpers.parse_verapdf_output(...)`, but the parsed result is not used or stored.
- `pdf_checker_project/pdf_checker_app/models.py` already includes `VeraPDFResult.raw_json` and summary fields (`is_accessible`, counts, etc.).
- `pdf_checker_project/pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/report.html` has a placeholder “Processing complete” block with no report details.

## Architecture Plan

### 1) Ingest and persist raw JSON
- Implement `pdf_helpers.parse_verapdf_output(...)` to:
  - Parse the raw veraPDF JSON string into a Python dict.
  - Extract basic summary fields for `VeraPDFResult` (pass/fail, counts, profile, version).
  - Return both raw dict and summary to the caller.
- In `upload_pdf(...)`, after running veraPDF:
  - Save a `VeraPDFResult` row linked to the `PDFDocument`, storing `raw_json` and summary fields.
  - Set `processing_status` to `completed` on success; on parse/analysis errors, set `failed` and capture `processing_error`.
- Ensure raw JSON is stored exactly as returned by veraPDF (no lossy transformations).
- DEVELOPER COMMENTS:
  - add code to persist the raw veraPDF JSON to the `VeraPDFResult` model.
    - this seems like the uuid-key of the document should be passed to the relevant helper code performing the persist.
  - ignore extracting additional info for the VeraPDFResult model for now.
  - return only the raw JSON to the caller.

### 2) Expose raw JSON via a report endpoint
- Extend `view_report(...)` to load `document.verapdf_result` (if it exists).
- Decide on access pattern:
  - ~~Option A (simple): add `?format=json` to `view_report` to return `raw_json` as `application/json`.~~
  - ~~Option B (clean separation): add a dedicated URL, e.g., `/report/<pk>/raw/`, returning the JSON.~~
- Keep this view read-only and avoid any data mutation.
- DEVELOPER COMMENTS:
  - for now, an Option C: 
    - conceptually, the url should be `/report/<pdf_uuid>/`.
    - I want the result to have a template that shows a brief summary stating "Summary coming soon.", followed by a section that shows a `<details>` block with a `<pre>` showing pretty-printed JSON for on-page viewing.

### 3) Add a UI block for raw JSON (minimal but usable)
- Update `report.html` to include a “Raw veraPDF JSON” section when `document.processing_status == 'completed'`.
- Use a `<details>` block with a `<pre>` showing pretty-printed JSON for on-page viewing.
- ~~Provide a “View as JSON” link to the raw JSON endpoint/query option for easy copy/download.~~

### 4) Tests for the new behavior
- Add Django tests for:
  - Successful upload path creates a `VeraPDFResult` with `raw_json`.
  - `view_report` includes the raw JSON link/section when results exist.
  - Raw JSON endpoint/query returns valid JSON and correct content type.
- Include a failure-path test where veraPDF output is invalid JSON and processing status becomes `failed`.
- DEVELOPER COMMENTS:
  - I do want tests, but not yet.

~~## Open Decisions (Make Once, Early)~~
- **Which endpoint style to prefer**: query (`?format=json`) vs dedicated URL.
- **Pretty-print formatting**: indent level and key ordering for display (not storage).
- **Visibility rules**: if raw JSON should be available to all users or only admins (if permissions are added later).
- DEVELOPER COMMENTS:
  - decisions made above.

## Milestones (Suggested Order)
~~1) Implement parser and persistence (`pdf_helpers.parse_verapdf_output`, `upload_pdf` write to `VeraPDFResult`).~~
~~2) Add raw JSON endpoint/query in `view_report`.~~
~~3) Update `report.html` to show raw JSON section and link.~~
~~4) Add tests for storage and display.~~
DEVELOPER COMMENTS:
  - 1) implement persistence.
  - 2) for now, have the parser code just return the raw JSON to the caller.
  - 3) implement the view_report() function to load the raw JSON from the VeraPDFResult model.

---
