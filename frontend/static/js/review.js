const ReviewModule = {
  currentDiagramBase64: null,
  currentDiagramMimeType: null,
  currentDiagramFilename: null,

  async loadPastReviews() {
    try {
      const tbody = document.getElementById("past-reviews-table-body");
      if (!tbody) return;
      
      const reviews = await App.apiRequest("/api/reviews");
      if (!reviews || reviews.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 1rem; color: var(--text-secondary);">No past reviews found.</td></tr>';
        return;
      }
      
      let html = "";
      reviews.forEach(r => {
        const date = new Date(r.created_at).toLocaleString();
        const clouds = r.target_clouds.join(", ") || "-";
        
        let statusColor = "var(--text-secondary)";
        if (r.status === "approved") statusColor = "#10b981";
        else if (r.status === "rejected") statusColor = "#ef4444";
        else if (r.status === "revision_requested") statusColor = "#f59e0b";
        else if (r.status === "awaiting_human_validation") statusColor = "#38bdf8";
        
        const pfxBadge = r.adr_prefix ? `<span class="past-adr-badge">${r.adr_prefix}</span>` : '';
        
        html += `
          <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
            <td style="padding: 0.8rem 0.5rem; font-weight: 500;">${pfxBadge}${r.title}</td>
            <td style="padding: 0.8rem 0.5rem; color: var(--text-secondary); font-size: 0.85rem;">${date}</td>
            <td style="padding: 0.8rem 0.5rem; font-size: 0.85rem;">${clouds}</td>
            <td style="padding: 0.8rem 0.5rem;">
              <span style="display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; border: 1px solid ${statusColor}; color: ${statusColor}; text-transform: uppercase;">
                ${r.status.replace(/_/g, ' ')}
              </span>
            </td>
            <td style="padding: 0.8rem 0.5rem; text-align: right;">
              <button class="btn btn-secondary" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;" onclick="ReviewModule.viewPastReview('${r.id}')">View</button>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = html;
    } catch (e) {
      console.error("Failed to load past reviews", e);
      const tbody = document.getElementById("past-reviews-table-body");
      if (tbody) tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 1rem; color: #ef4444;">Failed to load reviews.</td></tr>';
    }
  },

  async viewPastReview(id) {
    try {
      const result = await App.apiRequest(`/api/reviews/${id}`);
      App.currentReviewId = id;
      App.switchTab("tab-adr");
      if (result.adr && (result.adr.full_markdown || result.adr.decision || result.adr.title)) {
        ADRViewerModule.renderADR(result.adr, id);
      } else {
        document.getElementById("adr-content-area").innerHTML = '<p style="color: var(--text-secondary);">No ADR generated for this review yet.</p>';
      }
    } catch(e) {
      App.showToast("Failed to load review details.", "danger");
    }
  },

  onUnifiedFormatChange() {
    const format = document.getElementById("unified-format-select").value;
    const textContainer = document.getElementById("unified-text-container");
    const previewContainer = document.getElementById("unified-preview-container");
    const fileContainer = document.getElementById("unified-file-container");

    // Reset visibility
    textContainer.style.display = "none";
    previewContainer.style.display = "none";
    fileContainer.style.display = "none";

    if (format === "image" || format === "document") {
      fileContainer.style.display = "block";
      if (this.currentDiagramBase64) {
        previewContainer.style.display = "block";
      }
    } else if (format === "services") {
      textContainer.style.display = "block";
    } else {
      // mermaid, drawio, terraform
      textContainer.style.display = "block";
      fileContainer.style.display = "block";
    }
  },

  handleUnifiedUpload() {
    const fileInput = document.getElementById("unified-file-input");
    if (!fileInput.files.length) return;
    const file = fileInput.files[0];
    const fileName = file.name.toLowerCase();
    const selectEl = document.getElementById("unified-format-select");
    const format = selectEl.value;

    if (file.type.startsWith("image/") || fileName.endsWith(".png") || fileName.endsWith(".jpg") || fileName.endsWith(".jpeg") || fileName.endsWith(".webp")) {
      selectEl.value = "image";
      this.onUnifiedFormatChange();
      const reader = new FileReader();
      reader.onload = (e) => {
        this.currentDiagramBase64 = e.target.result;
        this.currentDiagramMimeType = file.type || "image/png";
        this.currentDiagramFilename = file.name;

        document.getElementById("unified-preview-container").style.display = "block";
        const imgEl = document.getElementById("unified-image-preview");
        imgEl.src = e.target.result;
        imgEl.style.display = "block";
        document.getElementById("unified-doc-preview").style.display = "none";
        document.getElementById("unified-input").value = e.target.result;
        App.showToast(`Loaded Image: ${file.name}`);
      };
      reader.readAsDataURL(file);

    } else if (file.type === "application/pdf" || fileName.endsWith(".pdf") || fileName.endsWith(".xlsx") || fileName.endsWith(".csv") || fileName.endsWith(".docx") || fileName.endsWith(".txt")) {
      selectEl.value = "document";
      this.onUnifiedFormatChange();
      const reader = new FileReader();
      reader.onload = (e) => {
        this.currentDiagramBase64 = e.target.result;
        this.currentDiagramMimeType = file.type || "application/octet-stream";
        this.currentDiagramFilename = file.name;

        document.getElementById("unified-preview-container").style.display = "block";
        document.getElementById("unified-image-preview").style.display = "none";
        const docEl = document.getElementById("unified-doc-preview");
        docEl.style.display = "block";
        document.getElementById("unified-doc-filename").innerText = file.name;
        document.getElementById("unified-input").value = e.target.result;
        App.showToast(`Loaded Document: ${file.name}`);
      };
      reader.readAsDataURL(file);

    } else {
      if (fileName.endsWith(".drawio") || fileName.endsWith(".xml")) {
        selectEl.value = "drawio";
      } else if (fileName.endsWith(".tf")) {
        selectEl.value = "terraform";
      } else {
        selectEl.value = "mermaid";
      }
      this.onUnifiedFormatChange();
      this.clearUnifiedUpload(false);
      this.handleFileUpload("unified-file-input", "unified-input");
    }
  },

  clearUnifiedUpload(resetSelect = true) {
    this.currentDiagramBase64 = null;
    this.currentDiagramMimeType = null;
    this.currentDiagramFilename = null;
    document.getElementById("unified-input").value = "";
    document.getElementById("unified-file-input").value = "";
    document.getElementById("unified-preview-container").style.display = "none";
    document.getElementById("unified-image-preview").style.display = "none";
    document.getElementById("unified-doc-preview").style.display = "none";
    if (resetSelect) {
      document.getElementById("unified-format-select").value = "mermaid";
      this.onUnifiedFormatChange();
      App.showToast("Input reset.");
    }
  },

  async submitReview(event) {
    event.preventDefault();

    const title = document.getElementById("arch-title").value.trim();
    const llm_provider = document.getElementById("llm-provider-select").value;
    const format = document.getElementById("unified-format-select").value;
    const rawValue = document.getElementById("unified-input").value.trim();

    let diagram_text = null;
    let diagram_format = null;
    let terraform_code = null;
    let services_text = null;

    if (format === "terraform") {
      terraform_code = rawValue;
    } else if (format === "services") {
      services_text = rawValue;
    } else {
      diagram_text = rawValue;
      diagram_format = (format === "document") ? "pdf" : format;
    }

    const target_clouds = [];
    document.querySelectorAll("input[name='target-cloud']:checked").forEach(cb => {
      target_clouds.push(cb.value);
    });

    if (!title) {
      App.showToast("Please provide an Architecture Title", "danger");
      return;
    }

    if (!diagram_text && !terraform_code && !services_text) {
      App.showToast("Please provide at least one input content.", "danger");
      return;
    }

    App.switchTab("tab-board");
    this.setAgentsState("running");
    this.addLogLine(`Starting evaluation for: "${title}" across [${target_clouds.join(", ")}]...`);
    this.addLogLine(`Routing to LLM Provider: ${llm_provider.toUpperCase()}`);

    try {
      const payload = {
        title,
        target_clouds,
        llm_provider,
        diagram_text,
        diagram_format,
        diagram_mime_type: this.currentDiagramMimeType,
        diagram_filename: this.currentDiagramFilename,
        terraform_code,
        services_text
      };

      const result = await App.apiRequest("/api/reviews", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      App.currentReviewId = result.review_id;
      const hasFailure = this.updateAgentBadges(result);

      if (result.logs) {
        result.logs.forEach(log => this.addLogLine(log));
      }

      if (hasFailure) {
        this.addLogLine(`[WARN] One or more agents encountered issues during execution.`);
        App.showToast("Review completed with warnings. Check Agent board & ADR tab.", "warning");
      } else {
        this.addLogLine(`Validation checkpoint reached: ${result.status.toUpperCase()}`);
        App.showToast("Architecture evaluation completed! Switching to ADR tab...");
        setTimeout(() => App.switchTab("tab-adr"), 1000);
      }

      // Render ADR
      if (result.adr) {
        ADRViewerModule.renderADR(result.adr, result.review_id);
      }
    } catch (err) {
      this.setAgentsState("failed");
      this.addLogLine(`Execution Error: ${err.message}`);
    }
  },

  updateAgentBadges(result) {
    const agents = [
      { id: "lead-badge", output: result.lead_architect_output },
      { id: "secops-badge", output: result.secops_output },
      { id: "finops-badge", output: result.finops_output },
      { id: "validator-badge", output: result.adr }
    ];
    let hasFailure = false;
    agents.forEach(({ id, output }) => {
      const el = document.getElementById(id);
      if (el) {
        if (output && (output.status === "failed" || output.error)) {
          el.className = "status-badge status-failed";
          el.innerText = "FAILED";
          hasFailure = true;
        } else {
          el.className = "status-badge status-completed";
          el.innerText = "COMPLETED";
        }
      }
    });
    return hasFailure;
  },

  setAgentsState(state) {
    const badges = ["lead-badge", "secops-badge", "finops-badge", "validator-badge"];
    badges.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.className = `status-badge status-${state}`;
        el.innerText = state.toUpperCase();
      }
    });
  },

  addLogLine(text) {
    const term = document.getElementById("terminal-logs");
    const line = document.createElement("div");
    line.className = "terminal-line";
    const time = new Date().toLocaleTimeString();
    line.innerText = `[${time}] ${text}`;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
  },

  handleFileUpload(inputId, textareaId) {
    const fileInput = document.getElementById(inputId);
    if (!fileInput.files.length) return;
    const file = fileInput.files[0];
    const reader = new FileReader();
    reader.onload = (e) => {
      document.getElementById(textareaId).value = e.target.result;
      App.showToast(`Loaded ${file.name}`);
    };
    reader.readAsText(file);
  }
};
