# Plan: Skip OpenRouter when veraPDF says accessible

Before making any coding changes, review `pdf_checker_project/AGENTS.md` for coding preferences.

## Goal
Avoid calling OpenRouter (sync and cron) when veraPDF reports the PDF is accessible. OpenRouter should only generate user-facing suggestions for non-accessible PDFs.

## Context snapshot (Jan 30, 2026)
- veraPDF compliance is parsed via `get_verapdf_compliant()` and `get_accessibility_assessment()` in `pdf_checker_app/lib/pdf_helpers.py`.
- Synchronous processing now skips OpenRouter when `VeraPDFResult.is_accessible` is true.
- Cron summary generation now excludes documents with `verapdf_result__is_accessible=True`.
- `save_verapdf_result()` now persists `is_accessible` based on veraPDF compliance (defaults to `False` when compliance is missing).

## Relevant code locations
- `pdf_checker_app/lib/pdf_helpers.py`:
  - `get_verapdf_compliant()`
  - `get_accessibility_assessment()`
  - `save_verapdf_result()`
- `pdf_checker_app/lib/sync_processing_helpers.py`:
  - `attempt_synchronous_processing()`
  - `attempt_verapdf_sync()`
  - `attempt_openrouter_sync()`
- `scripts/process_openrouter_summaries.py`:
  - `find_pending_summaries()`
  - `process_single_summary()`
- Tests:
  - `pdf_checker_app/tests/test_sync_processing.py`
  - `pdf_checker_app/tests/test_polling_endpoints.py`

## Assumptions
- The veraPDF compliance boolean is the single source of truth for accessibility.
- An accessible PDF should **not** have OpenRouter suggestions generated (sync or cron).

## Implementation summary
1. **Persist accessibility on veraPDF save**
   - `save_verapdf_result()` now sets `is_accessible` using `get_verapdf_compliant()` and defaults to `False` when compliance is missing.

2. **Short-circuit OpenRouter in sync processing**
   - `attempt_synchronous_processing()` loads `VeraPDFResult` and skips OpenRouter when `is_accessible` is `True`.
   - Logs an `info` message when skipping.

3. **Prevent cron from selecting accessible docs**
   - `find_pending_summaries()` excludes `verapdf_result__is_accessible=True` in both selection branches.

4. **Tests added/adjusted**
   - `test_sync_processing.py` covers the sync skip behavior and OpenRouter cron selection for accessible/non-accessible docs.
   - No changes required in `test_polling_endpoints.py`.

## Implementation notes
- Prefer single-return functions and avoid nested defs (per `AGENTS.md`).
- Maintain Python 3.12 typing conventions and PEP 604 unions.
- If OpenRouter depends on accessibility status during cron processing, ensure `save_verapdf_result()` is called before cron queues summaries.

## Expected behavior after change
- Accessible PDFs: veraPDF completes, document is marked completed, OpenRouter is not called, and no summary is queued by cron.
- Not-accessible PDFs: OpenRouter behaves as today (sync attempt, cron fallback).

## Verification
- Unit tests: `uv run ./run_tests.py` (confirmed passing).
- Manual smoke: upload an accessible PDF and confirm suggestions are not generated (pending).

---

# Plan: Hide suggestions section for accessible PDFs

## Goal
When veraPDF marks the PDF as accessible, the report page should not render the “Accessibility Improvement Suggestions” section or its placeholder text.

## Context snapshot (Jan 31, 2026)
- The suggestions section is rendered via `pdf_checker_app/fragments/summary_fragment.html`, which always shows a fallback “Suggestions coming soon.” block when there is no summary.
- `report.html` always includes the summary fragment: `{% include "pdf_checker_app/fragments/summary_fragment.html" %}`.
- `view_report()` already computes `assessment` with `pdf_helpers.get_accessibility_assessment()` and passes it to the template context.
- `summary_fragment()` passes `document` and `suggestions` only; it does not pass `assessment` or accessibility status.

## Relevant code locations
- `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/report.html`
- `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/fragments/summary_fragment.html`
- `pdf_checker_app/views.py` (`view_report()` and `summary_fragment()`)

## Plan
1. **Expose accessibility state to templates**
   - Option A (preferred): pass `assessment` (or `is_accessible`) into `summary_fragment()` and the fragment context so it can decide to render nothing when accessible.
   - Option B: in `report.html`, conditionally include the summary fragment only when `assessment != 'accessible'`.

2. **Update template conditional**
   - If using Option A, wrap the summary fragment contents with a guard:
     - Only render the section when the PDF is not accessible.
   - Keep the existing status-specific blocks for pending/processing/failed/completed in the non-accessible case.

3. **Tests to add/adjust**
   - `test_polling_endpoints.py`: add a case ensuring the summary fragment returns empty (or no suggestions section) when the document is accessible.
   - If using `report.html` guard only, add a view test to ensure the report page omits the suggestions section for accessible PDFs.

## Implementation notes
- Reuse existing `assessment` values: `accessible` vs `not-accessible`.
- Keep the summary fragment behavior unchanged for non-accessible PDFs.

## Suggested verification
- Manual: load report for an accessible PDF and confirm the “Accessibility Improvement Suggestions” section is absent.
