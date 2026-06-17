from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd

from cost_engine.schemas import PriceRow


EXPECTED_HEADERS = ["分类", "分类", "名称", "人", "材", "机", "单位", "备注"]


def _read_excel(path: Path, sheet_name: str | int | None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".xls":
        try:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                return pd.read_excel(path, sheet_name=sheet_name or 0, engine="xlrd", dtype=str)
        except ImportError as exc:
            converted = convert_xls_with_libreoffice(path)
            if converted:
                return pd.read_excel(converted, sheet_name=sheet_name or 0, engine="openpyxl", dtype=str)
            raise RuntimeError(
                "Reading .xls requires xlrd, or LibreOffice/soffice for headless conversion. "
                "Install xlrd or convert the source to .xlsx under data/private/converted."
            ) from exc
    return pd.read_excel(path, sheet_name=sheet_name or 0, engine="openpyxl", dtype=str)


def convert_xls_with_libreoffice(path: Path) -> Path | None:
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        return None
    out_dir = Path(tempfile.mkdtemp(prefix="cost-engine-xls-"))
    subprocess.run(
        [executable, "--headless", "--convert-to", "xlsx", "--outdir", str(out_dir), str(path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    converted = out_dir / f"{path.stem}.xlsx"
    return converted if converted.exists() else None


def sheet_names(path: str | Path) -> list[str]:
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        excel = pd.ExcelFile(path)
    return list(excel.sheet_names)


def read_price_rows(path: str | Path, sheet_name: str | None = None) -> tuple[list[PriceRow], list[str]]:
    source = Path(path)
    df = _read_excel(source, sheet_name)
    headers = [str(column).strip() for column in df.columns.tolist()]
    if len(headers) < 8:
        raise ValueError(f"Expected at least 8 columns, found {len(headers)}")
    df = df.iloc[:, :8].copy()
    df.columns = EXPECTED_HEADERS
    rows: list[PriceRow] = []
    for index, record in df.iterrows():
        if record.isna().all():
            continue
        rows.append(
            PriceRow(
                source_row_no=int(index) + 2,
                category_level_1=record.iloc[0],
                category_level_2=record.iloc[1],
                item_name=record.iloc[2],
                labor_price=record.iloc[3],
                material_price=record.iloc[4],
                machine_price=record.iloc[5],
                unit=record.iloc[6],
                remark=record.iloc[7],
            )
        )
    return rows, headers
