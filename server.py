import base64
import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.employee_master import EmployeeMasterCreator

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
