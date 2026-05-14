(() => {
  const $ = (id) => document.getElementById(id);

  // ===== 保存済みマスタ状態 =====
  let savedMasterExists = false;

  async function loadMasterStatus() {
    try {
      const res = await fetch("/api/master-status");
      const d   = await res.json();
      savedMasterExists = d.exists;

      if (d.exists) {
        // Tab1 バッジ
        $("master-saved-badge").classList.remove("hidden");
        // Tab2 ステップ3
        $("saved-master-info").classList.remove("hidden");
        $("no-master-warn").classList.add("hidden");
        const dt = new Date(d.saved_at).toLocaleString("ja-JP", {
          year: "numeric", month: "2-digit", day: "2-digit",
          hour: "2-digit", minute: "2-digit",
        });
        $("saved-master-detail").textContent =
          `${dt} 作成 ／ ${d.total}名（口座突合: ${d.matched}名）`;
        // チェックボックスをチェック済みにしてアップロードエリアを折り畳む
        const cb = $("use-saved-master");
        if (cb) cb.checked = true;
        setMasterUploadVisible(false);
      } else {
        $("master-saved-badge").classList.add("hidden");
        $("saved-master-info").classList.add("hidden");
        $("no-master-warn").classList.remove("hidden");
        setMasterUploadVisible(true);
      }
    } catch (_) { /* サーバー未起動時は無視 */ }
  }

  function setMasterUploadVisible(visible) {
    $("master-upload-area").style.display = visible ? "" : "none";
    // 必須/任意バッジ切り替え
    if (savedMasterExists) {
      $("master-required-badge").classList.toggle("hidden",  true);
      $("master-optional-badge").classList.toggle("hidden", !visible);
    }
    updateZenginRunBtn();
  }

  // チェックボックスのイベント（DOMContentLoaded後にセット）
  document.addEventListener("DOMContentLoaded", () => {
    const cb = $("use-saved-master");
    if (cb) {
      cb.addEventListener("change", () => {
        setMasterUploadVisible(!cb.checked);
      });
    }
  });

  // タブ切り替え時にも状態を反映
  document.addEventListener("DOMContentLoaded", loadMasterStatus);

  // ===== タブ切り替え =====
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
      btn.classList.add("active");
      $("tab-" + btn.dataset.tab).classList.remove("hidden");
    });
  });

  // ===== 汎用ファイルアップロードゾーン =====
  function setupUploadZone(zoneId, inputId, onFile) {
    const zone = $(zoneId);
    const input = $(inputId);
    zone.addEventListener("click", () => input.click());
    input.addEventListener("change", () => { if (input.files[0]) onFile(input.files[0]); });
    zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("dragover"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
      if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
    });
  }

  function markFileSelected(zoneId, infoId, file) {
    $(zoneId).classList.add("has-file");
    $(infoId).textContent = "✔ " + file.name;
  }

  // ===== タブ1: 従業員マスタ =====
  let salaryFile = null, zenginFile = null;

  setupUploadZone("zone-salary", "salary", (f) => {
    salaryFile = f;
    markFileSelected("zone-salary", "salary-info", f);
    updateMasterBtn();
  });
  setupUploadZone("zone-zengin", "zengin", (f) => {
    zenginFile = f;
    markFileSelected("zone-zengin", "zengin-info", f);
    updateMasterBtn();
  });

  function updateMasterBtn() {
    $("run-btn").disabled = !(salaryFile && zenginFile);
  }

  $("run-btn").addEventListener("click", async () => {
    $("master-results").classList.add("hidden");
    $("master-error").classList.add("hidden");
    $("master-spinner").classList.remove("hidden");
    $("run-btn").disabled = true;

    const form = new FormData();
    form.append("salary_file", salaryFile);
    form.append("zengin_file", zenginFile);

    let data;
    try {
      const res = await fetch("/api/create-master", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const det = err.detail;
        throw new Error(Array.isArray(det) ? det.map((e) => e.msg || JSON.stringify(e)).join("、") : (det || res.statusText));
      }
      data = await res.json();
    } catch (e) {
      showBanner("master-error", e.message);
      return;
    } finally {
      $("master-spinner").classList.add("hidden");
      $("run-btn").disabled = false;
    }

    renderMasterResults(data);
    loadMasterStatus();  // 保存済みバッジ・経費タブの状態を更新
  });

  function renderMasterResults(data) {
    $("m-total").textContent = data.total;
    $("m-matched").textContent = data.matched;
    $("m-unmatched").textContent = data.unmatched;
    $("m-unmatched-card").classList.toggle("danger", data.unmatched > 0);

    const warnSection = $("warnings-section");
    if (data.warnings.length > 0) {
      warnSection.classList.remove("hidden");
      $("warnings-count").textContent = data.warnings.length;
      $("warnings-list").innerHTML = data.warnings.map((w) => {
        const cls = w.includes("未突合") ? "warn-error"
                  : w.includes("要確認") ? "warn-caution" : "warn-info";
        return `<li class="${cls}">${escHtml(w)}</li>`;
      }).join("");
    } else {
      warnSection.classList.add("hidden");
    }

    if (data.records.length > 0) {
      const cols = Object.keys(data.records[0]);
      $("master-table-head").innerHTML =
        `<tr>${cols.map((c) => `<th>${escHtml(c)}</th>`).join("")}</tr>`;
      $("master-table-body").innerHTML = data.records.map((row) => {
        const unmatched = !row["金融機関コード"];
        return `<tr class="${unmatched ? "unmatched" : ""}">` +
          cols.map((c) => `<td class="${(row[c] ?? "") === "" ? "empty" : ""}">${escHtml(String(row[c] ?? ""))}</td>`).join("") +
          `</tr>`;
      }).join("");
    }

    attachDownload("master-download-btn", data.csv_b64, data.filename);
    $("master-results").classList.remove("hidden");
    $("master-results").scrollIntoView({ behavior: "smooth" });
  }

  $("warnings-toggle").addEventListener("click", () => {
    $("warnings-list").classList.toggle("hidden");
    document.querySelector(".toggle-arrow").classList.toggle("open");
  });

  // ===== タブ2: 経費精算集計 =====
  let expenseFile = null;

  setupUploadZone("zone-expense", "expense", (f) => {
    expenseFile = f;
    markFileSelected("zone-expense", "expense-info", f);
    $("expense-run-btn").disabled = false;
    // 新しいファイルに差し替えたらステップ3をリセット
    $("zengin-section").classList.add("hidden");
    $("zengin-results").classList.add("hidden");
    masterFile = null;
    zenginRefFile = null;
    cachedExpenseFile = null;
  });

  $("expense-run-btn").addEventListener("click", async () => {
    $("expense-results").classList.add("hidden");
    $("expense-error").classList.add("hidden");
    $("expense-spinner").classList.remove("hidden");
    $("expense-run-btn").disabled = true;

    const form = new FormData();
    form.append("expense_file", expenseFile);

    let data;
    try {
      const res = await fetch("/api/expense-summary", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const det = err.detail;
        throw new Error(Array.isArray(det) ? det.map((e) => e.msg || JSON.stringify(e)).join("、") : (det || res.statusText));
      }
      data = await res.json();
    } catch (e) {
      showBanner("expense-error", e.message);
      return;
    } finally {
      $("expense-spinner").classList.add("hidden");
      $("expense-run-btn").disabled = false;
    }

    renderExpenseResults(data);
  });

  function renderExpenseResults(data) {
    $("e-people").textContent = data.rows.length + " 人";
    $("e-total").textContent = "¥" + data.total_amount.toLocaleString();

    $("expense-table-body").innerHTML = data.rows.map((r) =>
      `<tr>
        <td>${escHtml(r.name)}</td>
        <td class="num">${r.count}</td>
        <td class="num">¥${r.total_amount.toLocaleString()}</td>
      </tr>`
    ).join("") +
    `<tr class="total-row">
      <td><strong>合計</strong></td>
      <td class="num"><strong>${data.rows.reduce((s, r) => s + r.count, 0)}</strong></td>
      <td class="num"><strong>¥${data.total_amount.toLocaleString()}</strong></td>
    </tr>`;

    attachDownload("expense-download-btn", data.csv_b64, data.filename);
    $("expense-results").classList.remove("hidden");
    $("expense-results").scrollIntoView({ behavior: "smooth" });

    // ステップ3を表示（経費ファイルをキャッシュして全銀生成に使う）
    cachedExpenseFile = expenseFile;
    masterFile = null;
    zenginRefFile = null;
    $("master-info").textContent = "";
    $("zone-master").classList.remove("has-file");
    $("zengin-ref-info").textContent = "";
    $("zone-zengin-ref").classList.remove("has-file");
    $("zengin-results").classList.add("hidden");
    $("zengin-section").classList.remove("hidden");
    loadMasterStatus();  // 保存済みマスタの最新状態を反映
  }

  // ===== タブ2ステップ3: 全銀データ生成 =====
  let masterFile = null;
  let zenginRefFile = null;
  let cachedExpenseFile = null;  // 集計済みの経費ファイルを保持

  setupUploadZone("zone-master", "master", (f) => {
    masterFile = f;
    markFileSelected("zone-master", "master-info", f);
    updateZenginRunBtn();
  });

  setupUploadZone("zone-zengin-ref", "zengin-ref", (f) => {
    zenginRefFile = f;
    markFileSelected("zone-zengin-ref", "zengin-ref-info", f);
  });

  function updateZenginRunBtn() {
    // 保存済みマスタがあるか、ファイルがアップロード済みであれば有効
    $("zengin-run-btn").disabled = !savedMasterExists && !masterFile;
  }

  $("zengin-run-btn").addEventListener("click", async () => {
    $("zengin-results").classList.add("hidden");
    $("zengin-error").classList.add("hidden");
    $("zengin-spinner").classList.remove("hidden");
    $("zengin-run-btn").disabled = true;

    const form = new FormData();
    form.append("expense_file", cachedExpenseFile);
    if (masterFile) form.append("master_file", masterFile);
    if (zenginRefFile) form.append("zengin_ref_file", zenginRefFile);
    const dateVal = $("zengin-date").value;  // "YYYY-MM-DD" or ""
    if (dateVal) {
      // 全銀フォーマットの取組日は MMDD
      const [, mm, dd] = dateVal.split("-");
      form.append("transfer_date", mm + dd);
    }

    let data;
    try {
      const res = await fetch("/api/expense-zengin", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const detail = err.detail;
        const msg = Array.isArray(detail)
          ? detail.map((e) => e.msg || JSON.stringify(e)).join("、")
          : (detail || res.statusText);
        throw new Error(msg);
      }
      data = await res.json();
    } catch (e) {
      const banner = $("zengin-error");
      banner.textContent = "エラー: " + e.message;
      banner.classList.remove("hidden");
      return;
    } finally {
      $("zengin-spinner").classList.add("hidden");
      $("zengin-run-btn").disabled = false;
    }

    renderZenginResults(data);
  });

  function renderZenginResults(data) {
    const matchedCount   = data.matched.length;
    const unmatchedCount = data.unmatched.length;

    $("z-matched").textContent   = matchedCount + " 人";
    $("z-unmatched").textContent = unmatchedCount + " 人";
    $("z-total").textContent     = "¥" + data.total_amount.toLocaleString();
    $("z-unmatched-card").classList.toggle("danger", unmatchedCount > 0);

    const rows = [
      ...data.matched.map((r) => ({
        name:         r.name,
        count:        r.count,
        total_amount: r.total_amount,
        bank_name:    r.bank_name,
        account_tail: r.account_tail,
        ok:           true,
      })),
      ...data.unmatched.map((r) => ({
        name:         r.name,
        count:        r.count,
        total_amount: r.total_amount,
        bank_name:    r.reason,
        account_tail: "—",
        ok:           false,
      })),
    ];

    $("zengin-table-body").innerHTML = rows.map((r) =>
      `<tr class="${r.ok ? "" : "unmatched"}">
        <td>${escHtml(r.name)}</td>
        <td class="num">${r.count}</td>
        <td class="num">¥${r.total_amount.toLocaleString()}</td>
        <td>${escHtml(r.bank_name)}</td>
        <td class="num">${escHtml(r.account_tail)}</td>
        <td class="center">${r.ok ? "✅" : "❌"}</td>
      </tr>`
    ).join("");

    const dlBtn = $("zengin-download-btn");
    if (data.zengin_b64) {
      attachDownload("zengin-download-btn", data.zengin_b64, data.filename);
      dlBtn.disabled = false;
      dlBtn.title = data.header_sourced
        ? "委託者コード・仕向銀行情報は参照全銀ファイルから引き継いでいます"
        : "参照全銀ファイル未指定のためヘッダは空欄です";
      dlBtn.textContent = data.header_sourced
        ? "📥 全銀データをダウンロード（ヘッダ引き継ぎ済）"
        : "📥 全銀データをダウンロード（⚠️ ヘッダ空欄）";
    } else {
      dlBtn.disabled = true;
    }

    $("zengin-results").classList.remove("hidden");
    $("zengin-results").scrollIntoView({ behavior: "smooth" });
  }

  // ===== タブ3: 給与明細整理 =====
  let payrollFile = null;
  const TARGET_LABELS = ["基本給", "割増賃金合計", "通勤手当（非課税）"];

  setupUploadZone("zone-payroll", "payroll-upload", (f) => {
    payrollFile = f;
    markFileSelected("zone-payroll", "payroll-info", f);
    $("payroll-run-btn").disabled = false;
    $("payroll-results").classList.add("hidden");
  });

  $("payroll-run-btn").addEventListener("click", async () => {
    $("payroll-results").classList.add("hidden");
    $("payroll-error").classList.add("hidden");
    $("payroll-spinner").classList.remove("hidden");
    $("payroll-run-btn").disabled = true;

    const form = new FormData();
    form.append("payroll_file", payrollFile);

    let data;
    try {
      const res = await fetch("/api/payroll-summary", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        const det = err.detail;
        throw new Error(Array.isArray(det) ? det.map((e) => e.msg || JSON.stringify(e)).join("、") : (det || res.statusText));
      }
      data = await res.json();
    } catch (e) {
      const banner = $("payroll-error");
      banner.textContent = "エラー: " + e.message;
      banner.classList.remove("hidden");
      return;
    } finally {
      $("payroll-spinner").classList.add("hidden");
      $("payroll-run-btn").disabled = false;
    }

    renderPayrollResults(data);
  });

  function renderPayrollResults(data) {
    // 見つからなかった列の警告
    const warnEl = $("payroll-missing-warn");
    if (data.missing_columns.length > 0) {
      warnEl.textContent = "⚠️ 以下の列が見つからず集計できませんでした: "
        + data.missing_columns.join("、");
      warnEl.classList.remove("hidden");
    } else {
      warnEl.classList.add("hidden");
    }

    const cols = data.detected_columns;

    // ヘッダ構築
    $("payroll-table-head").innerHTML =
      `<tr><th>勤務・賃金設定</th><th class="num">人数</th>` +
      TARGET_LABELS.map((lbl) =>
        `<th class="num${cols.includes(lbl) ? "" : " col-missing"}">${escHtml(lbl)}</th>`
      ).join("") +
      `</tr>`;

    // 合計計算
    const totals = {};
    TARGET_LABELS.forEach((lbl) => { totals[lbl] = 0; });
    let totalCount = 0;

    // データ行
    const tbody = data.groups.map((g) => {
      totalCount += g.employee_count;
      TARGET_LABELS.forEach((lbl) => { totals[lbl] += g.amounts[lbl] ?? 0; });
      return `<tr>
        <td>${escHtml(g.employee_type)}</td>
        <td class="num">${g.employee_count}</td>
        ${TARGET_LABELS.map((lbl) => {
          const v = g.amounts[lbl] ?? 0;
          const na = !cols.includes(lbl);
          return `<td class="num${na ? " col-missing" : ""}">${na ? "—" : "¥" + v.toLocaleString()}</td>`;
        }).join("")}
      </tr>`;
    }).join("");

    // 合計行
    const totalRow = `<tr class="total-row">
      <td><strong>合計</strong></td>
      <td class="num"><strong>${totalCount}</strong></td>
      ${TARGET_LABELS.map((lbl) => {
        const na = !cols.includes(lbl);
        return `<td class="num${na ? " col-missing" : ""}"><strong>${na ? "—" : "¥" + totals[lbl].toLocaleString()}</strong></td>`;
      }).join("")}
    </tr>`;

    $("payroll-table-body").innerHTML = tbody + totalRow;

    attachDownload("payroll-download-btn", data.csv_b64, data.filename);
    $("payroll-results").classList.remove("hidden");
    $("payroll-results").scrollIntoView({ behavior: "smooth" });
  }

  // ===== ユーティリティ =====
  function showBanner(id, msg) {
    $("master-spinner").classList.add("hidden");
    $("expense-spinner").classList.add("hidden");
    $("run-btn").disabled = false;
    $("expense-run-btn").disabled = false;
    const el = $(id);
    el.textContent = "エラー: " + msg;
    el.classList.remove("hidden");
  }

  function attachDownload(btnId, b64, filename) {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "text/csv;charset=utf-8;" }));
    $(btnId).onclick = () => {
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click();
    };
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
})();
