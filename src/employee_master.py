"""
従業員マスタ生成モジュール

給与一覧CSV と 全銀データ(.txt) を突合し、
従業員番号・氏名・振込口座情報を紐づけたマスタCSVを出力する。

突合キー（優先順位順）:
  1. 全銀の顧客コード1 == 給与CSVの従業員番号
  2. 全銀の顧客コード2 == 給与CSVの従業員番号
  3. 全銀の受取人名カナ == 給与CSVの氏名カナ（カナ列がある場合）
  4. 全銀の振込金額 == 給与CSVの差引支給額（金額が一意の場合のみ）
"""
import csv
import os
from typing import List, Optional, Tuple

from src.models.employee import EmployeeMasterRecord, SalaryRecord
from src.parsers.salary_csv_parser import SalaryCSVParser
from src.parsers.zengin_parser import ZenginDataRecord, ZenginParser


class EmployeeMasterCreator:
    def __init__(
        self,
        salary_csv_path: str,
        zengin_txt_path: str,
        salary_column_map: Optional[dict] = None,
        salary_encoding: Optional[str] = None,
        zengin_encoding: Optional[str] = None,
    ):
        self.salary_csv_path = salary_csv_path
        self.zengin_txt_path = zengin_txt_path
        self.salary_column_map = salary_column_map
        self.salary_encoding = salary_encoding
        self.zengin_encoding = zengin_encoding

    def create(self) -> Tuple[List[EmployeeMasterRecord], List[str]]:
        salary_records = SalaryCSVParser(
            self.salary_csv_path,
            column_map=self.salary_column_map,
            encoding=self.salary_encoding,
        ).parse()

        _, zengin_records, trailer = ZenginParser(
            self.zengin_txt_path, encoding=self.zengin_encoding
        ).parse()

        return self._merge(salary_records, zengin_records)

    def _merge(
        self,
        salary_records: List[SalaryRecord],
        zengin_records: List[ZenginDataRecord],
    ) -> Tuple[List[EmployeeMasterRecord], List[str]]:
        warnings: List[str] = []

        # インデックス構築
        by_code1: dict[str, ZenginDataRecord] = {}
        by_code2: dict[str, ZenginDataRecord] = {}
        by_kana:  dict[str, List[ZenginDataRecord]] = {}
        by_amount: dict[int, List[ZenginDataRecord]] = {}

        for zr in zengin_records:
            if zr.customer_code1:
                by_code1[zr.customer_code1] = zr
            if zr.customer_code2:
                by_code2[zr.customer_code2] = zr
            if zr.account_holder_kana:
                by_kana.setdefault(zr.account_holder_kana, []).append(zr)
            if zr.transfer_amount > 0:
                by_amount.setdefault(zr.transfer_amount, []).append(zr)

        master_records: List[EmployeeMasterRecord] = []
        matched_ids: set[int] = set()

        for sr in salary_records:
            emp_num = sr.employee_number
            zengin_rec: Optional[ZenginDataRecord] = None
            match_method = ""

            # 1. 顧客コード1
            if emp_num and emp_num in by_code1:
                zengin_rec = by_code1[emp_num]
                match_method = "顧客コード1"

            # 2. 顧客コード2
            elif emp_num and emp_num in by_code2:
                zengin_rec = by_code2[emp_num]
                match_method = "顧客コード2"

            # 3. 氏名カナ（カナ列がある場合）
            elif sr.name_kana:
                norm = _normalize_kana(sr.name_kana)
                for kana_key, zr_list in by_kana.items():
                    if _normalize_kana(kana_key) == norm:
                        if len(zr_list) == 1:
                            zengin_rec = zr_list[0]
                            match_method = "氏名カナ（要確認）"
                        else:
                            warnings.append(
                                f"[警告] 氏名カナ「{sr.name_kana}」が全銀データに複数存在します。"
                                f" 従業員番号「{emp_num}」は手動で紐づけてください。"
                            )
                        break

            # 4. 振込金額（一意の場合のみ）
            if zengin_rec is None and sr.net_pay > 0:
                candidates = by_amount.get(sr.net_pay, [])
                # まだ未マッチのものだけ
                unmatched_candidates = [zr for zr in candidates if id(zr) not in matched_ids]
                if len(unmatched_candidates) == 1:
                    zengin_rec = unmatched_candidates[0]
                    match_method = "振込金額（要確認）"

            if zengin_rec:
                matched_ids.add(id(zengin_rec))
                if "要確認" in match_method:
                    warnings.append(
                        f"[要確認] 「{sr.name}」（{emp_num}）を{match_method}で突合しました。"
                        f" 口座番号: {zengin_rec.account_number}"
                    )
            elif sr.net_pay > 0:
                # 支払いがあるのに口座が見つからない場合だけ警告
                warnings.append(
                    f"[未突合] 「{sr.name}」（{emp_num}）の振込口座が見つかりません。"
                )

            master_records.append(
                EmployeeMasterRecord(
                    employee_number=sr.employee_number,
                    name=sr.name,
                    name_kana=sr.name_kana,
                    employee_type=sr.employee_type,
                    bank_info=zengin_rec.to_bank_info() if zengin_rec else None,
                )
            )

        # 全銀データのみにある（給与CSV未掲載）レコード
        for zr in zengin_records:
            if id(zr) not in matched_ids:
                warnings.append(
                    f"[未突合] 全銀データの受取人「{zr.account_holder_kana}」"
                    f"（顧客コード1: {zr.customer_code1 or '空'}）が給与CSVに見つかりません。"
                )

        return master_records, warnings

    def save(self, output_path: str) -> Tuple[List[EmployeeMasterRecord], List[str]]:
        master_records, warnings = self.create()
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            if not master_records:
                return master_records, warnings
            writer = csv.DictWriter(f, fieldnames=list(master_records[0].to_dict().keys()))
            writer.writeheader()
            for rec in master_records:
                writer.writerow(rec.to_dict())

        return master_records, warnings


def _normalize_kana(text: str) -> str:
    half_to_full = str.maketrans(
        "ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ",
        "ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン゛゜",
    )
    return text.translate(half_to_full).replace(" ", "").replace("　", "").upper()
