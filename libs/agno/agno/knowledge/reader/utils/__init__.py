from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from shutil import copyfileobj
from tempfile import NamedTemporaryFile
from typing import Generator, IO, Optional, Union

from agno.knowledge.reader.utils.spreadsheet import (
    convert_xls_cell_value,
    excel_rows_to_documents,
    get_workbook_name,
    infer_file_extension,
    row_to_csv_line,
    stringify_cell_value,
)

__all__ = [
    "convert_xls_cell_value",
    "excel_rows_to_documents",
    "get_workbook_name",
    "infer_file_extension",
    "row_to_csv_line",
    "stringify_cell_value",
    "temp_file_from_bytesio",
]


@contextmanager
def temp_file_from_bytesio(
    file: Union[IO, BytesIO, Path, str],
    suffix: str,
) -> Generator[Optional[str], None, None]:
    """Resolve a file-like object to a file path string.

    - If *file* is a ``str`` or ``Path``, yields it as-is.
    - If *file* is a ``BytesIO`` or file-like object, writes its contents to a
      temporary file with the given *suffix*, yields the temp path, and cleans
      up on exit.
    """
    # Already a path on disk
    if isinstance(file, (str, Path)):
        yield str(file)
        return

    # BytesIO or other file-like object -- materialise to a temp file
    tmp_path: Optional[str] = None
    try:
        if hasattr(file, "seek"):
            file.seek(0)
        with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            copyfileobj(file, tmp)
            tmp_path = tmp.name
        if hasattr(file, "seek"):
            file.seek(0)
        yield tmp_path
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass
