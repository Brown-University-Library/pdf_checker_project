# PDF Upload Form Implementation Plan

## Overview

This document outlines the implementation plan for the initial PDF upload form feature, focusing on a simple web interface (no API) that performs basic PDF accessibility checking using veraPDF.

## Scope

### What's Included (Initial Implementation)
- Web form for PDF upload
- PDF file validation
- Checksum generation and storage
- veraPDF accessibility checking
- JSON result storage in SQLite
- Simple pass/fail report display
- List of accessibility issues found

### What's NOT Included (Future Iterations)
- API endpoints
- LLM processing
- Queue/worker architecture
- WebSockets or real-time updates
- Batch processing
- Authentication/authorization
- Advanced caching strategies

## Technical Components

### 1. Database Models

#### PDFDocument Model
```python
# pdf_checker_app/models.py
class PDFDocument(models.Model):
    """
    Stores uploaded PDF document metadata.
    """
    # File identification
    original_filename = models.CharField(max_length=255)
    file_checksum = models.CharField(max_length=64, unique=True, db_index=True)  # SHA-256
    file_size = models.BigIntegerField()  # bytes
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Status tracking
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    processing_error = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['file_checksum']),
            models.Index(fields=['-uploaded_at']),
        ]
```

#### VeraPDFResult Model
```python
class VeraPDFResult(models.Model):
    """
    Stores veraPDF analysis results.
    """
    # Relationship
    pdf_document = models.OneToOneField(
        PDFDocument, 
        on_delete=models.CASCADE,
        related_name='verapdf_result'
    )
    
    # veraPDF output
    raw_json = models.JSONField()  # Complete veraPDF JSON output
    
    # Parsed results
    is_accessible = models.BooleanField()  # Pass/fail status
    validation_profile = models.CharField(max_length=50)  # e.g., "PDF/UA-1"
    
    # Processing metadata
    analyzed_at = models.DateTimeField(auto_now_add=True)
    verapdf_version = models.CharField(max_length=20)
    
    # Summary data
    total_checks = models.IntegerField(default=0)
    failed_checks = models.IntegerField(default=0)
    passed_checks = models.IntegerField(default=0)
```

#### AccessibilityIssue Model
```python
class AccessibilityIssue(models.Model):
    """
    Individual accessibility issues found by veraPDF.
    """
    # Relationship
    verapdf_result = models.ForeignKey(
        VeraPDFResult,
        on_delete=models.CASCADE,
        related_name='issues'
    )
    
    # Issue details
    rule_id = models.CharField(max_length=50)  # e.g., "7.1-1"
    severity = models.CharField(
        max_length=20,
        choices=[
            ('error', 'Error'),
            ('warning', 'Warning'),
            ('info', 'Info'),
        ]
    )
    description = models.TextField()
    location = models.CharField(max_length=255, blank=True)  # Page/element reference
    
    # Occurrence tracking
    occurrence_count = models.IntegerField(default=1)
    
    class Meta:
        ordering = ['severity', 'rule_id']
```

### 2. Forms

#### PDF Upload Form
```python
# pdf_checker_app/forms.py
from django import forms
from django.core.exceptions import ValidationError
import magic

class PDFUploadForm(forms.Form):
    """
    Form for uploading PDF files.
    """
    pdf_file = forms.FileField(
        label='Select PDF file',
        help_text='Maximum file size: 50MB',
        widget=forms.FileInput(attrs={
            'accept': '.pdf,application/pdf',
            'class': 'form-control',
        })
    )
    
    def clean_pdf_file(self) -> UploadedFile:
        """
        Validates that the uploaded file is a PDF.
        """
        file = self.cleaned_data['pdf_file']
        
        # Check file size (50MB limit)
        if file.size > 50 * 1024 * 1024:
            raise ValidationError('File size exceeds 50MB limit.')
        
        # Check MIME type using python-magic
        file_type = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)  # Reset file pointer
        
        if file_type != 'application/pdf':
            raise ValidationError('File must be a PDF document.')
        
        return file
```

### 3. Views

