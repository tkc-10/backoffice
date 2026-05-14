"""
給与一覧CSVパーサー

列名は給与ソフトごとに異なるため、エイリアス辞書で複数の表記を吸収する。
必須列は従業員番号・氏名のみ。その他はなければスキップ。
"""
import csv
import os
from typing import List, Optional

from src.models.employee import SalaryRecord

# フィールド名 → 受け入れる列名のリスト（先頭優先）
COLUMN_ALIASES: dict[str, list[str]] = {
    "employee_number": ["従業員番号", "社員番号", "スタッフコード", "スタッフID"],
    "name":            ["氏名", "従業員名", "名前", "社員名"],
    "name_kana":       ["氏名カナ", "フリガナ", "カナ氏名", "氏名（カナ）"],
    "employee_type":   ["種別", "勤務・賃金設定", "雇用区分", "雇用形態", "契約種別"],
    "base_salary":     ["基本給"],
    "overtime_pay":    ["残業代", "時間外労働手当", "時間外手当", "残業手当"],
    "allowances":      ["各種手当", "各種手当合計", "手当合計"],
    "deductions":      ["控除合計", "社会保険料等控除合計", "控除額合計"],
    "net_pay":         ["差引支給額", "差引支給金額", "総振込額", "振込金額"],
}

REQUIRED_FIELDS = {"employee_number", "name"}

# 合計行と判定するキーワード（従業員名 or 従業員番号がこれに一致したらスキップ）
_TOTAL_ROW_KEYWORDS = {"総合計", "合計", "小計", "total"}


class SalaryCSVParser:
    def __init__(
        self,
        filepath: str,
        column_map: Optional[dict] = None,
        encoding: Optional[str] = None,
    ):
        self.filepath = filepath
        self.column_map = column_map  # 明示的な上書き用（省略時はエイリアス自動検出）
        self.encoding = encoding or self._detect_encoding(filepath)

    @staticmethod
    def _detect_encoding(filepath: str) -> str:
        for enc in ["utf-8-sig", "utf-8", "cp932"]:
            try:
                with open(filepath, encoding=enc) as f:
                    f.read()
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return "utf-8-sig"

    def parse(self) -> List[SalaryRecord]:
        records: List[SalaryRecord] = []

        with open(self.filepath, encoding=self.encoding, newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(f"CSVにヘッダーが見つかりません: {self.filepath}")

            # 列名 → 内部フィールド名 のマッピングを構築
            active_map = self._build_active_map(reader.fieldnames)

            # 必須列チェック
            missing = REQUIRED_FIELDS - set(active_map.values())
            if missing:
                detected = ", ".join(str(c) for c in reader.fieldnames)
                raise ValueError(
                    f"必須列が見つかりません: {', '.join(missing)}\n"
                    f"検出された列名: {detected}\n"
                    f"「従業員番号」「氏名」（または同等の列名）が必要です。"
                )

            for row in reader:
                rec = self._build_record(row, active_map)
                if rec:
                    records.append(rec)

        return records

    def _build_active_map(self, fieldnames) -> dict[str, str]:
        """CSVヘッダー列名 → 内部フィールド名 のマッピングを返す"""
        if self.column_map:
            return {col: field for col, field in self.column_map.items() if col in fieldnames}

        result: dict[str, str] = {}
        # エイリアスリストと照合（先着1件）
        for field, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in fieldnames:
                    result[alias] = field
                    break
        return result

    def _build_record(self, row: dict, active_map: dict[str, str]) -> Optional[SalaryRecord]:
        mapped = {field: (row.get(col) or "").strip() for col, field in active_map.items()}

        emp_num = mapped.get("employee_number", "")
        name = mapped.get("name", "")

        # 空行・合計行をスキップ
        if not emp_num and not name:
            return None
        if name.replace(" ", "").replace("　", "") in _TOTAL_ROW_KEYWORDS:
            return None
        if emp_num.replace(" ", "") in _TOTAL_ROW_KEYWORDS:
            return None

        extra = {col: val for col, val in row.items() if col not in active_map and (val or "").strip()}

        return SalaryRecord(
            employee_number=emp_num,
            name=name,
            name_kana=mapped.get("name_kana", ""),
            employee_type=mapped.get("employee_type", ""),
            base_salary=self._to_int(mapped.get("base_salary", "")),
            overtime_pay=self._to_int(mapped.get("overtime_pay", "")),
            allowances=self._to_int(mapped.get("allowances", "")),
            deductions=self._to_int(mapped.get("deductions", "")),
            net_pay=self._to_int(mapped.get("net_pay", "")),
            extra=extra,
        )

    @staticmethod
    def _to_int(value: str) -> int:
        cleaned = value.replace(",", "").replace("￥", "").replace("¥", "").replace("-", "").strip()
        try:
            return int(float(cleaned)) if cleaned else 0
        except (ValueError, TypeError):
            return 0
