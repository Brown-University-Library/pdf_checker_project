# Plan: Incorporate Pattern Header HTML

Before changing any code, review `pdf_checker_project/AGENTS.md` for my coding-preferences.

## Context

### Current State
- External pattern header HTML file exists at: `/Users/birkin/Documents/Brown_Library/djangoProjects/pdf_checker_stuff/pattern_header_html.html`
- File contains Brown University Library header/navigation with:
  - SVG icon definitions (368 lines total)
  - Main header with Brown logo, search modal, and hamburger menu
  - Subheader with site-specific navigation
  - JavaScript for modal/menu interactions
  - External CSS dependency: `https://dlibwwwcit.services.brown.edu/common/css/bul_patterns.css`
- Base template location: `pdf_checker_project/pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/base.html`
- Current base template is minimal (31 lines) with basic structure and htmx

### Dynamic URLs in Pattern Header
The pattern header contains placeholder URLs that will need dynamic generation:
- `DYNAMIC_ABOUT_URL` (appears twice: lines 224, 342)
- `DYNAMIC_CHECK-PDF_URL` (appears twice: lines 227, 345)
- `DYNAMIC__SITE` (line 332)

**Note**: Dynamic URL generation is **out of scope** for this implementation. These placeholders will remain as-is for now.

### Coding Preferences (from AGENTS.md)
- Python 3.12 with type hints
- Use `uv` for running scripts: `uv run ./path_to_script.py` or `uv run ./manage.py COMMAND`
- Use `httpx` for HTTP calls (not requests)
- Django architecture: business logic in `lib/`, views are thin orchestrators
- Prefer single-return functions, no nested function definitions
- Triple-quoted docstrings in present tense

### Plan Notes / Corrections (from review)
- The upstream `pattern_header_html.html` begins with a `<link rel="stylesheet" ...>` tag. If we include the entire file in the `<body>`, that `<link>` will end up in the body, which is invalid HTML (most browsers tolerate it, but it is better to place stylesheet links in the `<head>`).
- If you choose the **standalone script** route, reading `PATTERN_HEADER_URL` from `.env` will require the script to load `.env` explicitly (because it won’t automatically run Django’s settings module). The **management command** path avoids this because `manage.py` imports settings, and settings already loads `.env`.
- The example code snippets use some early-returns. That’s fine for a plan, but during implementation we should try to keep closer to your “prefer single-return functions” directive where practical.

---

## Approach Options

### Option 1: Django Include Template (Recommended)

**Description**: Store the pattern header as a separate Django template partial and include it in `base.html` using `{% include %}`.

**Implementation**:
1. **File Location**: `pdf_checker_project/pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/includes/pattern_header.html`
   - Rationale: Keeps template partials organized in an `includes/` subdirectory within the app's template folder
   - Follows Django convention for reusable template fragments

2. **Handle the upstream `<link>` tag** (recommended adjustment):
   - **Preferred**: move the upstream stylesheet `<link>` line(s) into `base.html`’s `<head>` (or into a second include like `includes/pattern_header_head.html` included in the head), and keep the rest of the header markup in `includes/pattern_header.html` included in the body.
   - **Acceptable shortcut**: include the upstream file as-is at the top of `<body>` and rely on browser tolerance (simpler, but less correct HTML).

3. **Base Template Integration** (assuming we keep `pattern_header.html` as a body include):
   ```django
   {% load static %}
   <!DOCTYPE html>
   <html lang="en">
   <head>
       <meta charset="UTF-8">
       <meta name="viewport" content="width=device-width, initial-scale=1.0">
       <title>{% block title %}PDF Accessibility Checker{% endblock %}</title>
       <link rel="stylesheet" href="{% static 'pdf_checker_app/css/base.css' %}">
       {% block extra_css %}{% endblock %}
   </head>
   <body>
       {% include "pdf_checker_app/includes/pattern_header.html" %}
       
       <div class="container">
           {% if messages %}
               <div class="messages">
                   {% for message in messages %}
                       <div class="alert alert-{{ message.tags }}">
                           {{ message }}
                       </div>
                   {% endfor %}
               </div>
           {% endif %}
           
           {% block content %}{% endblock %}
       </div>
       
       <script src="https://unpkg.com/htmx.org@1.9.10"></script>
       {% block extra_js %}{% endblock %}
   </body>
   </html>
   ```

