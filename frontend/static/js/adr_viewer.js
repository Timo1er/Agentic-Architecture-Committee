/**
 * Architecture Review Board (ARB) - ADR Viewer Module
 * Provides an executive-grade, readable presentation of ADR decisions,
 * consequences, finops summaries, and critical risk matrices.
 */

const ADRViewerModule = {
  currentADR: null,
  currentReviewId: null,
  currentView: 'visual', // 'visual' | 'markdown' | 'raw'
  activeRiskFilter: 'ALL', // 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'
  isContextExpanded: false,
  expandedCells: new Set(),

  cleanText(val) {
    if (!val) return '';
    let str = String(val).trim();
    // Strip trailing JSON leakage if present
    str = str.replace(/",\s*"(?:decision|consequences|risk_matrix|alternatives|cost_breakdown)":[\s\S]*$/, '');
    str = str.replace(/^["'\s]+|["'\s]+$/g, '');
    return str.trim();
  },

  cleanRisks(rawRisks) {
    if (!Array.isArray(rawRisks)) return [];
    const clean = [];
    const seen = new Set();

    rawRisks.forEach((r, idx) => {
      if (!r || typeof r !== 'object') return;
      let desc = this.cleanText(r.risk || r.issue || '');
      
      // Discard corrupted JSON residue or entire markdown ADR dumped in cell
      if (!desc || desc.length < 5 || desc.includes('full_markdown_adr') || desc.includes('"risk_matrix"') || desc.includes('## 1. Title')) {
        return;
      }
      if (seen.has(desc.toLowerCase())) return;
      seen.add(desc.toLowerCase());

      let sev = String(r.severity || 'MEDIUM').toUpperCase().trim();
      if (sev.includes('HIGH')) sev = 'HIGH';
      else if (sev.includes('LOW')) sev = 'LOW';
      else sev = 'MEDIUM';

      let impact = this.cleanText(r.impact || 'Operational or security impact identified during review');
      let mitigation = this.cleanText(r.mitigation || r.remediation || 'Enforce defense-in-depth architecture guardrails');

      clean.push({
        id: `risk-cell-${idx}`,
        risk: desc,
        severity: sev,
        impact: impact,
        mitigation: mitigation
      });
    });

    return clean;
  },

  renderADR(adrData, reviewId) {
    this.currentReviewId = reviewId || "";
    this.expandedCells.clear();
    this.isContextExpanded = false;
    this.activeRiskFilter = 'ALL';
    this.currentView = 'visual';

    const container = document.getElementById("adr-content-area");
    if (!container) return;

    if (!adrData || adrData.status === "failed" || adrData.error) {
      container.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem;">
          <h3 style="color: #ef4444; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>⚠️</span> Architecture Review Evaluation Failed
          </h3>
          <p style="color: var(--text-secondary); margin-bottom: 0.8rem;">
            The multi-agent system encountered an error while synthesizing the architecture:
          </p>
          <pre style="background: #0f172a; padding: 1rem; border-radius: 6px; overflow-x: auto; color: #f87171; font-size: 0.85rem; border: 1px solid rgba(239, 68, 68, 0.3);">${adrData?.error || JSON.stringify(adrData, null, 2)}</pre>
        </div>
      `;
      const fId = document.getElementById("feedback-review-id");
      if (fId) fId.value = this.currentReviewId;
      return;
    }

    // Determine clean ADR number & prefix
    const adrNum = Number(adrData.adr_number) || 1;
    const adrPrefix = adrData.adr_prefix || (`ADR-${String(adrNum).padStart(3, '0')}`);
    
    // Normalize clean title
    let rawTitle = String(adrData.adr_title || adrData.title || "Cloud-Native HA Architecture").trim();
    rawTitle = rawTitle.split("\n")[0].trim();
    rawTitle = rawTitle.replace(/^#+\s*/, '').trim();
    // Strip old prefix if present in the string
    const cleanSubj = rawTitle.replace(/^ADR-\d+\s*:\s*/i, '').trim();
    const fullTitle = `${adrPrefix}: ${cleanSubj}`;

    // Normalize context & decision
    const cleanContext = this.cleanText(adrData.context) || "Comprehensive architectural evaluation completed across target cloud platforms.";
    const cleanDecision = this.cleanText(adrData.decision) || "Adopt cloud-native patterns enforcing high availability, security hardening, and cost efficiency.";

    // Normalize risks
    const cleanRiskList = this.cleanRisks(adrData.risk_matrix || []);

    // Normalize consequences
    let posCons = [];
    let negCons = [];
    if (adrData.consequences && typeof adrData.consequences === 'object') {
      posCons = Array.isArray(adrData.consequences.positive) ? adrData.consequences.positive.map(p => this.cleanText(p)).filter(Boolean) : [];
      negCons = Array.isArray(adrData.consequences.negative) ? adrData.consequences.negative.map(n => this.cleanText(n)).filter(Boolean) : [];
    } else if (Array.isArray(adrData.consequences)) {
      posCons = adrData.consequences.map(p => this.cleanText(p)).filter(Boolean);
    }
    if (posCons.length === 0) posCons = ["Decoupled asynchronous workflow enhances scalability and fault isolation.", "Managed services reduce operational overhead for infrastructure maintenance."];
    if (negCons.length === 0) negCons = ["Operational overhead for distributed observability and telemetry tracing."];

    // Normalize alternatives
    const rawAlts = adrData.alternatives_considered || adrData.alternatives || [];
    const cleanAlts = Array.isArray(rawAlts) ? rawAlts.map(a => ({
      alternative: this.cleanText(a.alternative || "Alternative Architecture"),
      reason_rejected: this.cleanText(a.reason_rejected || a._reason_rejected || "Rejected due to operational or cloud fit constraints.")
    })) : [];

    // Normalize cost
    const costObj = adrData.cost_breakdown || {};
    const monthlyCost = Number(costObj.estimated_monthly_usd) || 1500.0;
    const costSummary = this.cleanText(costObj.summary) || "Compute instances, managed datastores, and edge egress routing.";

    // Ensure full markdown is present with correct prefix
    let md = adrData.full_markdown_adr || adrData.full_markdown || "";
    if (!md || md.length < 50 || md.includes('"risk_matrix":')) {
      md = this.buildCleanMarkdown({
        prefix: adrPrefix,
        num: adrNum,
        title: cleanSubj,
        status: adrData.status || "PROPOSED",
        context: cleanContext,
        decision: cleanDecision,
        positive: posCons,
        negative: negCons,
        risks: cleanRiskList,
        cost: monthlyCost,
        costSummary: costSummary,
        alternatives: cleanAlts
      });
    } else {
      // Enforce the correct ADR prefix in the markdown header
      md = md.replace(/^#\s*ADR-\d+\s*:\s*/i, `# ${adrPrefix}: `);
      md = md.replace(/-\s*\*\*ADR Number:\*\*\s*\d+/i, `- **ADR Number:** ${adrNum}`);
    }

    this.currentADR = {
      adr_number: adrNum,
      adr_prefix: adrPrefix,
      adr_title: fullTitle,
      title_subject: cleanSubj,
      status: adrData.status || "PROPOSED",
      context: cleanContext,
      decision: cleanDecision,
      risk_matrix: cleanRiskList,
      consequences: { positive: posCons, negative: negCons },
      alternatives_considered: cleanAlts,
      cost_breakdown: { estimated_monthly_usd: monthlyCost, summary: costSummary },
      full_markdown_adr: md
    };

    const fId = document.getElementById("feedback-review-id");
    if (fId) fId.value = this.currentReviewId;

    this.renderCurrentView();
  },

  buildCleanMarkdown(data) {
    const riskRows = data.risks.map(r => `| ${r.risk.replace(/\|/g, '/')} | \`${r.severity}\` | ${r.impact.replace(/\|/g, '/')} | ${r.mitigation.replace(/\|/g, '/')} |`).join("\n");
    const pos = data.positive.map(p => `- ${p}`).join("\n");
    const neg = data.negative.map(n => `- ${n}`).join("\n");
    const alts = data.alternatives.map(a => `- **${a.alternative}:** ${a.reason_rejected}`).join("\n");

    return `# ${data.prefix}: ${data.title}

**ADR Number:** ${data.num}  
**Status:** \`${data.status}\`  
**Date:** Evaluated by Architecture Review Board  
**Target Clouds:** AWS, GCP, Azure, AliCloud, OVH  

---

## 1. Context & Business Drivers
${data.context}

---

## 2. Architectural Decision
${data.decision}

---

## 3. Consequences & Trade-offs
### Positive Outcomes
${pos}

### Negative Trade-offs
${neg}

---

## 4. Critical Risk Matrix
| Risk Description | Severity | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
${riskRows || '| No critical risks identified | `LOW` | Minimal | Standard continuous monitoring |'}

---

## 5. FinOps & Cost Projection
- **Estimated Monthly Cost:** $${Number(data.cost).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} USD
- **Key Cost Drivers:** ${data.costSummary}

---

## 6. Considered Alternatives & Rejection Rationale
${alts || '- None documented'}
`;
  },

  switchView(viewName) {
    this.currentView = viewName;
    this.renderCurrentView();
  },

  toggleContext() {
    this.isContextExpanded = !this.isContextExpanded;
    const body = document.getElementById("adr-context-body");
    const btn = document.getElementById("adr-context-toggle-btn");
    if (!body || !btn || !this.currentADR) return;

    if (this.isContextExpanded) {
      body.innerHTML = this.formatParagraphs(this.currentADR.context);
      btn.innerHTML = "Show less ▴";
    } else {
      body.innerHTML = this.formatParagraphs(this.currentADR.context.slice(0, 320) + "...");
      btn.innerHTML = "Show full context ▾";
    }
  },

  toggleCell(cellKey) {
    if (this.expandedCells.has(cellKey)) {
      this.expandedCells.delete(cellKey);
    } else {
      this.expandedCells.add(cellKey);
    }
    this.updateRiskTableBody();
  },

  filterRisks(filterName) {
    this.activeRiskFilter = filterName;
    document.querySelectorAll(".risk-filter-chip").forEach(chip => {
      chip.classList.toggle("active", chip.dataset.filter === filterName);
    });
    this.updateRiskTableBody();
  },

  formatParagraphs(text) {
    if (!text) return "";
    return text.split(/\n\s*\n/).map(p => `<p style="margin-bottom: 0.6rem;">${p.replace(/\n/g, '<br>')}</p>`).join("");
  },

  renderCurrentView() {
    const container = document.getElementById("adr-content-area");
    if (!container || !this.currentADR) return;

    const adr = this.currentADR;
    const status = adr.status || "PROPOSED";
    let statusClass = "status-completed";
    if (status === "REJECTED") statusClass = "status-rejected";
    else if (status === "REVISION_REQUIRED" || status === "REVISION_REQUESTED") statusClass = "status-revision";

    // View Toolbar HTML
    const toolbarHtml = `
      <div class="adr-view-toolbar">
        <div class="adr-tab-group">
          <button class="adr-tab-btn ${this.currentView === 'visual' ? 'active' : ''}" onclick="ADRViewerModule.switchView('visual')">
            📊 Executive View
          </button>
          <button class="adr-tab-btn ${this.currentView === 'markdown' ? 'active' : ''}" onclick="ADRViewerModule.switchView('markdown')">
            📄 Formatted Markdown
          </button>
          <button class="adr-tab-btn ${this.currentView === 'raw' ? 'active' : ''}" onclick="ADRViewerModule.switchView('raw')">
            💻 Raw Source
          </button>
        </div>

        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <button class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.35rem 0.75rem;" onclick="ADRViewerModule.copyMarkdown()">
            📋 Copy Markdown
          </button>
          <button class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.35rem 0.75rem;" onclick="ADRViewerModule.exportMarkdown()">
            📥 Download .md
          </button>
        </div>
      </div>
    `;

    // Header Card
    const headerHtml = `
      <div class="adr-header-card">
        <div class="adr-header-top">
          <div style="display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap;">
            <span class="adr-id-badge">${adr.adr_prefix}</span>
            <h2 class="adr-main-title">${adr.title_subject}</h2>
          </div>
          <span class="status-badge ${statusClass}">${adr.status}</span>
        </div>
        <div class="adr-meta-row">
          <span><strong>ADR Number:</strong> #${adr.adr_number}</span>
          <span>•</span>
          <span><strong>Evaluated By:</strong> Architecture Review Board</span>
          <span>•</span>
          <span><strong>Target Clouds:</strong></span>
          <span class="cloud-pill">AWS</span>
          <span class="cloud-pill">GCP</span>
          <span class="cloud-pill">Azure</span>
          <span class="cloud-pill">AliCloud</span>
          <span class="cloud-pill">OVH</span>
        </div>
      </div>
    `;

    if (this.currentView === 'markdown') {
      const renderedMd = (typeof marked !== 'undefined' && marked.parse) 
        ? marked.parse(adr.full_markdown_adr) 
        : `<pre style="white-space: pre-wrap; font-family: inherit;">${adr.full_markdown_adr}</pre>`;

      container.innerHTML = `
        ${headerHtml}
        ${toolbarHtml}
        <div class="adr-markdown-rendered">
          ${renderedMd}
        </div>
      `;
      return;
    }

    if (this.currentView === 'raw') {
      container.innerHTML = `
        ${headerHtml}
        ${toolbarHtml}
        <div style="position: relative;">
          <pre style="background: #080d1a; padding: 1.5rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.08); overflow-x: auto; color: #cbd5e1; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap;">${adr.full_markdown_adr.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</pre>
        </div>
      `;
      return;
    }

    // Visual View:
    // 1. Context & Business Drivers ("First text to long" fix)
    const contextText = adr.context;
    const isLongContext = contextText.length > 320;
    const displayedContext = (isLongContext && !this.isContextExpanded) 
      ? contextText.slice(0, 320) + "..." 
      : contextText;

    const contextHtml = `
      <div class="adr-section-card">
        <div class="adr-section-title">
          <span>📋</span> 1. Context & Business Drivers
        </div>
        <div id="adr-context-body" class="adr-text-body">
          ${this.formatParagraphs(displayedContext)}
        </div>
        ${isLongContext ? `
          <button id="adr-context-toggle-btn" class="cell-expand-btn" style="margin-top: 0.4rem;" onclick="ADRViewerModule.toggleContext()">
            ${this.isContextExpanded ? "Show less ▴" : "Show full context ▾"}
          </button>
        ` : ''}
      </div>
    `;

    // 2. Decision
    const decisionHtml = `
      <div class="adr-section-card">
        <div class="adr-section-title">
          <span>🎯</span> 2. Architectural Decision
        </div>
        <div class="adr-decision-box">
          ${this.formatParagraphs(adr.decision)}
        </div>
      </div>
    `;

    // 3. Consequences
    const consequencesHtml = `
      <div class="adr-section-card">
        <div class="adr-section-title">
          <span>⚖️</span> 3. Consequences & Trade-offs
        </div>
        <div class="adr-consequences-grid">
          <div class="consequence-box positive">
            <strong style="color: #34d399; font-size: 0.9rem; display: flex; align-items: center; gap: 0.4rem;">
              <span>✓</span> Positive Outcomes & Strengths
            </strong>
            <ul class="consequence-list">
              ${adr.consequences.positive.map(p => `<li>${p}</li>`).join("")}
            </ul>
          </div>
          <div class="consequence-box negative">
            <strong style="color: #f87171; font-size: 0.9rem; display: flex; align-items: center; gap: 0.4rem;">
              <span>⚠</span> Negative Trade-offs & Constraints
            </strong>
            <ul class="consequence-list">
              ${adr.consequences.negative.map(n => `<li>${n}</li>`).join("")}
            </ul>
          </div>
        </div>
      </div>
    `;

    // 4. Critical Risk Matrix Table ("text to long in CRITICAL RISK MATRIX table" fix)
    const allRisks = adr.risk_matrix;
    const highCount = allRisks.filter(r => r.severity === 'HIGH').length;
    const medCount = allRisks.filter(r => r.severity === 'MEDIUM').length;
    const lowCount = allRisks.filter(r => r.severity === 'LOW').length;

    const riskSectionHtml = `
      <div class="adr-section-card">
        <div class="risk-toolbar">
          <div class="adr-section-title" style="margin-bottom: 0;">
            <span>🛡️</span> 4. Critical Risk Matrix (${allRisks.length})
          </div>
          <div class="risk-filters">
            <button class="risk-filter-chip ${this.activeRiskFilter === 'ALL' ? 'active' : ''}" data-filter="ALL" onclick="ADRViewerModule.filterRisks('ALL')">
              All (${allRisks.length})
            </button>
            <button class="risk-filter-chip ${this.activeRiskFilter === 'HIGH' ? 'active' : ''}" data-filter="HIGH" onclick="ADRViewerModule.filterRisks('HIGH')">
              🔴 High (${highCount})
            </button>
            <button class="risk-filter-chip ${this.activeRiskFilter === 'MEDIUM' ? 'active' : ''}" data-filter="MEDIUM" onclick="ADRViewerModule.filterRisks('MEDIUM')">
              🟡 Medium (${medCount})
            </button>
            <button class="risk-filter-chip ${this.activeRiskFilter === 'LOW' ? 'active' : ''}" data-filter="LOW" onclick="ADRViewerModule.filterRisks('LOW')">
              🟢 Low (${lowCount})
            </button>
          </div>
        </div>

        <div class="risk-table-container">
          <table class="risk-table">
            <thead>
              <tr>
                <th style="width: 28%;">Risk Description</th>
                <th style="width: 12%; text-align: center;">Severity</th>
                <th style="width: 28%;">Impact</th>
                <th style="width: 32%;">Mitigation Strategy</th>
              </tr>
            </thead>
            <tbody id="adr-risk-tbody">
              <!-- populated dynamically -->
            </tbody>
          </table>
        </div>
      </div>
    `;

    // 5. FinOps
    const cost = adr.cost_breakdown;
    const finopsHtml = `
      <div class="adr-section-card">
        <div class="adr-section-title">
          <span>💰</span> 5. FinOps & Cost Projection
        </div>
        <div style="display: flex; gap: 1.5rem; align-items: flex-start; flex-wrap: wrap;">
          <div style="background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 1rem 1.5rem; min-width: 240px;">
            <div style="font-size: 0.8rem; text-transform: uppercase; color: #7dd3fc; font-weight: 700; margin-bottom: 0.2rem;">Estimated Monthly Cost</div>
            <div style="font-size: 1.6rem; font-weight: 800; color: #38bdf8;">
              $${Number(cost.estimated_monthly_usd).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} <span style="font-size: 0.85rem; font-weight: 500; color: var(--text-secondary);">USD</span>
            </div>
          </div>
          <div style="flex: 1; min-width: 280px; font-size: 0.9rem; line-height: 1.6; color: #cbd5e1; align-self: center;">
            <strong style="color: #f1f5f9;">Primary Cost Drivers:</strong> ${cost.summary}
          </div>
        </div>
      </div>
    `;

    // 6. Alternatives Considered
    const alts = adr.alternatives_considered;
    const altsHtml = `
      <div class="adr-section-card">
        <div class="adr-section-title">
          <span>🔄</span> 6. Considered Alternatives & Rejection Rationale
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin-top: 0.5rem;">
          ${alts.map(a => `
            <div style="background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 8px; padding: 1rem;">
              <div style="font-weight: 700; color: #e2e8f0; margin-bottom: 0.4rem; font-size: 0.92rem;">${a.alternative}</div>
              <div style="font-size: 0.85rem; color: #94a3b8; line-height: 1.5;">
                <span style="color: #f87171; font-weight: 600;">Rejected:</span> ${a.reason_rejected}
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `;

    container.innerHTML = `
      ${headerHtml}
      ${toolbarHtml}
      ${contextHtml}
      ${decisionHtml}
      ${consequencesHtml}
      ${riskSectionHtml}
      ${finopsHtml}
      ${altsHtml}
    `;

    this.updateRiskTableBody();
  },

  updateRiskTableBody() {
    const tbody = document.getElementById("adr-risk-tbody");
    if (!tbody || !this.currentADR) return;

    let risks = this.currentADR.risk_matrix;
    if (this.activeRiskFilter !== 'ALL') {
      risks = risks.filter(r => r.severity === this.activeRiskFilter);
    }

    if (risks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; padding: 1.5rem; color: var(--text-secondary); font-style: italic;">
            No ${this.activeRiskFilter !== 'ALL' ? this.activeRiskFilter : ''} risks recorded.
          </td>
        </tr>
      `;
      return;
    }

    const renderCell = (text, key) => {
      if (!text) return '<span style="color: var(--text-secondary);">-</span>';
      const isExpanded = this.expandedCells.has(key);
      const isLong = text.length > 130;
      if (!isLong || isExpanded) {
        return `
          <span>${text}</span>
          ${isLong ? `<button class="cell-expand-btn" onclick="ADRViewerModule.toggleCell('${key}')">[less]▴</button>` : ''}
        `;
      }
      return `
        <span>${text.slice(0, 125)}...</span>
        <button class="cell-expand-btn" onclick="ADRViewerModule.toggleCell('${key}')">[more]▾</button>
      `;
    };

    tbody.innerHTML = risks.map(r => {
      let badgeClass = 'badge-medium';
      let sevIcon = '🟡';
      if (r.severity === 'HIGH') {
        badgeClass = 'badge-high';
        sevIcon = '🔴';
      } else if (r.severity === 'LOW') {
        badgeClass = 'badge-low';
        sevIcon = '🟢';
      }

      return `
        <tr>
          <td><strong style="color: #f1f5f9;">${renderCell(r.risk, r.id + '-risk')}</strong></td>
          <td style="text-align: center;">
            <span class="severity-badge ${badgeClass}">${sevIcon} ${r.severity}</span>
          </td>
          <td>${renderCell(r.impact, r.id + '-impact')}</td>
          <td>${renderCell(r.mitigation, r.id + '-mitigation')}</td>
        </tr>
      `;
    }).join("");
  },

  copyMarkdown() {
    if (!this.currentADR || !this.currentADR.full_markdown_adr) {
      if (typeof App !== 'undefined' && App.showToast) {
        App.showToast("No ADR Markdown available to copy", "warning");
      }
      return;
    }
    const text = this.currentADR.full_markdown_adr;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        if (typeof App !== 'undefined' && App.showToast) {
          App.showToast("📋 ADR Markdown copied to clipboard!");
        }
      }).catch(() => this.fallbackCopy(text));
    } else {
      this.fallbackCopy(text);
    }
  },

  fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    if (typeof App !== 'undefined' && App.showToast) {
      App.showToast("📋 ADR Markdown copied to clipboard!");
    }
  },

  exportMarkdown() {
    if (!this.currentADR || !this.currentADR.full_markdown_adr) {
      if (typeof App !== 'undefined' && App.showToast) {
        App.showToast("No ADR to export", "danger");
      }
      return;
    }
    const text = this.currentADR.full_markdown_adr;
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const cleanFilename = `${this.currentADR.adr_prefix || "ADR"}_${(this.currentADR.title_subject || "Architecture").replace(/[^a-zA-Z0-9_-]/g, "_")}.md`;
    a.download = cleanFilename;
    a.click();
    URL.revokeObjectURL(url);
    if (typeof App !== 'undefined' && App.showToast) {
      App.showToast(`Exported ${cleanFilename}`);
    }
  }
};

