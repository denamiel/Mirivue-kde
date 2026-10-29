"""Interpret folders and files received from Plasma or another application."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True)
class LaunchRequest:
    """A folder to browse and optional local files to select in that folder."""

    folder: str = ""
    files: tuple[str, ...] = ()


def _local_path(value: str) -> Path | None:
    """Return a local path for plain paths and local ``file:`` URLs."""
    local = Path(value).expanduser()
    # A valid Linux filename may contain a colon. Existing local paths take
    # priority over an apparent URL scheme such as "Saison:2".
    if local.exists():
        return local
    parsed = urlsplit(value)
    if parsed.scheme.casefold() == "file":
        if parsed.hostname not in (None, "", "localhost"):
            return None
        return Path(unquote(parsed.path)).expanduser()
    if parsed.scheme:
        return None
    return Path(value).expanduser()


def parse_launch_requests(arguments, *, show_items=False) -> tuple[LaunchRequest, ...]:
    """Preserve all requested folders, grouping selected files by parent.

    Insertion order is retained and repeated requests for one folder share a
    tab. ShowItems selects folders themselves, rather than browsing inside.
    """
    arguments = list(arguments)
    show_items = show_items or '--select' in arguments
    groups: dict[str, list[str]] = {}
    iterator = iter(arguments)
    positional = False
    for argument in iterator:
        if not positional and argument == '--':
            positional = True
            continue
        if not positional and argument == '--locations-json':
            try:
                batch = json.loads(next(iterator, '{}'))
                for item in batch.get('locations', []):
                    if isinstance(item, dict) and isinstance(item.get('folder'), str) and is_browsable_location(item['folder']):
                        files = item.get('files', [])
                        selected = groups.setdefault(item['folder'], [])
                        if isinstance(files, list):
                            selected.extend(p for p in files if isinstance(p, str) and p not in selected)
            except (ValueError, TypeError, AttributeError):
                pass
            continue
        if not positional and argument == '--session-tab':
            next(iterator, None)
            continue
        value = str(argument).strip()
        if not value or (not positional and value.startswith("-")):
            continue
        local = _local_path(value)
        if local is None:
            if urlsplit(value).scheme:
                groups.setdefault(value, [])
            continue
        absolute = local.absolute()
        if absolute.is_dir() and not show_items:
            groups.setdefault(str(absolute), [])
        elif absolute.exists() and show_items:
            selected = groups.setdefault(str(absolute.parent), [])
            if str(absolute) not in selected:
                selected.append(str(absolute))
        elif absolute.is_file():
            selected = groups.setdefault(str(absolute.parent), [])
            if str(absolute) not in selected:
                selected.append(str(absolute))
    return tuple(LaunchRequest(folder, tuple(files)) for folder, files in groups.items())


def parse_launch_arguments(arguments) -> LaunchRequest:
    """Single-location compatibility API used to validate a startup folder."""
    requests = parse_launch_requests(arguments)
    return requests[0] if requests else LaunchRequest()


def parse_show_items(arguments) -> LaunchRequest:
    """Resolve FileManager1 ShowItems URLs to one parent and its selected items."""
    requests = parse_launch_requests(arguments, show_items=True)
    return requests[0] if requests else LaunchRequest()


def is_browsable_location(value: str) -> bool:
    """Validate a location received from the local single-instance socket."""
    if not value:
        return False
    local = _local_path(value)
    if local is not None:
        return local.is_dir()
    return bool(urlsplit(value).scheme)
