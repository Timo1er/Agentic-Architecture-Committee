const ReviewModule = {
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
      App.showToast("Please provide at least one input (Diagram, Terraform, or Cloud Services)", "danger");
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
