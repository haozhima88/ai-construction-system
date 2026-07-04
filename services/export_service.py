import pandas as pd


IMPORT_BID_RECORD_EXPORT_COLUMNS = {
    "id": "ID",
    "batch_id": "导入批次ID",
    "source_file_name": "来源文件名",
    "source_sheet_name": "来源Sheet名称",
    "source_sheet_index": "来源Sheet序号",
    "source_row_index": "源行索引",
    "source_excel_row_no": "Excel原始行号",
    "parser_confidence": "解析置信度",
    "review_status": "验收状态",
    "parse_status": "解析状态",
    "parse_warnings": "解析警告",
    "project_name": "项目名称",
    "category": "分部分类",
    "serial_number": "序号",
    "item_code": "项目编码",
    "item_name": "项目名称",
    "feature": "项目特征",
    "unit": "单位",
    "quantity": "工程量",
    "unit_price": "综合单价",
    "total_price": "合价",
    "mapping_version": "映射版本",
    "imported_at": "导入时间",
}


def export_bid_records(db_conn=None, output_file="exports/bid_records.xlsx"):

    if db_conn is None:
        from utils.db import conn as db_conn

    sql = """
        SELECT
            id,
            batch_id,
            source_file_name,
            source_sheet_name,
            source_sheet_index,
            source_row_index,
            source_excel_row_no,
            parser_confidence,
            review_status,
            parse_status,
            parse_warnings,
            project_name,
            category,
            serial_number,
            item_code,
            item_name,
            feature,
            unit,
            quantity,
            unit_price,
            total_price,
            mapping_version,
            imported_at
        FROM import_bid_records
        ORDER BY id
    """

    df = pd.read_sql(sql, db_conn)
    df = df.rename(columns=IMPORT_BID_RECORD_EXPORT_COLUMNS)

    df.to_excel(
        output_file,
        index=False
    )

    return output_file
