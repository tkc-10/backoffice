"""
全銀フォーマット（総合振込 種別コード21）ライター

生成する全銀データ仕様:
  レコード長: 120 bytes / レコード
  エンコーディング: CP932
  レコード区切り: CRLF
  ヘッダ(1) → データ(2)×n → トレーラ(8) → エンド(9)
"""
import datetime
from typing import List, Optional, Tuple

from src.models.employee import BankInfo

RECORD_LENGTH = 120
ENCODING = "cp932"


def _field(text: str, width: int) -> bytes:
    """left-justified, space-padded to exactly `width` bytes."""
    encoded = text.encode(ENCODING, errors="replace")
    if len(encoded) > width:
        encoded = encoded[:width]
    return encoded + b" " * (width - len(encoded))


def _num(value: int, width: int) -> bytes:
    return str(value).zfill(width).encode(ENCODING)


def _make_header(info: dict) -> bytes:
    date_str = info.get("date") or datetime.date.today().strftime("%m%d")
    r = bytearray(RECORD_LENGTH)
    r[0:1]   = b"1"
    r[1:3]   = _field(info.get("type_code",    "21"),  2)
    r[3:4]   = _field(info.get("code_type",    "0"),   1)
    r[4:14]  = _field(info.get("client_code",  ""),   10)
    r[14:54] = _field(info.get("client_name",  ""),   40)
    r[54:58] = _field(date_str,                        4)
    r[58:62] = _field(info.get("bank_code",    ""),    4)
    r[62:77] = _field(info.get("bank_name",    ""),   15)
    r[77:80] = _field(info.get("branch_code",  ""),    3)
    r[80:95] = _field(info.get("branch_name",  ""),   15)
    r[95:96] = _field(info.get("account_type", "1"),   1)
    r[96:103]= _field(info.get("account_number",""),   7)
    r[103:120]= b" " * 17
    return bytes(r)


def _account_type_code(label_or_code: str) -> str:
    """'普通'→'1', '当座'→'2', '貯蓄'→'4'. Already-code strings pass through."""
    return {"普通": "1", "当座": "2", "貯蓄": "4"}.get(label_or_code, label_or_code)


def _make_data_record(bank_info: BankInfo, amount: int, customer_code1: str) -> bytes:
    acct_code = _account_type_code(bank_info.account_type)
    r = bytearray(RECORD_LENGTH)
    r[0:1]    = b"2"
    r[1:5]    = _field(bank_info.bank_code,           4)
    r[5:20]   = _field(bank_info.bank_name,          15)
    r[20:23]  = _field(bank_info.branch_code,         3)
    r[23:38]  = _field(bank_info.branch_name,        15)
    r[38:42]  = b" " * 4                              # dummy
    r[42:43]  = _field(acct_code,                     1)
    r[43:50]  = _field(bank_info.account_number,      7)
    r[50:80]  = _field(bank_info.account_holder_kana,30)
    r[80:90]  = _num(amount,                         10)
    r[90:91]  = b"0"                                  # new_code: 0=既存
    r[91:101] = _field(customer_code1,               10)
    r[101:111]= b" " * 10                             # customer_code2
    r[111:115]= b" " * 4                              # sending bank
    r[115:118]= b" " * 3                              # sending branch
    r[118:120]= b" " * 2
    return bytes(r)


def _make_trailer(count: int, total: int) -> bytes:
    r = bytearray(RECORD_LENGTH)
    r[0:1]   = b"8"
    r[1:7]   = _num(count,  6)
    r[7:19]  = _num(total, 12)
    r[19:120]= b" " * 101
    return bytes(r)


def _make_end() -> bytes:
    r = bytearray(RECORD_LENGTH)
    r[0:1]   = b"9"
    r[1:120] = b" " * 119
    return bytes(r)


def generate(
    records: List[Tuple[BankInfo, int, str]],
    header_info: Optional[dict] = None,
) -> bytes:
    """
    records: [(BankInfo, 振込金額, 顧客コード1), ...]
    header_info: ヘッダ情報の上書き（省略可）
    """
    lines = [_make_header(header_info or {})]
    count, total = 0, 0
    for bank_info, amount, code in records:
        lines.append(_make_data_record(bank_info, amount, code))
        count += 1
        total += amount
    lines.append(_make_trailer(count, total))
    lines.append(_make_end())
    return b"\r\n".join(lines)