#### Upload View
```python
# pdf_checker_app/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
import hashlib
from .forms import PDFUploadForm
from .models import PDFDocument, VeraPDFResult
from .lib.verapdf_processor import VeraPDFProcessor

def upload_pdf(request):
    """
    Handles PDF upload and initiates processing.
    """
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            pdf_file = form.cleaned_data['pdf_file']
            
            # Generate checksum
            checksum = generate_checksum(pdf_file)
            
            # Check if already processed
            existing_doc = PDFDocument.objects.filter(
                file_checksum=checksum
            ).first()
            
            if existing_doc and existing_doc.processing_status == 'completed':
                messages.info(request, 'This PDF has already been processed.')
                return redirect('pdf_checker_app:report', pk=existing_doc.pk)
            
            # Create new document record
            if not existing_doc:
                doc = PDFDocument.objects.create(
                    original_filename=pdf_file.name,
                    file_checksum=checksum,
                    file_size=pdf_file.size,
                    processing_status='pending'
                )
            else:
                doc = existing_doc
            
            # Save temporary file for processing
            temp_path = save_temp_file(pdf_file, checksum)
            
            # Process with veraPDF (synchronous for now)
            try:
                processor = VeraPDFProcessor()
                result = processor.process(temp_path, doc)
                
                messages.success(request, 'PDF successfully analyzed.')
                return redirect('pdf_checker_app:report', pk=doc.pk)
                
            except Exception as e:
                doc.processing_status = 'failed'
                doc.processing_error = str(e)
                doc.save()
                messages.error(request, f'Processing failed: {e}')
            
            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()
    else:
        form = PDFUploadForm()
    
    return render(request, 'pdf_checker_app/upload.html', {
        'form': form
    })

def generate_checksum(file) -> str:
    """
    Generates SHA-256 checksum for uploaded file.
    """
    sha256_hash = hashlib.sha256()
    for chunk in file.chunks():
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()
```

#### Report View
```python
def view_report(request, pk: int):
    """
    Displays the accessibility report for a processed PDF.
    """
    doc = get_object_or_404(PDFDocument, pk=pk)
    
    if doc.processing_status != 'completed':
        messages.warning(request, 'This PDF is still being processed.')
        return redirect('pdf_checker_app:upload')
    
    try:
        result = doc.verapdf_result
        issues = result.issues.all()
        
        # Group issues by severity
        issues_by_severity = {
            'error': issues.filter(severity='error'),
            'warning': issues.filter(severity='warning'),
            'info': issues.filter(severity='info'),
        }
        
    except VeraPDFResult.DoesNotExist:
        messages.error(request, 'No results found for this PDF.')
        return redirect('pdf_checker_app:upload')
    
    return render(request, 'pdf_checker_app/report.html', {
        'document': doc,
        'result': result,
        'issues_by_severity': issues_by_severity,
    })
```

### 4. veraPDF Integration

#### VeraPDF Processor Class
```python
# pdf_checker_app/lib/verapdf_processor.py
import subprocess
import json
from pathlib import Path
from django.conf import settings
from ..models import PDFDocument, VeraPDFResult, AccessibilityIssue

class VeraPDFProcessor:
    """
    Handles veraPDF command execution and result parsing.
    """
    
    def __init__(self):
        self.verapdf_path = settings.VERAPDF_PATH  # e.g., '/usr/local/bin/verapdf'
        self.profile = settings.VERAPDF_PROFILE  # e.g., 'PDFUA_1_MACHINE'
        
    def process(self, pdf_path: Path, document: PDFDocument) -> VeraPDFResult:
        """
        Runs veraPDF on the PDF and stores results.
        """
        document.processing_status = 'processing'
        document.save()
        
        try:
            # Run veraPDF command
            cmd = [
                self.verapdf_path,
                '--format', 'json',
                '--profile', self.profile,
                str(pdf_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            if result.returncode != 0:
                raise Exception(f"veraPDF error: {result.stderr}")
            
            # Parse JSON output
            verapdf_data = json.loads(result.stdout)
            
            # Create result record
            verapdf_result = self._save_result(document, verapdf_data)
            
            # Parse and save issues
            self._save_issues(verapdf_result, verapdf_data)
            
            # Update document status
            document.processing_status = 'completed'
            document.save()
            
            return verapdf_result
            
        except Exception as e:
            document.processing_status = 'failed'
            document.processing_error = str(e)
            document.save()
            raise
    
    def _save_result(self, document: PDFDocument, verapdf_data: dict) -> VeraPDFResult:
        """
        Saves the main veraPDF result.
        """
        # Extract summary information
        report = verapdf_data.get('report', {})
        details = report.get('details', {})
        
        # Determine pass/fail
        is_accessible = details.get('failedRules', 0) == 0
        
        return VeraPDFResult.objects.create(
            pdf_document=document,
            raw_json=verapdf_data,
            is_accessible=is_accessible,
            validation_profile=report.get('profileName', 'Unknown'),
            verapdf_version=verapdf_data.get('release', {}).get('version', 'Unknown'),
            total_checks=details.get('totalRules', 0),
            failed_checks=details.get('failedRules', 0),
            passed_checks=details.get('passedRules', 0)
        )
    
    def _save_issues(self, verapdf_result: VeraPDFResult, verapdf_data: dict):
        """
        Parses and saves individual accessibility issues.
        """
        report = verapdf_data.get('report', {})
        
        # Get validation details
        for detail in report.get('details', {}).get('rule', []):
            if detail.get('status') != 'failed':
                continue
            
            # Map veraPDF status to our severity levels
            severity = self._map_severity(detail.get('level', 'error'))
            
            AccessibilityIssue.objects.create(
                verapdf_result=verapdf_result,
                rule_id=detail.get('clause', 'Unknown'),
                severity=severity,
                description=detail.get('description', 'No description available'),
                location=detail.get('location', ''),
                occurrence_count=detail.get('failedChecks', 1)
            )
    
    def _map_severity(self, verapdf_level: str) -> str:
        """
        Maps veraPDF severity levels to our internal levels.
        """
        mapping = {
            'SHALL': 'error',
            'SHOULD': 'warning',
            'MAY': 'info',
        }
        return mapping.get(verapdf_level.upper(), 'error')
```

