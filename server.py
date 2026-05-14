import base64
import csv
import io
import os
import tempfile

from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.employee_master import EmployeeMasterCreator
from src.models.employee import BankInfo
from src.parsers.expense_csv_parser import ExpenseCSVParser
from src.parsers import zengin_writer
from src.parsers import payroll_csv_parser

app = FastAPI(title="精算データ処理ツール")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/api/create-master")
async def create_master(
    salary_file: UploadFile = File(...),
    zengin_file: UploadFile = File(...),
):
    with tempfile.TemporaryDirectory() as tmpdir:
        salary_path = os.path.join(tmpdir, "salary.csv")
        zengin_path = os.path.join(tmpdir, "zengin.txt")
        output_path = os.path.join(tmpdir, "master.csv")

        with open(salary_path, "wb") as f:
            f.write(await salary_file.read())
        with open(zengin_path, "wb") as f:
            f.write(await zengin_file.read())

        try:
            creator = EmployeeMasterCreator(salary_path, zengin_path)
            records, warnings = creator.save(output_path)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        with open(output_path, "rb") as f:
            csv_bytes = f.read()

    matched = sum(1 for r in records if r.bank_info is not None)

    return {
        "total": len(records),
        "matched": matched,
        "unmatched": len(records) - matched,
        "warnings": warnings,
        "records": [r.to_dict() for r in records],
        "csv_b64": base64.b64encode(csv_bytes).decode(),
        "filename": salary_file.filename.replace(".csv", "") + "_マスタ.csv",
    }


@app.post("/api/expense-summary")
async def expense_summary(expense_file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(await expense_file.read())
        tmp_path = tmp.name

    try:
        rows = ExpenseCSVParser(tmp_path).parse()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        os.unlink(tmp_path)

    total_amount = sum(r.total_amount for r in rows)

    # CSV生成
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["氏名", "申請件数", "合計精算額（円）"])
    for r in rows:
        writer.writerow([r.name, r.count, r.total_amount])
    writer.writerow(["合計", sum(r.count for r in rows), total_amount])
    csv_bytes = buf.getvalue().encode("utf-8-sig")

    return {
        "rows": [{"name": r.name, "count": r.count, "total_amount": r.total_amount} for r in rows],
        "total_amount": total_amount,
        "csv_b64": base64.b64encode(csv_bytes).decode(),
        "filename": expense_file.filename.replace(".csv", "") + "_精算集計.csv",
    }


