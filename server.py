import base64
import csv
import io
import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.employee_master import EmployeeMasterCreator
from src.parsers.expense_csv_parser import ExpenseCSVParser

app = FastAPI(title="バックオフィス管理ツール")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
