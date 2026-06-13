from fastapi import APIRouter, UploadFile, File
import pandas as pd
from utils.db import conn
import uuid

from fastapi.responses import FileResponse

from services.export_service import (
    export_bid_records
)

from services.db_service import (

    insert_many_records,
    query_import_records_for_review,
    update_review_status_service,
    approved_to_bid_records,
    update_review_status_service
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

# Bid Records API
# ==========================================
@router.post("/upload-bid-excel/")
async def upload_bid_excel(

    file: UploadFile = File(...),

    sheet_name: int = 0
):

    # 讀取文件
    # Read File
    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as f:

        f.write(await file.read())

    # 找到表頭行
    # Find the header row
    header_rows, skip_rows = find_header_rows(file_path, sheet_name)

    # 合并表頭行
    # merge header rows
    merged_rows = merge_header_rows(header_rows)

    # 構建 schema
    # Build schema
    schema = build_schema(merged_rows)

    # 建立行分類
    # Create row categories
    records = classify_rows(file_path, sheet_name, schema, skip_rows)

    # 合并續行
    # Merge consecutive lines
    merged_rows = merge_continuation_rows(records,schema)

    # 附加類別信息
    # Attachment category info
    attach_records = attach_category(records, schema)

    # 生成邏輯記錄
    # Generate logical records
    batch_id = str(uuid.uuid4())
    logical_records = build_logical_records(
        attach_records,
        schema,
    )

    # 標準化記錄數據
    # Standardize records
    normalized_records = build_normalized_records(
        logical_records,
        batch_id=batch_id,
        source_file_name=file.filename,
        source_sheet_name=str(sheet_name),
        mapping_version="v1.0"
    )

    # 寫入到import_bid_records表
    # Write into the import_bid_records table
    insert_many_records(normalized_records)


    # quality_result_test
    # quality_result = build_quality_report(normalized_records)

    return {

        "schema": schema,
        "normalized_records": normalized_records
        # "quality": quality_result,
        # "analysis": analysis_result
    }



# Read Excel Sheet Names API
# ==========================================
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



# Export Bid Records API
# ==========================================
@router.get("/export-bid-records/")
def export_bid():

    file_path = export_bid_records()

    return FileResponse(
        file_path,
        filename="bid_records.xlsx"
    )



# Review Import Bid Records API
# ==========================================
@router.get("/review-import-bid-records/")
def get_review_import_bid_records():

    records = query_import_records_for_review()

    return {
        "success": True,
        "count": len(records),
        "records": records
    }



# Update Review Status API
# ==========================================
@router.get("/update-review-status/")
@router.post("/review-record")
def review_record(record_id: int, new_status: str):
    result = update_review_status_service(record_id, new_status)
    return result



# Approved records to bid_records table
# ==========================================
@router.post("/sync-approved-records/")
def sync_approved_records(batch_id: str):

    result = approved_to_bid_records(batch_id)

    return result
