# ==========================================
# Construction Cost Rule Engine
# 建築成本分類規則引擎
# ==========================================


# 材料費
MATERIAL_KEYWORDS = [

    # 混凝土
    "混凝土",
    "砼",

    # 鋼筋
    "鋼筋",
    "钢筋",

    # 水泥
    "水泥",

    # 磚
    "磚",
    "砖",

    # 模板
    "模板",

    # 防水
    "防水",

    # 塗料
    "塗料",
    "涂料",

    # 石材
    "石材",

    # 管材
    "管材",
    "管道",

    # 電纜
    "電纜",
    "电缆",

    # 門窗
    "門窗",
    "门窗",

    # 保溫
    "保溫",
    "保温",

    # 砂石
    "砂",
    "石",

    # 瀝青
    "瀝青",
    "沥青"
]


# 人工費
LABOR_KEYWORDS = [

    # 安裝
    "安裝",
    "安装",

    # 施工
    "施工",

    # 人工
    "人工",

    # 焊接
    "焊接",

    # 綁扎
    "綁扎",
    "绑扎",

    # 砌築
    "砌築",
    "砌筑",

    # 抹灰
    "抹灰",

    # 澆築
    "澆築",
    "浇筑",

    # 吊裝
    "吊裝",
    "吊装",

    # 清理
    "清理",

    # 拆除
    "拆除"
]


# 機械費
MACHINE_KEYWORDS = [

    # 塔吊
    "塔吊",

    # 挖機
    "挖機",
    "挖机",

    # 吊車
    "吊車",
    "吊车",

    # 機械
    "機械",
    "机械",

    # 設備
    "設備",
    "设备",

    # 泵車
    "泵車",
    "泵车",

    # 發電機
    "發電機",
    "发电机",

    # 壓路機
    "壓路機",
    "压路机",

    # 攪拌機
    "攪拌機",
    "搅拌机"
]


def classify_cost_type(item_name: str):

    # 防止 None
    item_name = str(item_name)

    # 材料費
    for keyword in MATERIAL_KEYWORDS:

        if keyword in item_name:
            return "材料費"

    # 人工費
    for keyword in LABOR_KEYWORDS:

        if keyword in item_name:
            return "人工費"

    # 機械費
    for keyword in MACHINE_KEYWORDS:

        if keyword in item_name:
            return "機械費"

    return "其他"