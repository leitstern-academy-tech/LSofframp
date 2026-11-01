"""Map file extensions to media types and open-standard status.

Detection is by extension only; the file content is never opened.
"""

from pathlib import PurePosixPath

from lsofframp.core.manifest import FormatInfo, OpenStandard

_OPEN = OpenStandard.YES
_CLOSED = OpenStandard.NO

_KNOWN: dict[str, tuple[str | None, OpenStandard]] = {
    "mbox": ("application/mbox", _OPEN),
    "eml": ("message/rfc822", _OPEN),
    "ics": ("text/calendar", _OPEN),
    "vcf": ("text/vcard", _OPEN),
    "pdf": ("application/pdf", _OPEN),
    "odt": ("application/vnd.oasis.opendocument.text", _OPEN),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", _OPEN),
    "odp": ("application/vnd.oasis.opendocument.presentation", _OPEN),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", _OPEN),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _OPEN),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", _OPEN),
    "csv": ("text/csv", _OPEN),
    "json": ("application/json", _OPEN),
    "xml": ("application/xml", _OPEN),
    "html": ("text/html", _OPEN),
    "htm": ("text/html", _OPEN),
    "md": ("text/markdown", _OPEN),
    "txt": ("text/plain", _OPEN),
    "zip": ("application/zip", _OPEN),
    "png": ("image/png", _OPEN),
    "jpg": ("image/jpeg", _OPEN),
    "jpeg": ("image/jpeg", _OPEN),
    "gif": ("image/gif", _OPEN),
    "svg": ("image/svg+xml", _OPEN),
    "webp": ("image/webp", _OPEN),
    "doc": ("application/msword", _CLOSED),
    "xls": ("application/vnd.ms-excel", _CLOSED),
    "ppt": ("application/vnd.ms-powerpoint", _CLOSED),
    "gdoc": (None, _CLOSED),
    "gsheet": (None, _CLOSED),
    "gslides": (None, _CLOSED),
}


def describe_format(path: str) -> FormatInfo:
    """Describe the format of ``path`` from its last extension; unknown if not listed."""
    suffix = PurePosixPath(path).suffix.lower().lstrip(".")
    if not suffix:
        return FormatInfo()
    mediatype, open_standard = _KNOWN.get(suffix, (None, OpenStandard.UNKNOWN))
    return FormatInfo(mediatype=mediatype, extension=suffix, open_standard=open_standard)