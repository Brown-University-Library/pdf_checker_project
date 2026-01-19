# Implementation Progress Tracker

## Objective
Implement synchronous PDF processing with timeout fallback as specified in PLAN__live_plus_poll.md

## Session Context
- **Started**: 2026-01-19 06:19 EST
- **Plan Source**: `PLAN__live_plus_poll.md`
- **Coding Directives**: `AGENTS.md` (Python 3.12, uv, httpx, type hints, no nested functions)

## Completed Steps

### 1. Database Migration ✓
- **File**: `pdf_checker_app/models.py`
- **Change**: Added `processing_started_at = models.DateTimeField(blank=True, null=True)` to PDFDocument model
- **Migration**: Created and applied `0005_add_processing_started_at.py`
- **Purpose**: Track when processing began to prevent double-processing between sync attempts and cron jobs

### 2. Add Timeout Settings ✓
- **File**: `config/settings.py`
- **Added**:
  - `VERAPDF_SYNC_TIMEOUT_SECONDS: float = 30.0`
  - `OPENROUTER_SYNC_TIMEOUT_SECONDS: float = 30.0`
  - `RECOVER_STUCK_PROCESSING_AFTER_SECONDS: int = 600`

### 3. Update pdf_helpers.py ✓
- **File**: `pdf_checker_app/lib/pdf_helpers.py`
- **Changes**:
  - Added `VeraPDFTimeoutError` exception class
  - Modified `run_verapdf()` signature to accept `timeout_seconds: float | None = None`
  - Added timeout handling with `subprocess.TimeoutExpired` → `VeraPDFTimeoutError`

### 4. Create openrouter_helpers.py ✓
- **File**: `pdf_checker_app/lib/openrouter_helpers.py` (NEW)
- **Extracted**:
  - `PROMPT` template
  - `get_api_key()`, `get_model()`
  - `filter_down_failure_checks()` and recursive pruning logic
  - `build_prompt()`
  - `call_openrouter()` with timeout parameter
  - `parse_openrouter_response()`
  - `persist_openrouter_summary()`

### 5. Update process_verapdf_jobs.py ✓
- **File**: `scripts/process_verapdf_jobs.py`
- **Changes**:
  - Modified `find_pending_jobs()` to implement stuck processing recovery
  - Now selects `pending` jobs + `processing` jobs older than threshold
  - Sets `processing_started_at=now()` when starting processing

### 6. Update process_openrouter_summaries.py ✓
- **File**: `scripts/process_openrouter_summaries.py`
- **Changes**:
  - Refactored to use `openrouter_helpers` module
  - Removed duplicate code (prompt, API call, parsing, persistence)
  - Updated `process_single_summary()` to accept `model` parameter

### 7. Update views.upload_pdf() ✓
- **File**: `pdf_checker_app/views.py`
- **Changes**:
  - Added `attempt_synchronous_processing()` orchestrator function
  - Added `attempt_verapdf_sync()` with timeout handling
  - Added `attempt_openrouter_sync()` with timeout handling
  - Updated `upload_pdf()` to call sync processing before redirect
  - Proper fallback: timeout → `pending` status for cron pickup
  - Creates OpenRouterSummary with `processing` status BEFORE API call to prevent race conditions

### 8. Add Tests ✓
- **File**: `pdf_checker_app/tests/test_sync_processing.py` (NEW)
- **Test Coverage**:
  - `SyncVeraPDFProcessingTest`: Success, timeout fallback, error handling
  - `SyncOpenRouterProcessingTest`: Success, timeout fallback, error handling, credential checks
  - `CronSelectionLogicTest`: Pending selection, fresh processing skip, stuck processing recovery
  - `FullSyncProcessingTest`: End-to-end success path, timeout stops cascade
- **Result**: All 34 tests passing

### 9. Run Tests ✓
- **Command**: `uv run ./run_tests.py`
- **Result**: ✅ All 34 tests passed in 0.079s

### 10. Refactor views.py ✓
- **File**: `pdf_checker_app/lib/sync_processing_helpers.py` (NEW)
- **Changes**:
  - Moved `attempt_synchronous_processing()`, `attempt_verapdf_sync()`, and `attempt_openrouter_sync()` from views.py to new lib module
  - Updated `pdf_checker_app/views.py` to import and call from `sync_processing_helpers`
  - Updated `pdf_checker_app/tests/test_sync_processing.py` to import from new module location
  - Cleaned up unused imports in views.py
- **Result**: views.py now contains only URL endpoint handlers, delegating business logic to lib modules
- **Tests**: ✅ All 34 tests still passing

### 11. Add Cron Timeout Settings ✓
- **File**: `config/settings.py`
- **Changes**:
  - Added `VERAPDF_CRON_TIMEOUT_SECONDS: float = 60.0`
  - Added `OPENROUTER_CRON_TIMEOUT_SECONDS: float = 60.0`
  - Updated comments to clarify sync (30s) vs cron (60s) timeouts
- **File**: `scripts/process_verapdf_jobs.py`
- **Changes**:
  - Updated to use `project_settings.VERAPDF_CRON_TIMEOUT_SECONDS` instead of no timeout
- **File**: `scripts/process_openrouter_summaries.py`
- **Changes**:
  - Removed hardcoded `OPENROUTER_TIMEOUT = 60.0` constant
  - Added `from django.conf import settings as project_settings` import
  - Updated to use `project_settings.OPENROUTER_CRON_TIMEOUT_SECONDS`
- **Result**: Cron jobs now use longer 60-second timeouts, more patient than web requests (30s)
- **Tests**: ✅ All 34 tests still passing

## Implementation Complete ✅

All planned features have been successfully implemented and tested.
Views.py now follows the architectural pattern of containing only URL endpoint handlers.
Timeout settings are now centralized in settings.py with separate values for sync (web) and cron (background) processing.

## Key Design Decisions

- **Stuck Processing Threshold**: 10 minutes (600 seconds)
- **Sync Timeouts**: 30 seconds each for veraPDF and OpenRouter
- **Cron Selection Logic**: Skip `processing` docs with fresh `processing_started_at`, include old ones for recovery
- **OpenRouter Summary Creation**: Create with `status='processing'` BEFORE calling API to prevent race conditions

## Files Modified So Far
1. `pdf_checker_app/models.py` - Added `processing_started_at` field

## Files To Be Modified
1. `config/settings.py` - Add timeout constants
2. `pdf_checker_app/lib/pdf_helpers.py` - Add timeout support
3. `pdf_checker_app/lib/openrouter_helpers.py` - NEW FILE (extract logic)
4. `scripts/process_verapdf_jobs.py` - Add recovery logic
5. `scripts/process_openrouter_summaries.py` - Use extracted helpers
6. `pdf_checker_app/views.py` - Add sync attempt logic
7. Test files - Add new test cases
