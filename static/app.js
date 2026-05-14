(() => {
  const $ = (id) => document.getElementById(id);

  // --- ファイル選択 ---
  let salaryFile = null;
  let zenginFile = null;

  function setupUploadZone(zoneId, inputId, onFile) {
    const zone = $(zoneId);
    const input = $(inputId);

    zone.addEventListener("click", () => input.click());

    input.addEventListener("change", () => {
      if (input.files[0]) onFile(input.files[0]);
    });

    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      zone.classList.add("dragover");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
      if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
    });
  }

  function setFile(type, file) {
    const zone = $(`zone-${type}`);
    const info = $(`${type}-info`);
    zone.classList.add("has-file");
    info.textContent = `✔ ${file.name}`;
    if (type === "salary") salaryFile = file;
    else zenginFile = file;
    updateButton();
  }

  setupUploadZone("zone-salary",  "salary",  (f) => setFile("salary",  f));
  setupUploadZone("zone-zengin",  "zengin",  (f) => setFile("zengin",  f));

  function updateButton() {
    $("run-btn").disabled = !(salaryFile && zenginFile);
  }

  // --- マスタ作成 ---
  $("run-btn").addEventListener("click", async () => {
    $("results").classList.add("hidden");
    $("error-banner").classList.add("hidden");
    $("spinner").classList.remove("hidden");
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
      showError(e.message);
      return;
    } finally {
      $("spinner").classList.add("hidden");
      $("run-btn").disabled = false;
    }

    renderResults(data);
  });

  function showError(msg) {
    $("spinner").classList.add("hidden");
    $("run-btn").disabled = false;
    const el = $("error-banner");
    el.textContent = `エラー: ${msg}`;
    el.classList.remove("hidden");
  }

  // --- 結果描画 ---
  function renderResults(data) {
    // メトリクス
    $("m-total").textContent = data.total;
    $("m-matched").textContent = data.matched;
    $("m-unmatched").textContent = data.unmatched;
    const unmatchedCard = $("m-unmatched-card");
    unmatchedCard.classList.toggle("danger", data.unmatched > 0);

    // 警告
    const warnSection = $("warnings-section");
    if (data.warnings.length > 0) {
      warnSection.classList.remove("hidden");
      $("warnings-count").textContent = data.warnings.length;
      const list = $("warnings-list");
      list.innerHTML = data.warnings.map((w) => {
        const cls = w.includes("未突合") ? "warn-error"
                  : w.includes("要確認") ? "warn-caution"
                  : "warn-info";
        return `<li class="${cls}">${escHtml(w)}</li>`;
      }).join("");
    } else {
      warnSection.classList.add("hidden");
    }

    // テーブル
    if (data.records.length > 0) {
      const cols = Object.keys(data.records[0]);

      $("table-head").innerHTML =
        `<tr>${cols.map((c) => `<th>${escHtml(c)}</th>`).join("")}</tr>`;

      $("table-body").innerHTML = data.records.map((row) => {
        const isUnmatched = !row["金融機関コード"];
        const tds = cols.map((c) => {
          const v = row[c] ?? "";
          return `<td class="${v === "" ? "empty" : ""}">${escHtml(String(v))}</td>`;
        }).join("");
        return `<tr class="${isUnmatched ? "unmatched" : ""}">${tds}</tr>`;
      }).join("");
    }

    // ダウンロード
    const csvBytes = Uint8Array.from(atob(data.csv_b64), (c) => c.charCodeAt(0));
    const blob = new Blob([csvBytes], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const btn = $("download-btn");
    btn.onclick = () => {
      const a = document.createElement("a");
      a.href = url;
      a.download = data.filename;
      a.click();
    };

    $("results").classList.remove("hidden");
    $("results").scrollIntoView({ behavior: "smooth" });
  }

  // 警告アコーディオン
  $("warnings-toggle").addEventListener("click", () => {
    const list = $("warnings-list");
    const arrow = document.querySelector(".toggle-arrow");
    list.classList.toggle("hidden");
    arrow.classList.toggle("open");
  });

  function escHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
})();