### 5. Templates

#### Base Template
```html
<!-- pdf_checker_app/templates/pdf_checker_app/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}PDF Accessibility Checker{% endblock %}</title>
    <style>
        /* CSS-first approach with modern, clean design */
        :root {
            --color-primary: #2563eb;
            --color-success: #16a34a;
            --color-error: #dc2626;
            --color-warning: #d97706;
            --color-info: #0891b2;
            --color-bg: #f9fafb;
            --color-border: #e5e7eb;
        }
        
        body {
            font-family: system-ui, -apple-system, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background: var(--color-bg);
            margin: 0;
            padding: 0;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .card {
            background: white;
            border-radius: 8px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        /* Additional styles... */
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
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
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

#### Upload Template
```html
<!-- pdf_checker_app/templates/pdf_checker_app/upload.html -->
{% extends "pdf_checker_app/base.html" %}

{% block title %}Upload PDF - PDF Accessibility Checker{% endblock %}

{% block content %}
<div class="card">
    <h1>PDF Accessibility Checker</h1>
    <p>Upload a PDF document to check its accessibility compliance using veraPDF.</p>
    
    <form method="post" enctype="multipart/form-data" id="upload-form">
        {% csrf_token %}
        
        <div class="form-group">
            {{ form.pdf_file.label_tag }}
            {{ form.pdf_file }}
            {% if form.pdf_file.help_text %}
                <small class="help-text">{{ form.pdf_file.help_text }}</small>
            {% endif %}
            {% if form.pdf_file.errors %}
                <div class="error">{{ form.pdf_file.errors }}</div>
            {% endif %}
        </div>
        
        <!-- Drag and drop area -->
        <div id="drop-zone" class="drop-zone">
            <p>Or drag and drop your PDF here</p>
        </div>
        
        <button type="submit" class="btn btn-primary">
            Check Accessibility
        </button>
    </form>
</div>

<script>
    // Simple drag-and-drop enhancement
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('id_pdf_file');
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            // Optional: auto-submit
            // document.getElementById('upload-form').submit();
        }
    });
</script>
{% endblock %}
```

#### Report Template
```html
<!-- pdf_checker_app/templates/pdf_checker_app/report.html -->
{% extends "pdf_checker_app/base.html" %}

{% block title %}Accessibility Report - {{ document.original_filename }}{% endblock %}

