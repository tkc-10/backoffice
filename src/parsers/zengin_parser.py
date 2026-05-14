"""
全銀フォーマット（総合振込 種別コード21）パーサー

レコード長: 120バイト固定長
エンコーディング: Shift-JIS (CP932) / UTF-8 自動判定

注意: 全銀フォーマットの位置指定はすべてバイト単位。
      日本語文字（全角2バイト）を含むため、デコード後の文字列インデックスではなく
      バイト列で直接スライスしてからデコードする。
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.models.employee import BankInfo

RECORD_TYPE_HEADER = b"1"
RECORD_TYPE_DATA = b"2"
RECORD_TYPE_TRAILER = b"8"
RECORD_TYPE_END = b"9"

RECORD_LENGTH = 120


@dataclass
class ZenginHeader:
    type_code: str       # 種別コード (21=総合振込)
    code_type: str       # コード区分
    client_code: str     # 委託者コード
    client_name: str     # 委託者名
    date: str            # 取組日 (MMDD)
    bank_code: str       # 仕向銀行番号
    bank_name: str       # 仕向銀行名
    branch_code: str     # 仕向支店番号
    branch_name: str     # 仕向支店名
    account_type: str    # 預金種目（依頼人）
    account_number: str  # 口座番号（依頼人）


@dataclass
class ZenginDataRecord:
    bank_code: str           # 被仕向銀行番号
    bank_name: str           # 被仕向銀行名
    branch_code: str         # 被仕向支店番号
    branch_name: str         # 被仕向支店名
    account_type: str        # 預金種目
    account_number: str      # 口座番号
    account_holder_kana: str # 受取人名
    transfer_amount: int     # 振込金額
    new_code: str            # 新規コード
    customer_code1: str      # 顧客コード1（従業員番号等）
    customer_code2: str      # 顧客コード2

    def to_bank_info(self) -> BankInfo:
        return BankInfo(
            bank_code=self.bank_code,
            bank_name=self.bank_name,
            branch_code=self.branch_code,
            branch_name=self.branch_name,
            account_type=self.account_type,
            account_number=self.account_number,
            account_holder_kana=self.account_holder_kana,
        )


@dataclass
class ZenginTrailer:
    total_count: int
    total_amount: int


class ZenginParser:
    """
    全銀フォーマットファイルをパースする。

    顧客コード1（customer_code1）に従業員番号が格納されている前提で
    銀行口座情報と従業員番号を紐づける。
    """

    def __init__(self, filepath: str, encoding: Optional[str] = None):
        self.filepath = filepath
        self.encoding = encoding or self._detect_encoding(filepath)

    @staticmethod
    def _detect_encoding(filepath: str) -> str:
        for enc in ["cp932", "utf-8-sig", "utf-8"]:
            try:
                with open(filepath, "rb") as f:
                    f.read().decode(enc)
                return enc
            except (UnicodeDecodeError, LookupError):
                continue
        return "cp932"

    def parse(self) -> Tuple[Optional[ZenginHeader], List[ZenginDataRecord], Optional[ZenginTrailer]]:
        with open(self.filepath, "rb") as f:
            raw = f.read()

        header = None
        data_records: List[ZenginDataRecord] = []
        trailer = None

        for rec_bytes in self._split_records(raw):
            if len(rec_bytes) < RECORD_LENGTH:
                continue
            rec_bytes = rec_bytes[:RECORD_LENGTH]
            record_type = rec_bytes[0:1]

            if record_type == RECORD_TYPE_HEADER:
                header = self._parse_header(rec_bytes)
            elif record_type == RECORD_TYPE_DATA:
                data_records.append(self._parse_data_record(rec_bytes))
            elif record_type == RECORD_TYPE_TRAILER:
                trailer = self._parse_trailer(rec_bytes)
            elif record_type == RECORD_TYPE_END:
                break

        return header, data_records, trailer

    def _split_records(self, raw: bytes) -> List[bytes]:
        """改行ありなし両対応でレコードを分割する"""
        if b"\r\n" in raw or (b"\n" in raw and raw.find(b"\n") < RECORD_LENGTH * 2):
            lines = raw.splitlines()
            return [line for line in lines if line.strip()]
        return [raw[i:i + RECORD_LENGTH] for i in range(0, len(raw), RECORD_LENGTH)]

    def _decode(self, b: bytes) -> str:
        return b.decode(self.encoding, errors="replace").strip()

    def _parse_header(self, r: bytes) -> ZenginHeader:
        # バイトオフセット（全銀フォーマット仕様書準拠）
        # [0]種別1 [1-2]種別コード2 [3]コード区分1 [4-13]委託者コード10
        # [14-53]委託者名40 [54-57]取組日4 [58-61]仕向銀行番号4
        # [62-76]仕向銀行名15 [77-79]仕向支店番号3 [80-94]仕向支店名15
        # [95]預金種目1 [96-102]口座番号7 [103-119]ダミー17
        return ZenginHeader(
            type_code=self._decode(r[1:3]),
            code_type=self._decode(r[3:4]),
            client_code=self._decode(r[4:14]),
            client_name=self._decode(r[14:54]),
            date=self._decode(r[54:58]),
            bank_code=self._decode(r[58:62]),
            bank_name=self._decode(r[62:77]),
            branch_code=self._decode(r[77:80]),
            branch_name=self._decode(r[80:95]),
            account_type=self._decode(r[95:96]),
            account_number=self._decode(r[96:103]),
        )

    def _parse_data_record(self, r: bytes) -> ZenginDataRecord:
        # バイトオフセット（全銀フォーマット仕様書準拠）
        # [0]種別1 [1-4]被仕向銀行番号4 [5-19]被仕向銀行名15
        # [20-22]被仕向支店番号3 [23-37]被仕向支店名15 [38-41]ダミー4
        # [42]預金種目1 [43-49]口座番号7 [50-79]受取人名30
        # [80-89]振込金額10 [90]新規コード1 [91-100]顧客コード1(10)
        # [101-110]顧客コード2(10) [111-114]振込銀行番号4 [115-117]振込支店番号3
        # [118-119]ダミー2
        amount_str = self._decode(r[80:90])
        return ZenginDataRecord(
            bank_code=self._decode(r[1:5]),
            bank_name=self._decode(r[5:20]),
            branch_code=self._decode(r[20:23]),
            branch_name=self._decode(r[23:38]),
            account_type=self._decode(r[42:43]),
            account_number=self._decode(r[43:50]),
            account_holder_kana=self._decode(r[50:80]),
            transfer_amount=int(amount_str) if amount_str.isdigit() else 0,
            new_code=self._decode(r[90:91]),
            customer_code1=self._decode(r[91:101]),
            customer_code2=self._decode(r[101:111]),
        )

    def _parse_trailer(self, r: bytes) -> ZenginTrailer:
        # [0]種別1 [1-6]合計件数6 [7-18]合計金額12 [19-119]ダミー101
        count_str = self._decode(r[1:7])
        amount_str = self._decode(r[7:19])
        return ZenginTrailer(
            total_count=int(count_str) if count_str.isdigit() else 0,
            total_amount=int(amount_str) if amount_str.isdigit() else 0,
        )
