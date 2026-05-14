"""
給与明細一覧CSVパーサー（勤務・賃金設定別集計）

集計対象列:
  - 基本給
  - 割増賃金合計
  - 通勤手当（非課税）

グループキー:
  - 勤務・賃金設定（正社員 / アルバイト 等）
"""
import csv
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# グループキー列のエイリアス
GROUP_COLUMN_ALIASES = ["勤務・賃金設定", "雇用区分", "雇用形態", "種別", "契約種別"]

# 集計対象列の定義: (表示名, エイリアスリスト)
TARGET_COLUMNS = [
    ("基本給",          ["基本給"]),
    ("割増賃金合計",    ["割増賃金合計", "割増賃金", "割増手当合計", "時間外割増合計",
                         "残業代合計", "時間外労働手当合計"]),
    ("通勤手当（非課税）", ["通勤手当（非課税）", "通勤手当(非課税)",
                            "通勤費（非課税）", "通勤費(非課税)", "通勤手当"]),
]

# 合計行と判定するキーワード
_TOTAL_KEYWORDS = {"総合計", "合計", "小計", "total"}


@dataclass
class PayrollGroupRow:
    employee_type: str
    employee_count: int = 0
    amounts: Dict[str, int] = field(default_factory=dict)


@dataclass
class PayrollSummaryResult:
    groups: List[PayrollGroupRow]
    detected_columns: List[str]          # 実際に検出できた集計列の表示名
    missing_columns: List[str]           # 見つからなかった列の表示名


def _detect_encoding(filepath: str) -> str:
    for enc in ["utf-8-sig", "utf-8", "cp932"]:
        try:
            with open(filepath, encoding=enc) as f:
                f.read()
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "cp932"


def _to_int(value: str) -> int:
    cleaned = value.replace(",", "").replace("￥", "").replace("¥", "").strip()
    if cleaned in ("", "-", "—"):
        return 0
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0


def parse(filepath: str) -> PayrollSummaryResult:
    encoding = _detect_encoding(filepath)

    with open(filepath, encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSVにヘッダーが見つかりません")

        headers = list(reader.fieldnames)

        # グループキー列を特定
        group_col = next((h for a in GROUP_COLUMN_ALIASES for h in headers if h == a), None)
        if group_col is None:
            raise ValueError(
                f"勤務・賃金設定列が見つかりません。\n"
                f"検出された列: {', '.join(headers)}"
            )

        # 集計対象列を特定（エイリアス順に最初にヒットしたもの）
        col_map: Dict[str, Optional[str]] = {}  # 表示名 → 実際の列名
        for label, aliases in TARGET_COLUMNS:
            col_map[label] = next((h for a in aliases for h in headers if h == a), None)

        detected = [lbl for lbl, col in col_map.items() if col is not None]
        missing  = [lbl for lbl, col in col_map.items() if col is None]

        # グループ別集計
        counts: Dict[str, int] = defaultdict(int)
        totals: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for row in reader:
            grp = (row.get(group_col) or "").strip()
            name = (row.get("氏名") or row.get("従業員名") or row.get("名前") or "").strip()
            empno = (row.get("従業員番号") or row.get("社員番号") or "").strip()

            # 空行・合計行スキップ
            if not grp and not name and not empno:
                continue
            norm = name.replace(" ", "").replace("　", "").lower()
            if norm in _TOTAL_KEYWORDS or empno.lower() in _TOTAL_KEYWORDS:
                continue

            if not grp:
                grp = "（未設定）"

            counts[grp] += 1
            for label, col in col_map.items():
                if col:
                    totals[grp][label] += _to_int(row.get(col, ""))

    # 出力順: グループ名でソート
    groups = [
        PayrollGroupRow(
            employee_type=grp,
            employee_count=counts[grp],
            amounts=dict(totals[grp]),
        )
        for grp in sorted(counts.keys())
    ]

    return PayrollSummaryResult(
        groups=groups,
        detected_columns=detected,
        missing_columns=missing,
    )
