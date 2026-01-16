# Polling Architecture Plan (veraPDF + OpenRouter summary)

## Goal

Update the webapp so that:

- Uploading a PDF returns a user response quickly (no long-running veraPDF or LLM call inside the upload request/response).
- The report page polls for:
  - veraPDF processing completion + results
  - (future) OpenRouter “human-readable” summary completion + results

## Explicit constraints

- No Celery/RQ/queue system for now.
- Cron will trigger one or more scripts within the repo to do background work.
- **Do not change the database schema at all.**

## Current behavior (baseline)

- `views.upload_pdf()`:
  - Creates/uses a `PDFDocument` row.
  - Saves the uploaded PDF to disk via `pdf_helpers.save_pdf_file()`.
  - Runs veraPDF synchronously inside the request (`pdf_helpers.run_verapdf()`), parses JSON, stores the result with `pdf_helpers.save_verapdf_result()`.
  - Sets `processing_status='completed'` and redirects to `pdf_report_url`.
- `views.view_report()` renders `report.html` and, if `processing_status == 'completed'`, pulls `VeraPDFResult.raw_json` from the DB and shows it.

This makes the upload request slow (veraPDF is seconds; future OpenRouter is 10–30s).

## Proposed architecture (high level)

### Split the work into three independent concerns

1. **Fast web request path**
   - Upload endpoint should only:
     - validate input
     - compute checksum
     - create/update `PDFDocument`
     - save the PDF to disk
     - set `processing_status` to `pending` (or `processing` if you want “immediate pickup”) and redirect to the report page

2. **Background veraPDF processing (cron-driven)**
   - Cron runs a script that:
     - finds `PDFDocument` rows in `pending` (or `processing`, if using recovery) state
     - marks a document as `processing` (atomically, so multiple cron invocations don’t double-process)
     - runs veraPDF against the on-disk PDF
     - persists results to `VeraPDFResult` (existing table)
     - marks the document `completed` or `failed`

3. **Background LLM summary generation (cron-driven; future)**
   - Cron runs a script that:
     - finds documents whose veraPDF processing is complete
     - checks whether a summary exists
     - if missing, calls OpenRouter and writes the summary somewhere **not in the DB**

### Report page becomes a “live” UI via polling

- The report page continues to render server-side as it does today.
- It also includes a small JS poller that periodically fetches JSON endpoints to update the UI without reload.

## Data sources for polling (no DB changes)

### veraPDF status + results

- Use existing fields:
  - `PDFDocument.processing_status` and `processing_error`
  - `VeraPDFResult` (OneToOne) for the raw JSON

### Summary status + results (no DB schema changes)

Because we cannot add a `summary` column/table right now:

- Store summary output as a **sidecar file** on disk, keyed by the document.

Recommendation:

- Put summary artifacts under a deterministic directory, e.g.:
  - `project_settings.PDF_UPLOAD_PATH / "summaries" / f"{doc.id}.json"`

And store a JSON payload like:

- `{"status": "pending"|"completed"|"failed", "summary_text": "...", "error": "...", "created_at": "...", "model": "..."}`

This gives:

- **Polling signal**: file exists and `status` != pending.
- **No DB changes**.
- **Idempotency**: if the file exists with `completed`, the cron job skips.

(Alternative: store a `.txt` file and treat presence as completion; JSON is more extensible.)

## Web endpoints to add (polling)

Add lightweight JSON endpoints (Django views) that the report page can poll.

Suggested endpoints:

- `GET /pdf/report/<uuid:pk>/status.json`
  - returns document status and which artifacts exist
  - example response:
    - `{"processing_status": "pending"|"processing"|"completed"|"failed", "processing_error": null|"...", "has_verapdf": true|false, "has_summary": true|false}`

- `GET /pdf/report/<uuid:pk>/verapdf.json`
  - returns veraPDF raw JSON if available
  - if not available yet, return `202 Accepted` + `{ "ready": false }` (or `200` with `ready: false`; choose one convention and keep consistent)

- `GET /pdf/report/<uuid:pk>/summary.json`
  - returns summary data if available
  - if not available, same pending convention as above

Notes:

- Keep responses small where possible; veraPDF raw JSON can be huge.
  - If you need to keep the first iteration simple, return the raw JSON (it’s already being displayed), but long-term consider a “summary-of-the-json” endpoint that returns counts and top failures.
- Set headers to avoid caching issues while polling (eg `Cache-Control: no-store`).

## Frontend polling behavior (report page)

In `report.html`:

- Add a JS poll loop using `fetch()`.
- Poll cadence:
  - Start at ~1–2 seconds for the first 10–15 seconds
  - Then back off to ~5 seconds
  - Stop polling after:
    - both veraPDF and summary are complete OR
    - status is `failed` OR
    - a max time limit (ex: 2 minutes) with an on-page message telling the user to refresh later

