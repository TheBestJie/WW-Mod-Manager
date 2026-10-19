"""Constants shared across WWMM."""

ELEMENTS = ("冷凝", "热熔", "导电", "气动", "衍射", "湮灭")
GROUP_ORDER = (*ELEMENTS, "多属性", "其他", "未分类")
DISABLED_PREFIX = "DISABLED_"
ROSTER_SCHEMA_VERSION = 1
DEFAULT_ROSTER_URL = (
    "https://raw.githubusercontent.com/TheBestJie/WW-Mod-Manager/main/data/roster.json"
)
ELEMENT_ALIASES = {
    "冰": "冷凝",
    "glacio": "冷凝",
    "火": "热熔",
    "fusion": "热熔",
    "雷": "导电",
    "电磁": "导电",
    "电": "导电",
    "electro": "导电",
    "风": "气动",
    "aero": "气动",
    "光": "衍射",
    "spectro": "衍射",
    "暗": "湮灭",
    "havoc": "湮灭",
}
