# ==========================================
# 建築招標 Excel 欄位標準化映射（中國建築業常見版本）
# Construction Bid Excel Column Mapping
# Schema-driven Architecture
# 模式驅動架構
# ==========================================
from utils.mappings.basic_mapping import BASIC_MAPPING
from utils.mappings.bid_mapping import BID_MAPPING
from utils.mappings.material_mapping import MATERIAL_MAPPING
from utils.mappings.cost_mapping import COST_MAPPING
from utils.mappings.tax_mapping import TAX_MAPPING
from utils.mappings.project_mapping import PROJECT_MAPPING
from utils.mappings.summary_mapping import SUMMARY_MAPPING
from utils.mappings.supplier_mapping import SUPPLIER_MAPPING
from utils.mappings.labor_mapping import LABOR_MAPPING
from utils.mappings.contract_mapping import CONTRACT_MAPPING


COLUMN_MAPPING = {

    **BASIC_MAPPING,
    **BID_MAPPING,
    **MATERIAL_MAPPING,
    **COST_MAPPING,
    **TAX_MAPPING,
    **PROJECT_MAPPING,
    **SUMMARY_MAPPING,
    **SUPPLIER_MAPPING,
    **LABOR_MAPPING,
    **CONTRACT_MAPPING
}

# ==========================================
# 所有字段名（給 Parser 用）
# ==========================================

ALL_MAPPING_KEYWORDS = list(

    COLUMN_MAPPING.keys()
)