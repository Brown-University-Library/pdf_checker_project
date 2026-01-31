"""
Updates the pattern header HTML from a remote source.
"""

import pathlib
from argparse import ArgumentParser

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand


def fetch_pattern_header(url: str) -> str:
    """
    Fetches pattern header HTML from the given URL.
    """
    response: httpx.Response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    return response.text


def resolve_target_path() -> pathlib.Path:
    """
    Resolves the target path for the pattern header include.
    """
    app_dir: pathlib.Path = pathlib.Path(__file__).resolve().parent.parent.parent
    target_path: pathlib.Path = (
        app_dir / 'pdf_checker_app_templates' / 'pdf_checker_app' / 'includes' / 'pattern_header.html'
    )
    return target_path


def save_pattern_header(content: str, target_path: pathlib.Path) -> None:
    """
    Saves pattern header HTML to the target file.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding='utf-8')


class Command(BaseCommand):
    """
    Updates the pattern header HTML from a remote source.
    """

    help = 'Updates the pattern header HTML from PATTERN_HEADER_URL'

    def add_arguments(self, parser: ArgumentParser) -> None:
        """
        Adds command-line arguments.
        """
        parser.add_argument(
            '--url',
            type=str,
            help='Override URL from settings',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch but do not save',
        )

    def handle(self, *args: object, **options: object) -> None:
        """
        Executes the command.
        """
        options_dict: dict[str, object] = options
        url_option = options_dict.get('url')
        url_override = url_option if isinstance(url_option, str) else ''
        url: str = url_override or getattr(settings, 'PATTERN_HEADER_URL', '')
        if not url:
            self.stdout.write(self.style.ERROR('PATTERN_HEADER_URL not set in settings and --url not provided'))
            return

        dry_run = bool(options_dict.get('dry_run'))
        target_path = resolve_target_path()

        self.stdout.write(f'Fetching pattern header from: {url}')
        try:
            content = fetch_pattern_header(url)
        except httpx.HTTPError as exc:
            self.stdout.write(self.style.ERROR(f'Failed to fetch: {exc}'))
            return

        self.stdout.write(f'Fetched {len(content)} characters')
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run - not saving'))
            return

        save_pattern_header(content, target_path)
        self.stdout.write(self.style.SUCCESS(f'Saved to: {target_path}'))
