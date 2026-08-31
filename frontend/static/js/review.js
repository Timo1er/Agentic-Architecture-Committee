const ReviewModule = {
  currentDiagramBase64: null,
  currentDiagramMimeType: null,
  currentDiagramFilename: null,

  onDiagramFormatChange() {
    const format = document.getElementById("diagram-format-select").value;
    const textContainer = document.getElementById("diagram-text-container");
    const previewContainer = document.getElementById("diagram-preview-container");

    if (format === "image" || format === "pdf") {
      if (this.currentDiagramBase64) {
        textContainer.style.display = "none";
        previewContainer.style.display = "block";
      }
    } else {
      textContainer.style.display = "block";
      previewContainer.style.display = "none";
    }
  },

  handleDiagramUpload(inputId) {
    const fileInput = document.getElementById(inputId);
    if (!fileInput.files.length) return;
    const file = fileInput.files[0];
    const fileName = file.name.toLowerCase();
    const selectEl = document.getElementById("diagram-format-select");

    // Check if image or PDF
    if (file.type.startsWith("image/") || fileName.endsWith(".png") || fileName.endsWith(".jpg") || fileName.endsWith(".jpeg") || fileName.endsWith(".webp")) {
      selectEl.value = "image";
      const reader = new FileReader();
      reader.onload = (e) => {
        this.currentDiagramBase64 = e.target.result;
        this.currentDiagramMimeType = file.type || "image/png";
        this.currentDiagramFilename = file.name;

        // Show image preview
        document.getElementById("diagram-text-container").style.display = "none";
        const previewCont = document.getElementById("diagram-preview-container");
        previewCont.style.display = "block";

        const imgEl = document.getElementById("diagram-image-preview");
        imgEl.src = e.target.result;
        imgEl.style.display = "block";

        document.getElementById("diagram-pdf-preview").style.display = "none";
        document.getElementById("diagram-input").value = e.target.result;
        App.showToast(`Loaded Image: ${file.name}`);
      };
      reader.readAsDataURL(file);

    } else if (file.type === "application/pdf" || fileName.endsWith(".pdf")) {
      selectEl.value = "pdf";
      const reader = new FileReader();
      reader.onload = (e) => {
        this.currentDiagramBase64 = e.target.result;
        this.currentDiagramMimeType = "application/pdf";
        this.currentDiagramFilename = file.name;

        // Show PDF badge
        document.getElementById("diagram-text-container").style.display = "none";
        const previewCont = document.getElementById("diagram-preview-container");
        previewCont.style.display = "block";

        document.getElementById("diagram-image-preview").style.display = "none";
        const pdfEl = document.getElementById("diagram-pdf-preview");
        pdfEl.style.display = "block";
        document.getElementById("diagram-pdf-filename").innerText = file.name;

        document.getElementById("diagram-input").value = e.target.result;
        App.showToast(`Loaded PDF: ${file.name}`);
      };
      reader.readAsDataURL(file);

    } else {
      // Text / XML / Mermaid
      if (fileName.endsWith(".drawio") || fileName.endsWith(".xml")) {
        selectEl.value = "drawio";
      } else {
        selectEl.value = "mermaid";
      }
      this.clearDiagramUpload();
      this.handleFileUpload(inputId, "diagram-input");
    }
  },

  clearDiagramUpload() {
    this.currentDiagramBase64 = null;
    this.currentDiagramMimeType = null;
    this.currentDiagramFilename = null;
    document.getElementById("diagram-input").value = "";
    document.getElementById("diagram-file-input").value = "";
    document.getElementById("diagram-preview-container").style.display = "none";
    document.getElementById("diagram-text-container").style.display = "block";
    document.getElementById("diagram-image-preview").style.display = "none";
    document.getElementById("diagram-pdf-preview").style.display = "none";
    document.getElementById("diagram-format-select").value = "mermaid";
    App.showToast("Diagram reset to text input mode.");
  },

  async submitReview(event) {
    event.preventDefault();

    const title = document.getElementById("arch-title").value.trim();
    const llm_provider = document.getElementById("llm-provider-select").value;
    const diagram_text = document.getElementById("diagram-input").value.trim();
    const diagram_format = document.getElementById("diagram-format-select").value;
    const terraform_code = document.getElementById("terraform-input").value.trim();
    const services_text = document.getElementById("services-input").value.trim();

    // Collect selected target clouds
    const target_clouds = [];
    document.querySelectorAll("input[name='target-cloud']:checked").forEach(cb => {
      target_clouds.push(cb.value);
    });

    if (!title) {
      App.showToast("Please provide an Architecture Title", "danger");
      return;
    }

    if (!diagram_text && !terraform_code && !services_text) {
      App.showToast("Please provide at least one input (Diagram, Image/PDF, Terraform, or Cloud Services)", "danger");
      return;
    }

    // Switch to Review Board Tab and set Running state
    App.switchTab("tab-board");
    this.setAgentsState("running");
    this.addLogLine(`Starting evaluation for: "${title}" across [${target_clouds.join(", ")}]...`);
    this.addLogLine(`Routing to LLM Provider: ${llm_provider.toUpperCase()}`);

    try {
      const payload = {
        title,
        target_clouds,
        llm_provider,
        diagram_text: diagram_text || null,
        diagram_format,
        diagram_mime_type: this.currentDiagramMimeType,
        diagram_filename: this.currentDiagramFilename,
        terraform_code: terraform_code || null,
        services_text: services_text || null
      };

      const result = await App.apiRequest("/api/reviews", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      App.currentReviewId = result.review_id;
      this.setAgentsState("completed");

      if (result.logs) {
        result.logs.forEach(log => this.addLogLine(log));
      }

      this.addLogLine(`Validation checkpoint reached: ${result.status.toUpperCase()}`);
      App.showToast("Architecture evaluation completed! Check the ADR tab.");

      // Render ADR
      if (result.adr) {
        ADRViewerModule.renderADR(result.adr, result.review_id);
      }
    } catch (err) {
      this.setAgentsState("failed");
      this.addLogLine(`Execution Error: ${err.message}`);
    }
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
