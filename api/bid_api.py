from fastapi import APIRouter, UploadFile, File
import pandas as pd

from services.excel_service import process_excel
from services.intelligence_engine import (
    analyze_cost_structure
)

from services.excel_row_parser import  (
    classify_rows
)   

from services.data_quality import (
    validate_records
)

router = APIRouter()


@router.post("/upload-bid-excel/")
async def upload_bid_excel(

    file: UploadFile = File(...),

    sheet_name: int = 0
):

    # 保存文件
    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as f:

        f.write(await file.read())

    # Excel 解析
    # results = process_excel(file_path, sheet_name)
    results = classify_rows(file_path, sheet_name)

    # analysis_result = analyze_cost_structure(results)

    # quality_result = validate_records(results)

    return {
        "count": len(results),
        "data": results,
        # "analysis": analysis_result,
        # "quality": quality_result
    }

@router.post("/excel-sheet-names/")
async def get_excel_sheet_names(

    file: UploadFile = File(...)
):

    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as f:

        f.write(await file.read())

    excel_file = pd.ExcelFile(file_path)

    return {

        "sheet_names": excel_file.sheet_names
    }