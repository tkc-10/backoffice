(() => {
  const $ = (id) => document.getElementById(id);

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
        throw new Error(err.detail || res.statusText);
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
        throw new Error(err.detail || res.statusText);
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
    $("master-info").textContent = "";
    $("zone-master").classList.remove("has-file");
    $("zengin-run-btn").disabled = true;
    $("zengin-results").classList.add("hidden");
    $("zengin-section").classList.remove("hidden");
  }

  // ===== タブ2ステップ3: 全銀データ生成 =====
  let masterFile = null;
  let cachedExpenseFile = null;  // 集計済みの経費ファイルを保持

  setupUploadZone("zone-master", "master", (f) => {
    masterFile = f;
    markFileSelected("zone-master", "master-info", f);
    $("zengin-run-btn").disabled = false;
  });

  $("zengin-run-btn").addEventListener("click", async () => {
    $("zengin-results").classList.add("hidden");
    $("zengin-error").classList.add("hidden");
    $("zengin-spinner").classList.remove("hidden");
    $("zengin-run-btn").disabled = true;

    const form = new FormData();
    form.append("expense_file", cachedExpenseFile);
    form.append("master_file", masterFile);

    let data;
    try {
      const res = await fetch("/api/expense-zengin", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || res.statusText);
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

    if (data.zengin_b64) {
      attachDownload("zengin-download-btn", data.zengin_b64, data.filename);
      $("zengin-download-btn").disabled = false;
    } else {
      $("zengin-download-btn").disabled = true;
    }

    $("zengin-results").classList.remove("hidden");
    $("zengin-results").scrollIntoView({ behavior: "smooth" });
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
