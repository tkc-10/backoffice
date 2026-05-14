"""
経費精算一覧CSVパーサー（freee経費精算エクスポート対応）

- 備考列の氏名でグループ化
- 合計金額列を参照
- 申請番号で重複排除（1申請が複数行に分かれる場合に対応）
"""
import csv
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

# 氏名として使う列のエイリアス
NAME_COLUMN_ALIASES = ["備考", "申請者名", "氏名", "担当者", "担当者名"]
# 金額として使う列のエイリアス（「金額」より「合計金額」を優先）
AMOUNT_COLUMN_ALIASES = ["合計金額", "精算金額", "申請金額", "金額合計", "総額"]
# 申請番号列（重複排除用）
ID_COLUMN_ALIASES = ["申請番号", "No", "ID", "番号"]


@dataclass
class ExpenseSummaryRow:
    name: str         # 備考列の氏名
    count: int        # 申請件数
    total_amount: int # 合計精算額


class ExpenseCSVParser:
    def __init__(self, filepath: str, encoding: Optional[str] = None):
        self.filepath = filepath
        self.encoding = encoding or self._detect_encoding(filepath)

    @staticmethod
    def _find_column(fieldnames, aliases: list) -> Optional[str]:
        for alias in aliases:
            if alias in fieldnames:
                return alias
        return None

    @staticmethod
    def _detect_encoding(filepath: str) -> str:
        for enc in ["utf-8-sig", "utf-8", "cp932"]:
            try:
                with open(filepath, encoding=enc) as f:
                    f.read()
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return "cp932"

    def parse(self) -> List[ExpenseSummaryRow]:
        with open(self.filepath, encoding=self.encoding, newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSVにヘッダーが見つかりません")

            name_col   = self._find_column(reader.fieldnames, NAME_COLUMN_ALIASES)
            amount_col = self._find_column(reader.fieldnames, AMOUNT_COLUMN_ALIASES)
            id_col     = self._find_column(reader.fieldnames, ID_COLUMN_ALIASES)

            if not name_col:
                raise ValueError(
                    f"氏名列が見つかりません。「備考」等の列が必要です。\n"
                    f"検出された列: {', '.join(reader.fieldnames)}"
                )
            if not amount_col:
                raise ValueError(
                    f"金額列が見つかりません。「合計金額」等の列が必要です。\n"
                    f"検出された列: {', '.join(reader.fieldnames)}"
                )

            # 申請番号 → (氏名, 合計金額) で重複排除
            seen_ids: dict[str, tuple[str, int]] = {}
            # id列がない場合はすべて別申請として扱う
            fallback_counter = 0

            for row in reader:
                name = (row.get(name_col) or "").strip()
                amount_str = (row.get(amount_col) or "").replace(",", "").strip()

                if not name:
                    continue

                try:
                    amount = int(float(amount_str)) if amount_str else 0
                except ValueError:
                    amount = 0

                if id_col:
                    app_id = (row.get(id_col) or "").strip()
                else:
                    fallback_counter += 1
                    app_id = str(fallback_counter)

                if app_id and app_id not in seen_ids:
                    seen_ids[app_id] = (name, amount)

        # 氏名でグループ化・集計
        totals: dict[str, int] = defaultdict(int)
        counts: dict[str, int] = defaultdict(int)

        for name, amount in seen_ids.values():
            totals[name] += amount
            counts[name] += 1

        return [
            ExpenseSummaryRow(name=name, count=counts[name], total_amount=totals[name])
            for name in sorted(totals.keys())
        ]