UI states:

- Show a “processing” message while waiting.
- When `has_verapdf` becomes true:
  - either inject the JSON into the existing `<pre>` element
  - or reload just the JSON area
- When `has_summary` becomes true:
  - render summary text

Implementation detail:

- To keep the first iteration low-risk, the poller can just call `/status.json` and, once it reports `has_verapdf`, do a second call to `/verapdf.json`.

## Cron-driven scripts (no queue)

Create repo scripts runnable via `uv run`.

### Script 1: process veraPDF jobs

- Location suggestion:
  - `pdf_checker_project/scripts/process_verapdf_jobs.py`

Responsibilities:

- `django.setup()` and use ORM.
- Find jobs:
  - `PDFDocument.objects.filter(processing_status__in=['pending', 'processing'])`
- Concurrency safety (recommended):
  - Use `transaction.atomic()` + `select_for_update(skip_locked=True)`
  - Grab a small batch (ex: 1–5) to avoid long transactions.
  - Immediately set `processing_status='processing'` before running veraPDF.
- For each job:
  - resolve the PDF path based on `file_checksum` (consistent with `save_pdf_file()` naming)
  - run veraPDF
  - parse JSON
  - upsert `VeraPDFResult` via existing helper
  - set document `completed` on success; `failed` on exception

Recovery:

- If a job is stuck in `processing` (server crash), decide a policy:
  - simplest: reprocess anything in `processing` older than N minutes
  - since we have no DB timestamp for “processing started”, use one of:
    - treat `processing` same as `pending` (acceptable early on)
    - or add a log-only policy and reset manually

### Script 2: generate OpenRouter summaries (future)

- Location suggestion:
  - `pdf_checker_project/scripts/generate_summaries.py`

Responsibilities:

- Find completed docs:
  - `PDFDocument.objects.filter(processing_status='completed')`
- Only act on docs that also have a `VeraPDFResult`.
- Determine if summary already exists by checking for the sidecar file.
- If missing:
  - call OpenRouter
  - write summary JSON file (with `status`, `summary_text`, `error`, `model`, timestamps)

Failure handling:

- On OpenRouter failure, write `status='failed'` + error to the sidecar file so polling can show a stable error message.

## Upload flow changes (web request path)

Update `views.upload_pdf()` so it does **not** run veraPDF.

Desired behavior:

- For a new checksum:
  - create doc, save PDF, set status `pending`, redirect to report.
- For an existing checksum:
  - if `completed`: redirect immediately to report (already supported)
  - if `pending`/`processing`: redirect to report and let polling handle completion
  - if `failed`: decide whether to re-queue on re-upload or keep failed until manually reset

## URL routing

- Extend `config/urls.py` with the new JSON endpoints.
- Keep the existing `pdf_report_url` page endpoint intact.

## Testing plan

Add/adjust Django tests:

- `GET pdf_report_url` still returns 200 for valid UUID.
- New tests for:
  - `GET /status.json` returns expected JSON for each status
  - `GET /verapdf.json` returns pending payload when no `VeraPDFResult` exists
  - `GET /verapdf.json` returns JSON when it exists
  - `GET /summary.json` returns pending payload when sidecar file missing

For cron scripts:

- Unit-ish tests (if feasible) for “job selection” logic and for the sidecar-file conventions.
- (Optional) smoke test that a doc transitions `pending -> completed` when helper functions are stubbed.

## Operational notes

- Cron frequency:
  - veraPDF job runner: every minute (or more frequently if desired)
  - summary generator: every 1–5 minutes (depending on cost / rate limits)

- Ensure cron environment has:
  - correct Python/uv environment
  - `DJANGO_SETTINGS_MODULE` configured
  - `VERAPDF_PATH` configured
  - OpenRouter API key configured (future)

- Logging:
  - cron scripts should log per-document start/end + exceptions.

## Suggested implementation sequence (low-risk incremental)

1. Add JSON status endpoint + JS polling that only updates the “status” display (no veraPDF JSON fetch yet).
2. Change upload to mark `pending` and return immediately.
3. Add cron script to process veraPDF jobs and update DB.
4. Extend polling to fetch and render veraPDF JSON when ready.
5. Add summary sidecar-file convention + `/summary.json` endpoint returning pending.
6. Implement OpenRouter call in cron summary script (future).

## Open questions / decisions to make (can be decided during implementation)

- Polling response conventions:
  - Use `200` always with `{ready: false}` vs using `202 Accepted`.
- Summary storage:
  - Sidecar JSON file location under `PDF_UPLOAD_PATH` vs a separate `RESULTS_PATH`.
- Security / access:
  - Anyone with the UUID can access the report endpoints; is that acceptable for your environment?
- veraPDF JSON size:
  - Keep returning the full JSON (simple) vs return a compact subset for UI.
