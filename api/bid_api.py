from fastapi import APIRouter, UploadFile, File
import pandas as pd

from services.db_service import (

    insert_many_records
)

from services.excel_row_pipeline import (

    attach_category,
    build_logical_records,
    clean_row_data,
    merge_continuation_rows,
    build_normalized_records,
    build_quality_report
)

from services.excel_service import (

    process_excel
)

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
    records = classify_rows(file_path, sheet_name)

    cleaned_rows = clean_row_data(records)

    attached_rows = attach_category(cleaned_rows)

    merged_rows = merge_continuation_rows(attached_rows)

    logical_records = build_logical_records(merged_rows)

    normalized_records = build_normalized_records(logical_records)

    quality_result = build_quality_report(normalized_records)

    insert_many_records(normalized_records)



    return {
        "count": len(normalized_records),
        "data": normalized_records,
        "quality": quality_result
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