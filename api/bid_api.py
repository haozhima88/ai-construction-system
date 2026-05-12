from fastapi import APIRouter, UploadFile, File

from services.excel_service import process_excel
from services.intelligence_engine import (
    analyze_cost_structure
)

router = APIRouter()


@router.post("/upload-bid-excel")
async def upload_bid_excel(
    file: UploadFile = File(...)
):

    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as f:

        f.write(await file.read())

    results = process_excel(file_path)
    analysis_result = analyze_cost_structure(results)

    return {
        "count": len(results),
        "data": results,
        "analysis": analysis_result
    }