**Pros**:
- Standard Django pattern for template composition
- Easy to maintain and update
- Can be included in multiple templates if needed
- Clear separation of concerns
- No additional dependencies

**Cons**:
- Pattern header HTML is static in the template (updates require manual editing)
- No automatic refresh from external source

---

### Option 2: Template Tag with File Read

(I've removed Option-2 -- I want to use Option-1)

---

## Update Script

### Purpose
Fetch the latest pattern header HTML from a remote URL and update the local copy.

### Implementation Options

#### Option A: Standalone Script in `scripts/`

**File**: `pdf_checker_project/scripts/update_pattern_header.py`

**Structure**:
```python
#!/usr/bin/env python3
"""
Updates the pattern header HTML from a remote source.
"""

import argparse
import pathlib
import sys

import httpx


def load_dotenv_for_script() -> None:
    """
    Loads the project's .env file.

    Note: This is needed for standalone scripts because Django settings (which already load .env)
    are not imported.
    """
    import pathlib

    from dotenv import find_dotenv, load_dotenv

    ## Match config/settings.py behavior: .env is expected one level above pdf_checker_project/
    project_root: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent
    dotenv_path: pathlib.Path = project_root.parent / '.env'
    load_dotenv(find_dotenv(str(dotenv_path), raise_error_if_not_found=True), override=True)


def fetch_pattern_header(url: str) -> str:
    """
    Fetches pattern header HTML from the given URL.
    """
    response: httpx.Response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    return response.text


def save_pattern_header(content: str, target_path: pathlib.Path) -> None:
    """
    Saves pattern header HTML to the target file.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding='utf-8')


def main() -> None:
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(description='Update pattern header HTML from remote source')
    parser.add_argument('--url', help='Override URL from environment variable')
    parser.add_argument('--dry-run', action='store_true', help='Fetch but do not save')
    args = parser.parse_args()
    
    load_dotenv_for_script()

    ## Get URL from args or environment
    import os
    url: str = args.url or os.environ.get('PATTERN_HEADER_URL', '')
    if not url:
        print('Error: PATTERN_HEADER_URL not set and --url not provided', file=sys.stderr)
        sys.exit(1)
    
    ## Determine target path based on chosen approach
    ## For Option 1: pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/includes/pattern_header.html
    ## For Option 2: pdf_checker_app/lib/pattern_header.html
    project_root: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent
    target_path: pathlib.Path = project_root / 'pdf_checker_app' / 'pdf_checker_app_templates' / 'pdf_checker_app' / 'includes' / 'pattern_header.html'
    
    ## Fetch content
    print(f'Fetching pattern header from: {url}')
    content: str = fetch_pattern_header(url)
    print(f'Fetched {len(content)} characters')
    
    if args.dry_run:
        print('Dry run - not saving')
        return
    
    ## Save content
    save_pattern_header(content, target_path)
    print(f'Saved to: {target_path}')


if __name__ == '__main__':
    main()
```

**Usage**:
```bash
# Using environment variable
uv run ./scripts/update_pattern_header.py

# Override URL
uv run ./scripts/update_pattern_header.py --url https://example.com/header.html

# Dry run
uv run ./scripts/update_pattern_header.py --dry-run
```

**Environment Variable**:
Add to `.env`:
```
PATTERN_HEADER_URL=https://dlibwwwcit.services.brown.edu/common/includes/pattern_header.html
```

---

#### Option B: Django Management Command

**File**: `pdf_checker_project/pdf_checker_app/management/commands/update_pattern_header.py`

**Structure**:
```python
"""
Django management command to update pattern header HTML.
"""

import os
import pathlib

import httpx
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Updates the pattern header HTML from a remote source.
    """
    
    help = 'Updates the pattern header HTML from PATTERN_HEADER_URL'
    
    def add_arguments(self, parser) -> None:
        """
        Adds command-line arguments.
        """
        parser.add_argument(
            '--url',
            type=str,
            help='Override URL from environment variable'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch but do not save'
        )
    
    def handle(self, *args, **options) -> None:
        """
        Executes the command.
        """
        ## manage.py loads Django settings, and settings loads .env.
        ## So PATTERN_HEADER_URL should already be available here.

        ## Get URL
        url: str = options.get('url') or os.environ.get('PATTERN_HEADER_URL', '')
        if not url:
            self.stdout.write(self.style.ERROR('PATTERN_HEADER_URL not set and --url not provided'))
            return
        
        ## Determine target path
        app_dir: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent.parent
        target_path: pathlib.Path = app_dir / 'pdf_checker_app_templates' / 'pdf_checker_app' / 'includes' / 'pattern_header.html'
        
        ## Fetch content
        self.stdout.write(f'Fetching pattern header from: {url}')
        try:
            response: httpx.Response = httpx.get(url, timeout=30.0)
            response.raise_for_status()
            content: str = response.text
            self.stdout.write(f'Fetched {len(content)} characters')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch: {e}'))
            return
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Dry run - not saving'))
            return
        
        ## Save content
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Saved to: {target_path}'))
```

**Usage**:
```bash
# Using environment variable
uv run ./manage.py update_pattern_header

# Override URL
uv run ./manage.py update_pattern_header --url https://example.com/header.html

# Dry run
uv run ./manage.py update_pattern_header --dry-run
```

**Comparison**:
- **Standalone script**: Simpler, no Django dependency, can run without Django environment
- **Management command**: Integrates with Django's command system, follows Django conventions, easier to discover

---

## Recommended Approach

**Primary Recommendation**: **Option 1 (Django Include) + Option B (Management Command)**

**Rationale**:
1. **Option 1** is simpler and more maintainable for the template integration
2. **Option B** follows Django conventions and is easier to discover/document
3. The pattern header can be updated manually when needed via the management command
4. No performance overhead from file I/O on every request
5. Clear separation: templates in template directory, update logic in management command

**Alternative**: If the pattern header needs to be updated very frequently or automatically, consider **Option 2 (Template Tag)** with caching to reduce I/O overhead.

---

## Implementation Steps

### Step 1: Create Directory Structure
```bash
mkdir -p pdf_checker_project/pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/includes
mkdir -p pdf_checker_project/pdf_checker_app/management/commands
```

### Step 2: Copy Pattern Header
Copy the external file to the includes directory:
```bash
cp /Users/birkin/Documents/Brown_Library/djangoProjects/pdf_checker_stuff/pattern_header_html.html \
   pdf_checker_project/pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/includes/pattern_header.html
```

If you adopt the “move `<link>` into `<head>`” adjustment, do one of these:
- Edit the copied `pattern_header.html` and remove the first `<link>` line, then add that `<link>` to `base.html`’s `<head>`.
- Or split into two includes:
  - `includes/pattern_header_head.html` (stylesheet link)
  - `includes/pattern_header.html` (everything else)

### Step 3: Create Management Command
Create `pdf_checker_project/pdf_checker_app/management/__init__.py` (empty file)
Create `pdf_checker_project/pdf_checker_app/management/commands/__init__.py` (empty file)
Create `pdf_checker_project/pdf_checker_app/management/commands/update_pattern_header.py` (see Option B above)

### Step 4: Update Base Template
Modify `pdf_checker_project/pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/base.html` to include the pattern header (see Option 1 above)

### Step 5: Add Environment Variable
Add to `.env` (if not already present):
```
PATTERN_HEADER_URL=https://dlibwwwcit.services.brown.edu/common/includes/pattern_header.html
```

### Step 6: Test
1. Run development server: `uv run ./manage.py runserver`
2. Visit a page and verify the header appears
3. Test the update command: `uv run ./manage.py update_pattern_header --dry-run`

---

## Future Considerations

### Dynamic URL Generation
When ready to implement dynamic URLs, create a context processor:

**File**: `pdf_checker_project/pdf_checker_app/context_processors.py`
```python
from django.http import HttpRequest
from django.urls import reverse


def pattern_header_urls(request: HttpRequest) -> dict[str, str]:
    """
    Provides URL context for pattern header.
    """
    return {
        'pattern_about_url': reverse('about'),  # Adjust to actual URL name
        'pattern_check_pdf_url': reverse('check_pdf'),  # Adjust to actual URL name
        'pattern_site_url': '/',
    }
```

Then update `pattern_header.html` to use Django template variables:
- Replace `DYNAMIC_ABOUT_URL` with `{{ pattern_about_url }}`
- Replace `DYNAMIC_CHECK-PDF_URL` with `{{ pattern_check_pdf_url }}`
- Replace `DYNAMIC__SITE` with `{{ pattern_site_url }}`

And add the context processor to `settings.py`:
```python
TEMPLATES = [
    {
        # ...
        'OPTIONS': {
            'context_processors': [
                # ... existing processors ...
                'pdf_checker_app.context_processors.pattern_header_urls',
            ],
        },
    },
]
```

### Caching
If using Option 2 (template tag), consider adding Django caching:
```python
from django.core.cache import cache

@register.simple_tag
def pattern_header() -> str:
    cache_key: str = 'pattern_header_html'
    cached_content: str | None = cache.get(cache_key)
    if cached_content:
        return mark_safe(cached_content)
    
    header_path: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent / 'lib' / 'pattern_header.html'
    html_content: str = header_path.read_text(encoding='utf-8')
    cache.set(cache_key, html_content, 3600)  # Cache for 1 hour
    return mark_safe(html_content)
```

---

## Dependencies

### Required
- `httpx` (for update script/command) - likely already in dependencies

### Optional
- None for basic implementation

---

## Testing Considerations

### Manual Testing
1. Verify header appears on all pages using base template
2. Test search modal functionality (click search icon, enter text, submit)
3. Test hamburger menu (click menu icon, verify links)
4. Test responsive behavior (resize browser window)
5. Verify external CSS loads correctly

### Automated Testing
Consider adding a test for the management command:

**File**: `pdf_checker_project/pdf_checker_app/tests/test_management_commands.py`
```python
from django.core.management import call_command
from django.test import TestCase
import pathlib


class UpdatePatternHeaderTests(TestCase):
    """
    Tests for update_pattern_header management command.
    """
    
    def test_dry_run(self) -> None:
        """
        Checks that dry run does not save file.
        """
        ## This would need a mock URL or test server
        ## Placeholder for future implementation
        pass
```

---

## Notes for Future Sessions

### Key Files
- Base template: `pdf_checker_project/pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/base.html`
- Pattern header: `pdf_checker_project/pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/includes/pattern_header.html`
- Update command: `pdf_checker_project/pdf_checker_app/management/commands/update_pattern_header.py`
- Settings: `pdf_checker_project/config/settings.py`
- Environment: `.env` (in project root, one level up from `pdf_checker_project/`)

### Important Context
- The pattern header contains JavaScript that must be preserved
- External CSS dependency must remain accessible
- Dynamic URLs are placeholders for now (future work)
- Follow AGENTS.md conventions for any code changes

### Security Note
- Treat the remote `PATTERN_HEADER_URL` content as **trusted** input only. The header contains inline JavaScript, and the update script will write it into a template that is served to users. If the remote source can be tampered with, this becomes a supply-chain XSS risk.

### Common Issues
- If header doesn't appear: check template include path
- If CSS doesn't load: verify external URL is accessible
- If JavaScript doesn't work: check for conflicts with htmx or other scripts
- If management command fails: verify `httpx` is installed and `PATTERN_HEADER_URL` is set

---

## Decision Points

Before implementation, decide:
1. **Template approach**: Option 1 (include) or Option 2 (template tag)?
   - **Recommendation**: Option 1
2. **Update script**: Option A (standalone) or Option B (management command)?
   - **Recommendation**: Option B
3. **File location for pattern header**:
   - If Option 1: `pdf_checker_app_templates/pdf_checker_app/includes/pattern_header.html`
   - If Option 2: `pdf_checker_app/lib/pattern_header.html`

---

## Questions / Issues to Consider (for implementation)

1. **Where should the upstream stylesheet `<link>` live?**
   - In `<head>` (recommended) vs leaving it in the upstream fragment and including it in `<body>`.

2. **Do you want the update mechanism to write into templates or into a “source-of-truth” file?**
   - If you want a cleaner separation, we could store the downloaded upstream HTML in `pdf_checker_app/lib/pattern_header_upstream.html` and maintain a small template partial that includes/embeds it.
   - This would require either:
     - a template tag (Option 2), or
     - a build step that copies `lib/pattern_header_upstream.html` into the templates include file.

3. **Do you need a “pin” / reproducibility mechanism?**
   - Example: store `ETag`/`Last-Modified` response headers alongside the downloaded file, or log them, so you can tell what version is deployed.

4. **What environments should allow fetching remote HTML?**
   - Dev-only? Allow in prod? If prod, consider whether outbound network access is permitted.

5. **CSP considerations**
   - If you deploy with a strict Content Security Policy, inline `<script>` in the header will be blocked unless you allow `'unsafe-inline'` or use nonces/hashes.

6. **Accessibility / semantics**
   - Confirm that the skip-link targets (`#bul_pl_header_end`, etc.) don’t conflict with IDs elsewhere in your pages.
