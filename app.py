import io
import tempfile
import os
import pandas as pd
import streamlit as st

from src.employee_master import EmployeeMasterCreator

st.set_page_config(page_title="バックオフィス管理", page_icon="🏢", layout="wide")

st.title("🏢 バックオフィス管理ツール")
st.caption("給与CSV と 全銀データ から従業員マスタを作成します")

st.header("① ファイルをアップロード")

col1, col2 = st.columns(2)

with col1:
    salary_file = st.file_uploader(
        "給与一覧 CSV",
        type=["csv"],
        help="従業員番号・氏名・氏名カナ・基本給などが含まれるCSVファイル",
    )
    if salary_file:
        try:
            df_salary = pd.read_csv(salary_file, encoding="utf-8-sig")
            st.success(f"{len(df_salary)} 件読み込みました")
            st.dataframe(df_salary, use_container_width=True, height=200)
        except Exception:
            salary_file.seek(0)
            df_salary = pd.read_csv(salary_file, encoding="cp932")
            st.success(f"{len(df_salary)} 件読み込みました")
            st.dataframe(df_salary, use_container_width=True, height=200)

with col2:
    zengin_file = st.file_uploader(
        "全銀データ（振込データ .txt）",
        type=["txt"],
        help="銀行システムから出力した全銀フォーマット（120バイト固定長）のファイル",
    )
    if zengin_file:
        st.success("ファイルを受け取りました")
        raw = zengin_file.read()
        st.text(f"ファイルサイズ: {len(raw):,} バイト  /  レコード数（推定）: {len(raw) // 120} 件")

st.divider()

st.header("② マスタを作成")

ready = salary_file is not None and zengin_file is not None
if not ready:
    st.info("給与CSV と 全銀データの両方をアップロードすると実行できます")

if st.button("マスタを作成する", disabled=not ready, type="primary"):
    salary_file.seek(0)
    zengin_file.seek(0)

    with tempfile.TemporaryDirectory() as tmpdir:
        salary_path = os.path.join(tmpdir, "salary.csv")
        zengin_path = os.path.join(tmpdir, "zengin.txt")
        output_path = os.path.join(tmpdir, "master.csv")

        with open(salary_path, "wb") as f:
            f.write(salary_file.read())
        with open(zengin_path, "wb") as f:
            f.write(zengin_file.read())

        try:
            creator = EmployeeMasterCreator(salary_path, zengin_path)
            records, warnings = creator.save(output_path)
        except ValueError as e:
            st.error(f"エラー: {e}")
            st.stop()

        # 結果を読み込む
        df_master = pd.read_csv(output_path, encoding="utf-8-sig")
        csv_bytes = df_master.to_csv(index=False).encode("utf-8-sig")

    st.header("③ 結果")

    matched = sum(1 for r in records if r.bank_info is not None)
    unmatched = len(records) - matched

    m1, m2, m3 = st.columns(3)
    m1.metric("総件数", f"{len(records)} 件")
    m2.metric("突合成功", f"{matched} 件")
    m3.metric("未突合", f"{unmatched} 件", delta=f"-{unmatched}" if unmatched else None,
              delta_color="inverse" if unmatched else "off")

    if warnings:
        with st.expander(f"⚠️ 警告・確認事項 （{len(warnings)} 件）", expanded=unmatched > 0):
            for w in warnings:
                if "未突合" in w:
                    st.warning(w)
                elif "要確認" in w:
                    st.info(w)
                else:
                    st.write(w)

    st.subheader("マスタデータ")

    # 未突合行をハイライト表示
    def highlight_unmatched(row):
        if not row.get("金融機関コード"):
            return ["background-color: #fff3cd"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_master.style.apply(highlight_unmatched, axis=1),
        use_container_width=True,
        height=400,
    )

    st.download_button(
        label="📥 マスタCSVをダウンロード",
        data=csv_bytes,
        file_name="employee_master.csv",
        mime="text/csv",
        type="primary",
    )
