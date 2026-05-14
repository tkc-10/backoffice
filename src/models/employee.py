from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BankInfo:
    """振込先口座情報"""
    bank_code: str           # 金融機関コード (4桁)
    bank_name: str           # 金融機関名
    branch_code: str         # 支店コード (3桁)
    branch_name: str         # 支店名
    account_type: str        # 預金種目 (1=普通, 2=当座, 4=貯蓄)
    account_number: str      # 口座番号 (7桁)
    account_holder_kana: str # 受取人名（カナ）

    @property
    def account_type_label(self) -> str:
        return {"1": "普通", "2": "当座", "4": "貯蓄"}.get(self.account_type, self.account_type)


@dataclass
class SalaryRecord:
    """給与明細レコード"""
    employee_number: str     # 従業員番号
    name: str                # 氏名
    name_kana: str           # 氏名カナ
    employee_type: str       # 種別（社員/アルバイト等）
    base_salary: int         # 基本給
    overtime_pay: int        # 残業代
    allowances: int          # 各種手当合計
    deductions: int          # 控除合計
    net_pay: int             # 差引支給額
    extra: dict = field(default_factory=dict)  # その他の列


@dataclass
class EmployeeMasterRecord:
    """従業員マスタレコード"""
    employee_number: str
    name: str
    name_kana: str
    employee_type: str
    bank_info: Optional[BankInfo] = None

    def to_dict(self) -> dict:
        d = {
            "従業員番号": self.employee_number,
            "氏名": self.name,
            "氏名カナ": self.name_kana,
            "種別": self.employee_type,
            "金融機関コード": "",
            "金融機関名": "",
            "支店コード": "",
            "支店名": "",
            "預金種目": "",
            "口座番号": "",
            "受取人名（カナ）": "",
        }
        if self.bank_info:
            d.update({
                "金融機関コード": self.bank_info.bank_code,
                "金融機関名": self.bank_info.bank_name,
                "支店コード": self.bank_info.branch_code,
                "支店名": self.bank_info.branch_name,
                "預金種目": self.bank_info.account_type_label,
                "口座番号": self.bank_info.account_number,
                "受取人名（カナ）": self.bank_info.account_holder_kana,
            })
        return d
