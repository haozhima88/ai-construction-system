from fastapi import APIRouter, UploadFile, File
import pandas as pd
from utils.db import conn

from fastapi.responses import FileResponse

from services.export_service import (
    export_bid_records
)

from services.db_service import (

    insert_many_records
)


from services.excel_row_pipeline import (

    attach_category,
    attach_context_to_main_rows,
    build_logical_records,
    clean_row_data,
    merge_continuation_rows,
    merge_header_rows,
    build_schema,
    attach_category,
    build_normalized_records,
    build_quality_report,
)

from services.excel_service import (

    process_excel
)

from services.intelligence_engine import (

    analyze_cost_structure
)


from services.excel_row_parser import  (

    classify_rows,
    find_header_rows
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

    # 保存上傳文件到本地
    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as f:

        f.write(await file.read())

    # 找到表頭行
    header_rows, skip_rows = find_header_rows(file_path, sheet_name)

    # 合并表頭行
    merged_rows = merge_header_rows(header_rows)

    # 構建 schema
    schema = build_schema(merged_rows)

    # 分類行類型
    records = classify_rows(file_path, sheet_name, schema, skip_rows)

    # 合并續行
    merged_rows = merge_continuation_rows(records,schema)

    
    # 附加類別信息
    attach_records = attach_category(records, schema)

    # # 生成邏輯記錄
    logical_records = build_logical_records(attach_records, schema)

    # 標準化記錄數據
    normalized_records = build_normalized_records(logical_records)

    # quality_result = build_quality_report(normalized_records)

    # 
    insert_many_records(normalized_records)



    return {

        "schema": schema,
        "normalized_records": normalized_records
        # "quality": quality_result
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

@router.get("/export-bid-records")
def export_bid():

    file_path = export_bid_records()

    return FileResponse(
        file_path,
        filename="bid_records.xlsx"
    )