{% block content %}
<div class="card">
    <h1>Accessibility Report</h1>
    
    <div class="document-info">
        <h2>Document Information</h2>
        <dl>
            <dt>File:</dt>
            <dd>{{ document.original_filename }}</dd>
            
            <dt>Uploaded:</dt>
            <dd>{{ document.uploaded_at|date:"Y-m-d H:i" }}</dd>
            
            <dt>Size:</dt>
            <dd>{{ document.file_size|filesizeformat }}</dd>
        </dl>
    </div>
    
    <div class="result-summary">
        <h2>Accessibility Status</h2>
        {% if result.is_accessible %}
            <div class="status-pass">
                ✓ PASSED - This PDF meets accessibility standards
            </div>
        {% else %}
            <div class="status-fail">
                ✗ FAILED - This PDF has accessibility issues
            </div>
        {% endif %}
        
        <div class="stats">
            <span>Total Checks: {{ result.total_checks }}</span>
            <span>Passed: {{ result.passed_checks }}</span>
            <span>Failed: {{ result.failed_checks }}</span>
        </div>
    </div>
    
    {% if not result.is_accessible %}
    <div class="issues-section">
        <h2>Accessibility Issues</h2>
        
        {% for severity, issues in issues_by_severity.items %}
            {% if issues %}
            <div class="severity-group severity-{{ severity }}">
                <h3>{{ severity|title }}s ({{ issues|length }})</h3>
                <ul>
                    {% for issue in issues %}
                    <li>
                        <strong>Rule {{ issue.rule_id }}:</strong>
                        {{ issue.description }}
                        {% if issue.occurrence_count > 1 %}
                            <span class="occurrence-count">({{ issue.occurrence_count }} occurrences)</span>
                        {% endif %}
                    </li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
        {% endfor %}
    </div>
    {% endif %}
    
    <div class="actions">
        <a href="{% url 'pdf_checker_app:upload' %}" class="btn btn-secondary">
            Check Another PDF
        </a>
    </div>
</div>
{% endblock %}
```

### 6. URL Configuration

```python
# pdf_checker_app/urls.py
from django.urls import path
from . import views

app_name = 'pdf_checker_app'

urlpatterns = [
    path('', views.upload_pdf, name='upload'),
    path('report/<int:pk>/', views.view_report, name='report'),
]
```

```python
# config/urls.py (addition)
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pdf_checker_app.urls')),
    # ... other patterns
]
```

### 7. Settings Configuration

```python
# config/settings.py additions

# veraPDF Configuration
VERAPDF_PATH = env('VERAPDF_PATH', default='/usr/local/bin/verapdf')
VERAPDF_PROFILE = env('VERAPDF_PROFILE', default='PDFUA_1_MACHINE')

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB

# Temp file storage
TEMP_FILE_PATH = BASE_DIR / 'tmp' / 'uploads'
TEMP_FILE_PATH.mkdir(parents=True, exist_ok=True)
```

## Implementation Steps

### Phase 1: Foundation
1. Create database models
2. Run migrations
3. Create basic forms
4. Implement file upload view
5. Add URL patterns

### Phase 2: Processing
1. Implement checksum generation
2. Add veraPDF processor class
3. Integrate veraPDF with view
4. Parse veraPDF JSON output
5. Store results in database

### Phase 3: Reporting
1. Create report view
2. Design report template
3. Implement issue grouping
4. Add styling for pass/fail status

### Phase 4: Enhancement
1. Add drag-and-drop support
2. Improve error handling
3. Add duplicate detection
4. Implement temporary file cleanup

## Testing Strategy

### Unit Tests
```python
# tests/test_models.py
- Test PDFDocument model creation
- Test checksum uniqueness
- Test status transitions

# tests/test_forms.py
- Test PDF validation
- Test file size limits
- Test invalid file types

# tests/test_verapdf.py
- Test command execution
- Test JSON parsing
- Test error handling
- Mock veraPDF responses
```

### Integration Tests
```python
# tests/test_views.py
- Test complete upload flow
- Test duplicate file handling
- Test report generation
- Test error scenarios
```

## Dependencies to Add

```toml
# pyproject.toml additions
[project]
dependencies = [
    # ... existing dependencies
    "python-magic>=0.4.27",  # File type detection
]
```

## Environment Variables

```bash
# .env additions
VERAPDF_PATH=/usr/local/bin/verapdf
VERAPDF_PROFILE=PDFUA_1_MACHINE
```

## Future Enhancements

After this initial implementation is working:

1. **Async Processing**
   - Move to background processing with cronjob
   - Add processing queue table
   - Implement batch processor script

2. **Caching Improvements**
   - Add result caching by checksum
   - Implement cache expiry
   - Add cache statistics

3. **UI Enhancements**
   - Add progress indicators
   - Implement HTMX for dynamic updates
   - Add file preview
   - Export reports as PDF/CSV

4. **API Addition**
   - Add REST endpoints
   - Implement authentication
   - Add rate limiting

5. **LLM Integration**
   - Add LLM processing for human-readable reports
   - Implement prompt templates
   - Add model selection logic

## Notes

- This plan follows the CSS-first approach with minimal JavaScript
- No WebSockets or real-time updates in initial version
- Synchronous processing initially (async via cronjob later)
- Using Django's built-in test framework
- Following project's coding standards from AGENTS.md

---
