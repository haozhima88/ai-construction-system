from fastapi import APIRouter, UploadFile, File

from services.excel_service import process_excel

router = APIRouter()


@router.post("/upload-bid-excel")
async def upload_bid_excel(
    file: UploadFile = File(...)
):

    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as f:

        f.write(await file.read())

    results = process_excel(file_path)

    return {
        "count": len(results),
        "data": results
    }