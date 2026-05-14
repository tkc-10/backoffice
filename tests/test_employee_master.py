import os
import sys
import tempfile
import csv

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.parsers.salary_csv_parser import SalaryCSVParser
from src.parsers.zengin_parser import ZenginParser
from src.employee_master import EmployeeMasterCreator

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")
SALARY_CSV = os.path.join(SAMPLES_DIR, "salary_sample.csv")
ZENGIN_TXT = os.path.join(SAMPLES_DIR, "transfer_sample.txt")


class TestSalaryCSVParser:
    def test_parse_sample(self):
        records = SalaryCSVParser(SALARY_CSV).parse()
        assert len(records) == 5

    def test_employee_number_and_name(self):
        records = SalaryCSVParser(SALARY_CSV).parse()
        assert records[0].employee_number == "E001"
        assert records[0].name == "山田 太郎"
        assert records[0].name_kana == "ヤマダ タロウ"

    def test_employee_types(self):
        records = SalaryCSVParser(SALARY_CSV).parse()
        types = {r.employee_number: r.employee_type for r in records}
        assert types["E001"] == "社員"
        assert types["E003"] == "アルバイト"

    def test_salary_amounts(self):
        records = SalaryCSVParser(SALARY_CSV).parse()
        r = records[0]  # E001
        assert r.base_salary == 280000
        assert r.overtime_pay == 35000
        assert r.net_pay == 263000

    def test_missing_required_column_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write("名前,基本給\n")
            f.write("山田,100000\n")
            path = f.name
        try:
            with pytest.raises(ValueError, match="必須列"):
                SalaryCSVParser(path).parse()
        finally:
            os.unlink(path)

    def test_skip_empty_rows(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write("従業員番号,氏名,氏名カナ,種別,基本給,残業代,各種手当,控除合計,差引支給額\n")
            f.write("E001,山田 太郎,ヤマダ タロウ,社員,280000,0,0,0,280000\n")
            f.write(",,,,,,,\n")  # 空行
            path = f.name
        try:
            records = SalaryCSVParser(path).parse()
            assert len(records) == 1
        finally:
            os.unlink(path)


class TestZenginParser:
    def test_parse_sample(self):
        _, data_records, trailer = ZenginParser(ZENGIN_TXT).parse()
        assert len(data_records) == 5
        assert trailer is not None
        assert trailer.total_count == 5

    def test_total_amount(self):
        _, data_records, trailer = ZenginParser(ZENGIN_TXT).parse()
        assert trailer.total_amount == sum(r.transfer_amount for r in data_records)

    def test_customer_code1_is_employee_number(self):
        _, data_records, _ = ZenginParser(ZENGIN_TXT).parse()
        codes = {r.customer_code1 for r in data_records}
        assert "E001" in codes
        assert "E005" in codes

    def test_bank_info_fields(self):
        _, data_records, _ = ZenginParser(ZENGIN_TXT).parse()
        r = data_records[0]  # E001
        assert r.bank_code == "0001"
        assert r.account_number == "1111111"
        assert r.account_type == "1"
        assert r.account_holder_kana == "ヤマダ タロウ"


class TestEmployeeMasterCreator:
    def test_full_match(self, tmp_path):
        out = str(tmp_path / "master.csv")
        creator = EmployeeMasterCreator(SALARY_CSV, ZENGIN_TXT)
        records, warnings = creator.save(out)

        assert len(records) == 5
        assert warnings == []

    def test_output_csv_columns(self, tmp_path):
        out = str(tmp_path / "master.csv")
        EmployeeMasterCreator(SALARY_CSV, ZENGIN_TXT).save(out)

        with open(out, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 5
        expected_cols = {"従業員番号", "氏名", "氏名カナ", "種別", "金融機関コード",
                         "金融機関名", "支店コード", "支店名", "預金種目", "口座番号", "受取人名（カナ）"}
        assert expected_cols == set(reader.fieldnames)

    def test_bank_info_in_output(self, tmp_path):
        out = str(tmp_path / "master.csv")
        EmployeeMasterCreator(SALARY_CSV, ZENGIN_TXT).save(out)

        with open(out, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))

        by_num = {r["従業員番号"]: r for r in rows}
        assert by_num["E001"]["金融機関コード"] == "0001"
        assert by_num["E001"]["口座番号"] == "1111111"
        assert by_num["E001"]["預金種目"] == "普通"
        assert by_num["E003"]["種別"] == "アルバイト"

    def test_unmatched_employee_warns(self, tmp_path):
        # 全銀データにないE999を給与CSVに追加したケース
        salary_path = str(tmp_path / "salary.csv")
        with open(salary_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["従業員番号", "氏名", "氏名カナ", "種別", "基本給", "残業代", "各種手当", "控除合計", "差引支給額"])
            writer.writerow(["E999", "未登録 太郎", "ミトウロク タロウ", "社員", 200000, 0, 0, 0, 200000])

        _, warnings = EmployeeMasterCreator(salary_path, ZENGIN_TXT).create()
        unmatched = [w for w in warnings if "E999" in w and "未突合" in w]
        assert len(unmatched) == 1

    def test_kana_fallback_match(self, tmp_path):
        """顧客コードが空の場合、氏名カナでフォールバック突合できること"""
        from samples.generate_sample_zengin import (
            build_header, build_data, build_trailer, build_end
        )
        # 顧客コード1が空の全銀データを生成
        zengin_path = str(tmp_path / "zengin.txt")
        records = [
            build_header(),
            build_data("0001", "ミツイスミトモ", "001", "ホンテン", "1", "9999999",
                       "テスト タロウ", 100000, ""),  # 顧客コード1が空
            build_trailer(1, 100000),
            build_end(),
        ]
        with open(zengin_path, "wb") as f:
            for rec in records:
                f.write(rec)

        salary_path = str(tmp_path / "salary.csv")
        with open(salary_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["従業員番号", "氏名", "氏名カナ", "種別", "基本給", "残業代", "各種手当", "控除合計", "差引支給額"])
            writer.writerow(["E010", "テスト 太郎", "テスト タロウ", "社員", 100000, 0, 0, 0, 100000])

        master_records, warnings = EmployeeMasterCreator(salary_path, zengin_path).create()
        assert len(master_records) == 1
        assert master_records[0].bank_info is not None
        assert master_records[0].bank_info.account_number == "9999999"
        # カナ突合なので要確認警告が出る
        assert any("要確認" in w for w in warnings)
