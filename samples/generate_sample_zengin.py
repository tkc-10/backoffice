"""サンプル全銀データ生成スクリプト（開発・テスト用）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RECORD_LEN = 120
ENCODING = "cp932"


def pad(s: str, length: int, char: str = " ") -> str:
    """全角文字を考慮しながら指定バイト長にパディングする"""
    encoded = s.encode(ENCODING, errors="replace")
    if len(encoded) > length:
        # バイト境界で切り捨て
        while len(encoded) > length:
            s = s[:-1]
            encoded = s.encode(ENCODING, errors="replace")
    pad_bytes = length - len(encoded)
    return encoded + (char.encode(ENCODING) * pad_bytes)


def make_record(*fields: tuple) -> bytes:
    """(value, byte_length) のタプルリストからレコードを生成する"""
    record = b""
    for value, length in fields:
        record += pad(str(value), length)
    assert len(record) == RECORD_LEN, f"レコード長エラー: {len(record)} != {RECORD_LEN}"
    return record


def build_header() -> bytes:
    return make_record(
        ("1", 1),           # データ区分
        ("21", 2),          # 種別コード (総合振込)
        ("0", 1),           # コード区分 (JIS)
        ("9999999999", 10), # 委託者コード
        ("サンプルカイシャ", 40),  # 委託者名
        ("0501", 4),        # 取組日 (5月1日)
        ("0001", 4),        # 仕向銀行番号
        ("ミツイスミトモ", 15),   # 仕向銀行名
        ("001", 3),         # 仕向支店番号
        ("ホンテン", 15),        # 仕向支店名
        ("1", 1),           # 預金種目
        ("1234567", 7),     # 口座番号
        (" " * 17, 17),     # ダミー
    )


def build_data(bank_code, bank_name, branch_code, branch_name,
               acc_type, acc_num, holder_kana, amount,
               customer_code1, customer_code2="") -> bytes:
    return make_record(
        ("2", 1),                      # データ区分
        (bank_code, 4),                # 被仕向銀行番号
        (bank_name, 15),               # 被仕向銀行名
        (branch_code, 3),              # 被仕向支店番号
        (branch_name, 15),             # 被仕向支店名
        (" " * 4, 4),                  # ダミー
        (acc_type, 1),                 # 預金種目
        (acc_num, 7),                  # 口座番号
        (holder_kana, 30),             # 受取人名
        (str(amount).zfill(10), 10),   # 振込金額
        ("0", 1),                      # 新規コード
        (customer_code1, 10),          # 顧客コード1（従業員番号）
        (customer_code2, 10),          # 顧客コード2
        ("0001", 4),                   # 振込銀行番号
        ("001", 3),                    # 振込支店番号
        (" " * 2, 2),                  # ダミー
    )


def build_trailer(count: int, total: int) -> bytes:
    return make_record(
        ("8", 1),                   # データ区分
        (str(count).zfill(6), 6),   # 合計件数
        (str(total).zfill(12), 12), # 合計金額
        (" " * 101, 101),           # ダミー
    )


def build_end() -> bytes:
    return make_record(
        ("9", 1),       # データ区分
        (" " * 119, 119), # ダミー
    )


if __name__ == "__main__":
    data_records = [
        # (銀行コード, 銀行名, 支店コード, 支店名, 預金種目, 口座番号, 受取人名カナ, 金額, 顧客コード1)
        ("0001", "ミツイスミトモ", "001", "ホンテン",   "1", "1111111", "ヤマダ タロウ",   263000, "E001"),
        ("0005", "ミツビシUFJ", "010", "シンジュク", "1", "2222222", "スズキ ハナコ",   212800, "E002"),
        ("0009", "ミズホ",      "020", "シブヤ",     "1", "3333333", "サトウ ジロウ",   115200, "E003"),
        ("0033", "ジャパンネット", "030", "ネット",   "1", "4444444", "タナカ サブロウ",  296000, "E004"),
        ("0035", "ソニー",      "040", "ネット",     "1", "5555555", "タカハシ シロウ",   81000, "E005"),
    ]

    records = [build_header()]
    total = 0
    for row in data_records:
        records.append(build_data(*row))
        total += row[7]
    records.append(build_trailer(len(data_records), total))
    records.append(build_end())

    out_path = os.path.join(os.path.dirname(__file__), "transfer_sample.txt")
    with open(out_path, "wb") as f:
        for rec in records:
            f.write(rec)

    print(f"生成完了: {out_path}")
    print(f"  件数: {len(data_records)}, 合計金額: {total:,} 円")
