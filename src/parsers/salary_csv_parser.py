"""
給与一覧CSVパーサー

期待するCSV列（列名は設定で変更可能）:
  従業員番号, 氏名, 氏名カナ, 種別, 基本給, 残業代, 各種手当, 控除合計, 差引支給額
"""
import csv
import os
from typing import List, Optional

from src.models.employee import SalaryRecord


# デフォルトの列名マッピング（実ファイルの列名 → 内部フィールド名）
DEFAULT_COLUMN_MAP = {
    "従業員番号": "employee_number",
    "氏名": "name",
    "氏名カナ": "name_kana",
    "種別": "employee_type",
    "基本給": "base_salary",
    "残業代": "overtime_pay",
    "各種手当": "allowances",
    "控除合計": "deductions",
    "差引支給額": "net_pay",
}

# 必須列
REQUIRED_COLUMNS = {"employee_number", "name"}


class SalaryCSVParser:
    """
    給与一覧CSVを読み込み SalaryRecord のリストを返す。

    Parameters
    ----------
    filepath : str
        CSVファイルのパス
    column_map : dict, optional
        列名マッピング。デフォルトは DEFAULT_COLUMN_MAP を使用。
    encoding : str, optional
        エンコーディング。省略時は自動判定。
    """

    def __init__(
        self,
        filepath: str,
        column_map: Optional[dict] = None,
        encoding: Optional[str] = None,
    ):
        self.filepath = filepath
        self.column_map = column_map or DEFAULT_COLUMN_MAP
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
                raise ValueError(f"CSVファイルにヘッダーが見つかりません: {self.filepath}")

            # 実際の列名 → 内部フィールド名 のマッピングを構築
            reverse_map = {v: k for k, v in self.column_map.items()}
            active_map: dict[str, str] = {}
            for col in reader.fieldnames:
                col_stripped = col.strip()
                if col_stripped in self.column_map:
                    active_map[col] = self.column_map[col_stripped]

            # 必須列チェック
            mapped_fields = set(active_map.values())
            missing = REQUIRED_COLUMNS - mapped_fields
            if missing:
                missing_labels = [reverse_map.get(m, m) for m in missing]
                raise ValueError(
                    f"CSVに必須列が見つかりません: {', '.join(missing_labels)}\n"
                    f"検出された列: {', '.join(str(c) for c in reader.fieldnames)}"
                )

            for row in reader:
                record = self._build_record(row, active_map)
                if record:
                    records.append(record)

        return records

    def _build_record(self, row: dict, active_map: dict[str, str]) -> Optional[SalaryRecord]:
        mapped = {internal: (row.get(col) or "").strip() for col, internal in active_map.items()}

        employee_number = mapped.get("employee_number", "").strip()
        name = mapped.get("name", "").strip()
        if not employee_number and not name:
            return None  # 空行をスキップ

        extra = {
            col: val for col, val in row.items()
            if col not in active_map and val.strip()
        }

        return SalaryRecord(
            employee_number=employee_number,
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
        cleaned = value.replace(",", "").replace("￥", "").replace("¥", "").strip()
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0
