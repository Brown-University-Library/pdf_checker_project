# PLAN: CSS tweaks (info.css scope + naming)

## Current state (as of now)

### Where the standalone-page stylesheet is used

- Template: `pdf_checker_app/pdf_checker_app_templates/info.html`
- Loads: `{% static 'pdf_checker_app/css/info.css' %}`
- View: `pdf_checker_app.views.info()`
- URL: `/info/` (name: `info_url`)
- Root `/` redirects to `/info/` via `views.root()`

### Why a generic stylesheet name is potentially confusing

- A generic stylesheet filename is easy to misuse.
- The stylesheet currently appears to be **only** for the standalone `info.html` page.
- It contains selectors like `.container` that are *not* compatible with the base-template UI (`base.css` also defines `.container`, but with different intent/layout).


## Recommendation: keep the stylesheet name scoped to the page

### Option A (recommended): `info.css`

- Pros:
  - Immediately communicates that it’s for the `/info/` page.
  - Minimizes accidental reuse in other pages.
- Cons:
  - Requires updating any references (currently only `info.html`, but verify).

## Implementation steps

1. Ensure `info.html` references `info.css`:
   - `<link rel="stylesheet" href="{% static 'pdf_checker_app/css/info.css' %}">`
2. Verify locally:
   - Load `/info/` and confirm layout/typography.
   - Load `/pdf_uploader/` and `/pdf/report/<uuid>/` and confirm no regressions.
3. Optional safety check:
   - If you run Django `collectstatic` in your deploy workflow, verify no legacy stylesheet references remain.


## Comments to add to the top of the stylesheet

### More explicit (recommended for reviewers)

- `/*
-  File: info.css
-
-  Purpose
-  - Styles the standalone /info/ page rendered by pdf_checker_app.views.info() using template info.html.
-
-  Important
-  - This file intentionally defines .container for the standalone page layout.
-  - Base-template pages use base.css, which also defines .container with different layout rules.
-  - Do not load both files on the same page unless you also rename/scope selectors.
- */`


## Additional cleanup work

- Rename `.container` in `info.html`/`info.css` to something more specific (e.g., `.info-container`) to eliminate accidental collisions.