@app.post("/api/expense-zengin")
async def expense_zengin(
    expense_file:    UploadFile = File(...),
    master_file:     UploadFile = File(...),
    zengin_ref_file: Optional[UploadFile] = File(default=None),
    transfer_date:   Optional[str] = None,  # MMDD 形式（例: "0520"）
):
    with (
        tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as et,
        tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as mt,
    ):
        et.write(await expense_file.read())
        mt.write(await master_file.read())
        expense_path, master_path = et.name, mt.name

    try:
        expense_rows = ExpenseCSVParser(expense_path).parse()
        master_rows  = _parse_master_csv(master_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        os.unlink(expense_path)
        os.unlink(master_path)

    # 名前正規化（スペース除去）
    def norm(s: str) -> str:
        return s.replace(" ", "").replace("　", "")

    master_by_name = {norm(r["name"]): r for r in master_rows}

    matched, unmatched = [], []
    zengin_records = []

    for er in expense_rows:
        key = norm(er.name)
        mr = master_by_name.get(key)
        if mr and mr["bank_info"]:
            matched.append({
                "name":         er.name,
                "count":        er.count,
                "total_amount": er.total_amount,
                "account_tail": mr["bank_info"].account_number[-4:],
                "bank_name":    mr["bank_info"].bank_name,
            })
            zengin_records.append((mr["bank_info"], er.total_amount, mr["employee_number"]))
        else:
            reason = "口座情報なし" if (mr and not mr["bank_info"]) else "マスタ未登録"
            unmatched.append({
                "name":         er.name,
                "count":        er.count,
                "total_amount": er.total_amount,
                "reason":       reason,
            })

    # 参照全銀ファイルからヘッダを抽出（指定された場合）
    header_info = {}
    if zengin_ref_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as rt:
            rt.write(await zengin_ref_file.read())
            ref_path = rt.name
        try:
            header_info = zengin_writer.extract_header_info(ref_path)
        finally:
            os.unlink(ref_path)

    if transfer_date:
        header_info["date"] = transfer_date

    zengin_bytes = zengin_writer.generate(zengin_records, header_info) if zengin_records else b""

    return {
        "matched":         matched,
        "unmatched":       unmatched,
        "total_amount":    sum(r["total_amount"] for r in matched),
        "header_sourced":  bool(header_info),
        "zengin_b64":      base64.b64encode(zengin_bytes).decode(),
        "filename":        expense_file.filename.replace(".csv", "") + "_経費精算振込.txt",
    }


def _parse_master_csv(path: str) -> list:
    """従業員マスタCSV（タブ1の出力）を読み込む"""
    ACCOUNT_LABEL = {"普通": "1", "当座": "2", "貯蓄": "4"}
    for enc in ["utf-8-sig", "utf-8", "cp932"]:
        try:
            with open(path, encoding=enc, newline="") as f:
                rows = list(csv.DictReader(f))
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        raise ValueError("マスタCSVのエンコーディングを判定できませんでした")

    result = []
    for row in rows:
        bank_code = (row.get("金融機関コード") or "").strip()
        acct_num  = (row.get("口座番号") or "").strip()
        bank_info = BankInfo(
            bank_code=bank_code,
            bank_name=(row.get("金融機関名") or "").strip(),
            branch_code=(row.get("支店コード") or "").strip(),
            branch_name=(row.get("支店名") or "").strip(),
            account_type=ACCOUNT_LABEL.get(
                (row.get("預金種目") or "").strip(),
                (row.get("預金種目") or "1").strip()
            ),
            account_number=acct_num,
            account_holder_kana=(row.get("受取人名（カナ）") or "").strip(),
        ) if bank_code and acct_num else None

        result.append({
            "employee_number": (row.get("従業員番号") or "").strip(),
            "name":            (row.get("氏名") or "").strip(),
            "bank_info":       bank_info,
        })
    return result


@app.post("/api/payroll-summary")
async def payroll_summary(payroll_file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(await payroll_file.read())
        tmp_path = tmp.name

    try:
        result = payroll_csv_parser.parse(tmp_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        os.unlink(tmp_path)

    labels = [lbl for lbl, _ in payroll_csv_parser.TARGET_COLUMNS]

    # CSV生成
    buf = io.StringIO()
    writer = csv.writer(buf)
    header_row = ["勤務・賃金設定", "人数"] + result.detected_columns
    writer.writerow(header_row)
    totals_row: dict[str, int] = {lbl: 0 for lbl in result.detected_columns}
    for g in result.groups:
        row = [g.employee_type, g.employee_count] + [g.amounts.get(lbl, 0) for lbl in result.detected_columns]
        writer.writerow(row)
        for lbl in result.detected_columns:
            totals_row[lbl] += g.amounts.get(lbl, 0)
    writer.writerow(["合計", sum(g.employee_count for g in result.groups)] +
                    [totals_row[lbl] for lbl in result.detected_columns])
    csv_bytes = buf.getvalue().encode("utf-8-sig")

    return {
        "groups": [
            {
                "employee_type":  g.employee_type,
                "employee_count": g.employee_count,
                "amounts":        {lbl: g.amounts.get(lbl, 0) for lbl in labels},
            }
            for g in result.groups
        ],
        "detected_columns": result.detected_columns,
        "missing_columns":  result.missing_columns,
        "csv_b64":   base64.b64encode(csv_bytes).decode(),
        "filename":  payroll_file.filename.replace(".csv", "") + "_給与集計.csv",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
