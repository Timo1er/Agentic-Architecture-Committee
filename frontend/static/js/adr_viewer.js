const ADRViewerModule = {
  currentADR: null,

  renderADR(adrData, reviewId) {
    this.currentADR = adrData;
    const container = document.getElementById("adr-content-area");
    
    let markdownText = adrData.full_markdown_adr || adrData.full_markdown || "";

    let risksHtml = "";
    if (adrData.risk_matrix && Array.isArray(adrData.risk_matrix)) {
      risksHtml = `
        <table class="risk-table">
          <thead>
            <tr>
              <th>Risk Description</th>
              <th>Severity</th>
              <th>Impact</th>
              <th>Mitigation Strategy</th>
            </tr>
          </thead>
          <tbody>
            ${adrData.risk_matrix.map(r => `
              <tr>
                <td>${r.risk || ""}</td>
                <td><span class="risk-${(r.severity || 'low').toLowerCase()}">${r.severity || 'LOW'}</span></td>
                <td>${r.impact || ""}</td>
                <td>${r.mitigation || ""}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    let alternativesHtml = "";
    if (adrData.alternatives_considered && Array.isArray(adrData.alternatives_considered)) {
      alternativesHtml = `
        <ul style="margin-left: 1.5rem; margin-top: 0.5rem;">
          ${adrData.alternatives_considered.map(a => `
            <li style="margin-bottom: 0.4rem;">
              <strong>${a.alternative}:</strong> ${a.reason_rejected}
            </li>
          `).join("")}
        </ul>
      `;
    }

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h2>${adrData.adr_title || adrData.title || "Architecture Decision Record"}</h2>
        <span class="status-badge status-completed">${adrData.status || "PROPOSED"}</span>
      </div>

      <div style="margin-bottom: 1.2rem;">
        <h4 style="color: var(--text-secondary); margin-bottom: 0.3rem;">1. CONTEXT</h4>
        <p>${adrData.context || "No context provided."}</p>
      </div>

      <div style="margin-bottom: 1.2rem;">
        <h4 style="color: var(--text-secondary); margin-bottom: 0.3rem;">2. DECISION</h4>
        <p>${adrData.decision || "Decision recorded."}</p>
      </div>

      <div style="margin-bottom: 1.2rem;">
        <h4 style="color: var(--text-secondary); margin-bottom: 0.3rem;">3. CONSEQUENCES</h4>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
          <div>
            <strong style="color: #34d399;">Positive:</strong>
            <ul style="margin-left: 1.2rem;">
              ${(adrData.consequences?.positive || []).map(p => `<li>${p}</li>`).join("")}
            </ul>
          </div>
          <div>
            <strong style="color: #f87171;">Negative / Trade-offs:</strong>
            <ul style="margin-left: 1.2rem;">
              ${(adrData.consequences?.negative || []).map(n => `<li>${n}</li>`).join("")}
            </ul>
          </div>
        </div>
      </div>

      <div style="margin-bottom: 1.2rem;">
        <h4 style="color: var(--text-secondary); margin-bottom: 0.3rem;">4. CRITICAL RISK MATRIX</h4>
        ${risksHtml}
      </div>

      <div style="margin-bottom: 1.2rem;">
        <h4 style="color: var(--text-secondary); margin-bottom: 0.3rem;">5. ALTERNATIVES CONSIDERED</h4>
        ${alternativesHtml}
      </div>
    `;

    // Also populate feedback review ID
    document.getElementById("feedback-review-id").value = reviewId || "";
  },

  exportMarkdown() {
    if (!this.currentADR) {
      App.showToast("No ADR to export", "danger");
      return;
    }
    const text = this.currentADR.full_markdown_adr || this.currentADR.full_markdown || JSON.stringify(this.currentADR, null, 2);
    const blob = new Blob([text], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${this.currentADR.adr_title || "ADR"}.md`;
    a.click();
    App.showToast("Exported ADR as Markdown");
  }
};
