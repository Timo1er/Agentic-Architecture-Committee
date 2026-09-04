const BuildModule = {
  selectedCloud: "AWS",
  activeModality: "text",
  uploadedFile: null,
  extractedContent: "",
  currentProposal: null,
  diagramScale: 1.0,
  activeDiagramTab: "visual", // "visual" or "drawio"
  activeProposalTab: "overview", // "overview", "diagram", "components", "history"
  zoomLevel: 1.0,

  init() {
    this.setupCloudSelector();
    this.setupModalityTabs();
    this.setupDropzone();
    this.loadPastBuilds();
  },

  setupCloudSelector() {
    const cards = document.querySelectorAll(".cloud-card");
    cards.forEach(card => {
      card.addEventListener("click", () => {
        cards.forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        this.selectedCloud = card.getAttribute("data-cloud");
      });
    });
  },

  selectCloud(cloudName) {
    this.selectedCloud = cloudName;
    document.querySelectorAll(".cloud-card").forEach(c => {
      if (c.getAttribute("data-cloud") === cloudName) {
        c.classList.add("selected");
      } else {
        c.classList.remove("selected");
      }
    });
  },

  setupModalityTabs() {
    const buttons = document.querySelectorAll(".modality-btn");
    buttons.forEach(btn => {
      btn.addEventListener("click", () => {
        const modality = btn.getAttribute("data-modality");
        this.setModality(modality);
      });
    });
  },

  setModality(modality) {
    this.activeModality = modality;
    document.querySelectorAll(".modality-btn").forEach(b => {
      b.classList.toggle("active", b.getAttribute("data-modality") === modality);
    });

    const textSection = document.getElementById("build-text-section");
    const fileSection = document.getElementById("build-file-section");
    const fileInput = document.getElementById("build-file-input");
    const dropzoneTitle = document.getElementById("build-dropzone-title");
    const dropzoneSubtitle = document.getElementById("build-dropzone-subtitle");

    if (modality === "text") {
      textSection.style.display = "block";
      fileSection.style.display = "none";
    } else {
      textSection.style.display = "none";
      fileSection.style.display = "block";

      if (modality === "excel") {
        fileInput.accept = ".xlsx,.xls,.csv";
        dropzoneTitle.innerText = "Drop Excel Spreadsheet (.xlsx, .xls) here";
        dropzoneSubtitle.innerText = "Upload server inventories, database sizing sheets, or hardware specs";
      } else if (modality === "pdf") {
        fileInput.accept = ".pdf";
        dropzoneTitle.innerText = "Drop PDF Architecture Document (.pdf) here";
        dropzoneSubtitle.innerText = "Upload system specifications, RFPs, or compliance requirement documents";
      } else if (modality === "word") {
        fileInput.accept = ".docx,.doc";
        dropzoneTitle.innerText = "Drop Word Document (.docx, .doc) here";
        dropzoneSubtitle.innerText = "Upload technical design documents, requirements notes, or migration briefs";
      }
    }
  },

  setupDropzone() {
    const dropzone = document.getElementById("build-dropzone");
    const fileInput = document.getElementById("build-file-input");

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        this.handleFileUpload(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        this.handleFileUpload(e.target.files[0]);
      }
    });
  },

  async handleFileUpload(file) {
    this.uploadedFile = file;
    const previewContainer = document.getElementById("build-file-preview-card");
    const fileNameEl = document.getElementById("build-file-name");
    const fileSizeEl = document.getElementById("build-file-size");
    const previewTextEl = document.getElementById("build-file-preview-text");

    const sizeKb = (file.size / 1024).toFixed(1);
    fileNameEl.innerText = file.name;
    fileSizeEl.innerText = `${sizeKb} KB`;
    previewContainer.style.display = "flex";

    App.showToast(`Parsing ${file.name}...`);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const resp = await fetch("/api/build/extract-file", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${App.token}`
        },
        body: formData
      });

      if (!resp.ok) {
        throw new Error("Failed extracting text from uploaded file");
      }

      const data = await resp.json();
      this.extractedContent = data.extracted_text || "";
      previewTextEl.innerText = data.preview || "Text successfully extracted from document.";
      previewTextEl.parentElement.style.display = "block";
      App.showToast(`Extracted ${data.char_count} characters from ${file.name}`, "success");
    } catch (e) {
      console.warn("Server extraction error, reading locally:", e);
      const reader = new FileReader();
      reader.onload = (event) => {
        this.extractedContent = event.target.result || "";
        previewTextEl.innerText = (this.extractedContent).slice(0, 500) + "...";
        previewTextEl.parentElement.style.display = "block";
        App.showToast(`Loaded ${file.name} for transmission.`);
      };
      reader.readAsText(file);
    }
  },

  clearUploadedFile() {
    this.uploadedFile = null;
    this.extractedContent = "";
    document.getElementById("build-file-input").value = "";
    document.getElementById("build-file-preview-card").style.display = "none";
    document.getElementById("build-file-preview-box").style.display = "none";
  },

  loadExample(type) {
    const titleInput = document.getElementById("build-arch-title");
    const textArea = document.getElementById("build-input-text");
    const workloadSelect = document.getElementById("build-workload-type");
    const haSelect = document.getElementById("build-ha-level");
    const complianceSelect = document.getElementById("build-compliance");

    this.setModality("text");

    if (type === "aws_microservices") {
      this.selectCloud("AWS");
      titleInput.value = "Retail E-Commerce Platform Modernization";
      workloadSelect.value = "Microservices & Web Apps";
      haSelect.value = "Multi-AZ";
      complianceSelect.value = "PCI-DSS Level 1";
      textArea.value = `Current Infrastructure:
- 12 on-premise VMware ESXi virtual machines hosting a monolithic Tomcat Java application
- Oracle 19c enterprise database with 1.8TB transactional data
- Apache HTTP server front-end with SSL termination
- Redis standalone cache for user sessions
- Local SFTP server for merchant data batch ingestion

Target Cloud Requirements on AWS:
- Decompose monolith into containerized domain microservices (Catalog, Cart, Checkout, Inventory, Notification)
- High availability with multi-AZ zero-downtime rolling deployments
- Strict PCI-DSS Level 1 compliance for cardholder data processing
- Sub-50ms API response time under peak Black Friday sales traffic (up to 20,000 requests/second)
- Asynchronous decoupling for order placement and third-party logistics webhook calls
- Comprehensive audit trail with encrypted secrets management and Customer-Managed KMS keys`;
    } else if (type === "gcp_data") {
      this.selectCloud("GCP");
      titleInput.value = "Healthcare Clinical Analytics Lakehouse";
      workloadSelect.value = "Data Lakehouse & Analytics";
      haSelect.value = "Multi-AZ";
      complianceSelect.value = "HIPAA / HITECH";
      textArea.value = `Current Infrastructure:
- Legacy on-premise Hadoop/Spark 6-node cluster processing HL7 and FHIR clinical records
- MS SQL Server 2017 holding patient demographic and EHR records (850GB)
- Batch cron jobs transferring nightly patient encounter dumps via VPN

Target Cloud Requirements on GCP:
- Real-time streaming ingestion of HL7/FHIR telemetry from hospital clinic endpoints
- Strict HIPAA and BAA compliance with zero-trust data access and CMEK encryption
- Serverless or managed Kubernetes processing engine with horizontal auto-scaling
- Fast clinical doctor query portal with sub-second response times on cohort searches
- Long-term audit-grade clinical data archive with automated 7-year retention policies
- Zero trust identity integration with hospital Okta identity provider`;
    } else if (type === "azure_finance") {
      this.selectCloud("Azure");
      titleInput.value = "Core Banking Payment & Settlement Engine";
      workloadSelect.value = "Core Financial & Payment";
      haSelect.value = "Multi-Region Active-Active";
      complianceSelect.value = "PCI-DSS Level 1";
      textArea.value = `Current Infrastructure:
- On-prem mainframe and Windows Server cluster handling interbank wire transfers and card authorizations
- IBM MQ message bus coordinating credit card transaction clearing
- Microsoft SQL Server AlwaysOn Availability Group spanning two local data centers
- Hardware Security Modules (HSM) on-prem for PIN cryptographic verification

Target Cloud Requirements on Azure:
- Low-latency payment transaction authorization pipeline handling 5,000 transactions/second
- Multi-region active-active resilience with RTO < 5 minutes and RPO = 0
- Hardware-level HSM key management and Microsoft Entra ID managed identities
- Asynchronous durable message streaming with dead-letter queue guarantees
- Automated reconciliation ledger with immutable audit logging`;
    } else if (type === "ovh_sovereign") {
      this.selectCloud("OVH");
      titleInput.value = "European Public Sector Citizen Portal";
      workloadSelect.value = "Microservices & Web Apps";
      haSelect.value = "Multi-AZ";
      complianceSelect.value = "GDPR Sovereign (EU)";
      textArea.value = `Current Infrastructure:
- Hosted bare-metal servers in Paris data center running PHP/Symfony web portal and PostgreSQL
- Manual server provisioning and backup scripts executed via SSH

Target Cloud Requirements on OVHcloud:
- 100% European sovereign cloud posture immune to US CLOUD Act extraterritoriality
- Strict GDPR compliance with all patient and citizen data stored exclusively in France/Germany regions
- Managed Kubernetes for citizen authentication and digital tax filing microservices
- Managed PostgreSQL with triple-node multi-datacenter replication (Roubaix / Gravelines)
- S3-compatible sovereign high-performance object storage for citizen document scans
- Anti-DDoS protection with automated TLS certificates`;
    } else if (type === "alicloud_ecommerce") {
      this.selectCloud("AliCloud");
      titleInput.value = "Cross-Border APAC Logistics & E-Commerce";
      workloadSelect.value = "E-Commerce & Retail";
      haSelect.value = "Multi-Region Active-Active";
      complianceSelect.value = "Standard";
      textArea.value = `Current Infrastructure:
- Distributed branch servers across Singapore, Tokyo, and Hong Kong running bespoke logistic microservices
- MySQL replication with noticeable cross-border latency and frequent synchronization drops

Target Cloud Requirements on Alibaba Cloud:
- High-elasticity container cluster supporting Single's Day traffic bursts
- Cross-border multi-region deployment with localized caching in Singapore and Tokyo
- Low-latency transactional datastore with automated read/write splitting
- Reliable message queue handling order event propagation across APAC fulfillment centers
- High-durability object storage for shipping manifests and barcode label generation`;
    }

    App.showToast(`Loaded template for ${this.selectedCloud}!`);
  },

  async submitBuildProposal(event) {
    if (event) event.preventDefault();

    const title = document.getElementById("build-arch-title").value.trim();
    if (!title) {
      App.showToast("Please provide an Architecture Title", "danger");
      return;
    }

    const cloud = this.selectedCloud || "AWS";
    const provider = document.getElementById("build-llm-provider-select").value;
    const workloadType = document.getElementById("build-workload-type").value;
    const haLevel = document.getElementById("build-ha-level").value;
    const compliance = document.getElementById("build-compliance").value;
    const budgetTier = document.getElementById("build-budget-tier").value;
    const notes = document.getElementById("build-additional-notes").value.trim();

    let inputText = "";
    if (this.activeModality === "text") {
      inputText = document.getElementById("build-input-text").value.trim();
      if (!inputText) {
        App.showToast("Please enter requirements or description of your architecture.", "danger");
        return;
      }
      if (notes) inputText = `${notes}\n\n${inputText}`;
    } else {
      if (!this.uploadedFile && !this.extractedContent) {
        App.showToast(`Please select or drop a ${this.activeModality.toUpperCase()} file.`, "danger");
        return;
      }
      inputText = this.extractedContent || `Specifications from ${this.uploadedFile.name}`;
      if (notes) inputText = `Directives:\n${notes}\n\n${inputText}`;
    }

    // Show animated progress modal
    this.showProgressModal(cloud, title);

    try {
      const payload = {
        title: title,
        target_cloud: cloud,
        llm_provider: provider,
        input_modality: this.activeModality,
        input_text: inputText,
        input_filename: this.uploadedFile ? this.uploadedFile.name : null,
        workload_type: workloadType,
        high_availability: haLevel,
        compliance: compliance,
        budget_tier: budgetTier
      };

      const resp = await App.apiRequest("/api/build/propose", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      this.hideProgressModal();

      if (resp && resp.components) {
        this.currentProposal = resp;
        this.renderProposalView(resp);
        this.loadPastBuilds();
        App.showToast(`Architecture proposed for ${cloud}!`, "success");
      } else {
        throw new Error("Invalid proposal received from server.");
      }
    } catch (e) {
      this.hideProgressModal();
      console.error("Build proposal error:", e);
      App.showToast(`Error generating architecture: ${e.message || e}`, "danger");
    }
  },

  showProgressModal(cloud, title) {
    let modal = document.getElementById("build-progress-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "build-progress-modal";
      modal.className = "build-progress-modal";
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <div class="build-progress-card">
        <div class="build-spinner"></div>
        <h3 style="font-size: 1.25rem; margin-bottom: 0.5rem;">Synthesizing Target Architecture</h3>
        <p style="color: var(--text-secondary); font-size: 0.88rem;">Designing enterprise <b style="color: var(--accent);">${cloud}</b> cloud topology for <i>${title}</i></p>
        
        <div class="stepper-list">
          <div class="stepper-item active" id="step-1">
            <div class="stepper-icon">1</div>
            <span>Parsing workload requirements & inventory parameters...</span>
          </div>
          <div class="stepper-item" id="step-2">
            <div class="stepper-icon">2</div>
            <span>Cloud Solutions Architect mapping native ${cloud} managed services...</span>
          </div>
          <div class="stepper-item" id="step-3">
            <div class="stepper-icon">3</div>
            <span>SecOps Agent configuring zero-trust boundaries & KMS keys...</span>
          </div>
          <div class="stepper-item" id="step-4">
            <div class="stepper-icon">4</div>
            <span>FinOps Agent calculating resource sizing & monthly spend...</span>
          </div>
          <div class="stepper-item" id="step-5">
            <div class="stepper-icon">5</div>
            <span>Generating Visual Diagram & standard Draw.io XML topology...</span>
          </div>
        </div>
      </div>
    `;

    modal.style.display = "flex";

    // Progress animation timers
    setTimeout(() => {
      const s1 = document.getElementById("step-1");
      const s2 = document.getElementById("step-2");
      if (s1 && s2) { s1.className = "stepper-item done"; s2.className = "stepper-item active"; }
    }, 1200);

    setTimeout(() => {
      const s2 = document.getElementById("step-2");
      const s3 = document.getElementById("step-3");
      if (s2 && s3) { s2.className = "stepper-item done"; s3.className = "stepper-item active"; }
    }, 2800);

    setTimeout(() => {
      const s3 = document.getElementById("step-3");
      const s4 = document.getElementById("step-4");
      if (s3 && s4) { s3.className = "stepper-item done"; s4.className = "stepper-item active"; }
    }, 4500);

    setTimeout(() => {
      const s4 = document.getElementById("step-4");
      const s5 = document.getElementById("step-5");
      if (s4 && s5) { s4.className = "stepper-item done"; s5.className = "stepper-item active"; }
    }, 6200);
  },

  hideProgressModal() {
    const modal = document.getElementById("build-progress-modal");
    if (modal) modal.style.display = "none";
  },

  renderProposalView(data) {
    document.getElementById("build-input-card").style.display = "none";
    const resultCard = document.getElementById("build-results-card");
    resultCard.style.display = "block";

    // Title & Header info
    document.getElementById("build-res-title").innerText = data.title;
    document.getElementById("build-res-cloud-badge").innerText = data.target_cloud;
    document.getElementById("build-res-cloud-badge").className = `cloud-service-badge ${data.target_cloud.toLowerCase()}`;

    // KPI Cards
    const monthlyCost = Number(data.total_estimated_monthly_usd || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    document.getElementById("kpi-cost").innerText = `$${monthlyCost}`;
    document.getElementById("kpi-cloud").innerText = data.target_cloud;
    document.getElementById("kpi-components-count").innerText = (data.components || []).length;
    document.getElementById("kpi-ha").innerText = data.high_availability || "Multi-AZ";
    document.getElementById("kpi-compliance").innerText = data.compliance || "Standard";

    // Executive Summary
    if (data.executive_summary) {
      document.getElementById("build-exec-summary").innerText = data.executive_summary;
    }
    if (data.cost_drivers_summary) {
      document.getElementById("build-cost-summary").innerText = data.cost_drivers_summary;
    }

    // Render Components Table
    this.renderComponentsTable(data.components || [], data.target_cloud);

    // Render Diagram
    this.renderMermaidDiagram(data.diagram_mermaid || "");
    this.renderDrawIOXml(data.diagram_drawio_xml || "");

    // Render TAD Markdown
    this.renderTADMarkdown(data.full_tad_markdown || "");

    // Switch to Overview tab by default
    this.switchProposalTab("overview");
  },

  switchProposalTab(tabName) {
    this.activeProposalTab = tabName;
    document.querySelectorAll(".build-tab-btn").forEach(b => {
      b.classList.toggle("active", b.getAttribute("data-tab") === tabName);
    });

    document.getElementById("build-panel-overview").style.display = (tabName === "overview") ? "block" : "none";
    document.getElementById("build-panel-diagram").style.display = (tabName === "diagram") ? "block" : "none";
    document.getElementById("build-panel-components").style.display = (tabName === "components") ? "block" : "none";
    document.getElementById("build-panel-tad").style.display = (tabName === "tad") ? "block" : "none";

    if (tabName === "diagram") {
      // Re-trigger mermaid layout if needed
      setTimeout(() => {
        if (this.currentProposal && this.currentProposal.diagram_mermaid) {
          this.renderMermaidDiagram(this.currentProposal.diagram_mermaid);
        }
      }, 50);
    }
  },

  renderComponentsTable(components, cloud) {
    const tbody = document.getElementById("build-components-tbody");
    if (!tbody) return;

    if (!components || components.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 1.5rem; color: var(--text-secondary);">No components returned.</td></tr>';
      return;
    }

    let total = 0;
    let html = "";

    components.forEach((c, idx) => {
      const cost = Number(c.monthly_cost_usd || 0);
      total += cost;

      let tierClass = "compute";
      const t = (c.tier || "").toLowerCase();
      if (t.includes("edge") || t.includes("ingress")) tierClass = "edge";
      else if (t.includes("database") || t.includes("data") || t.includes("storage")) tierClass = "data";
      else if (t.includes("messaging") || t.includes("async") || t.includes("stream")) tierClass = "messaging";
      else if (t.includes("security") || t.includes("observability") || t.includes("governance")) tierClass = "security";

      const cloudClass = (cloud || "aws").toLowerCase();

      html += `
        <tr data-tier="${c.tier}">
          <td style="font-weight: 600; color: var(--text-primary);">${c.name}</td>
          <td><span class="tier-badge ${tierClass}">${c.tier}</span></td>
          <td><span class="cloud-service-badge ${cloudClass}">${c.cloud_service}</span></td>
          <td style="font-size: 0.82rem; color: var(--text-secondary); max-width: 220px;">${c.sizing}</td>
          <td style="font-size: 0.82rem; color: var(--text-primary); max-width: 260px;">${c.purpose}</td>
          <td style="font-size: 0.82rem; color: #34d399; max-width: 180px;">${c.ha_resilience}</td>
          <td style="font-size: 0.82rem; color: #f87171; max-width: 180px;">${c.security_networking}</td>
          <td style="font-weight: 700; color: #38bdf8; text-align: right; white-space: nowrap;">$${cost.toFixed(2)}</td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    document.getElementById("build-table-total-cost").innerText = `$${total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  },

  filterComponentsByTier(tier) {
    document.querySelectorAll(".tier-filter-pill").forEach(p => {
      p.classList.toggle("active", p.getAttribute("data-tier") === tier);
    });

    const rows = document.querySelectorAll("#build-components-tbody tr");
    rows.forEach(r => {
      const rowTier = r.getAttribute("data-tier") || "";
      if (tier === "all" || rowTier.toLowerCase().includes(tier.toLowerCase())) {
        r.style.display = "";
      } else {
        r.style.display = "none";
      }
    });
  },

  searchComponentsTable(query) {
    const q = query.toLowerCase().trim();
    const rows = document.querySelectorAll("#build-components-tbody tr");
    rows.forEach(r => {
      const text = r.innerText.toLowerCase();
      r.style.display = text.includes(q) ? "" : "none";
    });
  },

  exportComponentsCSV() {
    if (!this.currentProposal || !this.currentProposal.components) {
      App.showToast("No components to export", "danger");
      return;
    }

    const headers = ["Component Name", "Tier", "Cloud Service", "Sizing Specs", "Purpose", "HA Resilience", "Security & Networking", "Monthly Cost (USD)"];
    const rows = this.currentProposal.components.map(c => [
      `"${(c.name || '').replace(/"/g, '""')}"`,
      `"${(c.tier || '').replace(/"/g, '""')}"`,
      `"${(c.cloud_service || '').replace(/"/g, '""')}"`,
      `"${(c.sizing || '').replace(/"/g, '""')}"`,
      `"${(c.purpose || '').replace(/"/g, '""')}"`,
      `"${(c.ha_resilience || '').replace(/"/g, '""')}"`,
      `"${(c.security_networking || '').replace(/"/g, '""')}"`,
      c.monthly_cost_usd || 0
    ]);

    const csvContent = [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `${this.currentProposal.title.replace(/\s+/g, '_')}_components.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    App.showToast("Components exported to CSV!", "success");
  },

  copyComponentsJSON() {
    if (!this.currentProposal || !this.currentProposal.components) return;
    navigator.clipboard.writeText(JSON.stringify(this.currentProposal.components, null, 2));
    App.showToast("Components JSON copied to clipboard!", "success");
  },

  async renderMermaidDiagram(mermaidCode) {
    const container = document.getElementById("build-mermaid-viewport");
    if (!container) return;

    if (!mermaidCode || !mermaidCode.trim()) {
      container.innerHTML = '<p style="color: var(--text-secondary);">No diagram available.</p>';
      return;
    }

    try {
      const id = "build-mermaid-svg-" + Date.now();
      const { svg } = await mermaid.render(id, mermaidCode.trim());
      container.innerHTML = svg;
      this.zoomLevel = 1.0;
      this.applyDiagramZoom();
    } catch (e) {
      console.warn("Mermaid render error:", e);
      container.innerHTML = `<pre style="color: var(--text-secondary); white-space: pre-wrap; font-size: 0.85rem;">${mermaidCode}</pre>`;
    }
  },

  renderDrawIOXml(xmlCode) {
    const pre = document.getElementById("build-drawio-xml-pre");
    if (pre) {
      pre.innerText = xmlCode;
    }
  },

  setDiagramSubTab(mode) {
    this.activeDiagramTab = mode;
    document.querySelectorAll(".diagram-mode-btn").forEach(b => {
      b.classList.toggle("active", b.getAttribute("data-mode") === mode);
    });

    document.getElementById("build-diagram-visual-view").style.display = (mode === "visual") ? "block" : "none";
    document.getElementById("build-diagram-drawio-view").style.display = (mode === "drawio") ? "block" : "none";
  },

  zoomDiagram(delta) {
    this.zoomLevel = Math.max(0.4, Math.min(2.5, this.zoomLevel + delta));
    this.applyDiagramZoom();
  },

  resetDiagramZoom() {
    this.zoomLevel = 1.0;
    this.applyDiagramZoom();
  },

  applyDiagramZoom() {
    const svg = document.querySelector("#build-mermaid-viewport svg");
    if (svg) {
      svg.style.transform = `scale(${this.zoomLevel})`;
      svg.style.transformOrigin = "top center";
      svg.style.transition = "transform 0.15s ease-out";
    }
  },

  downloadDiagramSVG() {
    const svg = document.querySelector("#build-mermaid-viewport svg");
    if (!svg) {
      App.showToast("No diagram SVG to download", "danger");
      return;
    }

    const serializer = new XMLSerializer();
    const source = serializer.serializeToString(svg);
    const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(this.currentProposal ? this.currentProposal.title : 'architecture').replace(/\s+/g, '_')}_diagram.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    App.showToast("SVG diagram downloaded!", "success");
  },

  downloadDiagramPNG() {
    const svg = document.querySelector("#build-mermaid-viewport svg");
    if (!svg) {
      App.showToast("No diagram to export", "danger");
      return;
    }

    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svg);
    const img = new Image();
    const svgBlob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(svgBlob);

    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = (svg.clientWidth || 1200) * 2;
      canvas.height = (svg.clientHeight || 800) * 2;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#0f172a";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      const pngUrl = canvas.toDataURL("image/png");
      const link = document.createElement("a");
      link.download = `${(this.currentProposal ? this.currentProposal.title : 'architecture').replace(/\s+/g, '_')}_diagram.png`;
      link.href = pngUrl;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      App.showToast("PNG diagram downloaded!", "success");
    };
    img.src = url;
  },

  downloadDrawIOFile() {
    if (!this.currentProposal || !this.currentProposal.diagram_drawio_xml) {
      App.showToast("No Draw.io diagram available", "danger");
      return;
    }

    const xml = this.currentProposal.diagram_drawio_xml;
    const blob = new Blob([xml], { type: "application/xml" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${this.currentProposal.title.replace(/\s+/g, '_')}_${this.currentProposal.target_cloud}.drawio`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    App.showToast("Draw.io (.drawio) file downloaded!", "success");
  },

  openInDiagramsNet() {
    if (!this.currentProposal || !this.currentProposal.diagram_drawio_xml) {
      App.showToast("No Draw.io diagram available", "danger");
      return;
    }

    const xml = this.currentProposal.diagram_drawio_xml;
    // URL-safe deflate or base64 data encoding for diagrams.net
    try {
      const encodedData = encodeURIComponent(xml);
      const url = `https://app.diagrams.net/#R${encodedData}`;
      window.open(url, "_blank");
    } catch (e) {
      window.open("https://app.diagrams.net", "_blank");
    }
  },

  copyDrawIOXML() {
    if (!this.currentProposal || !this.currentProposal.diagram_drawio_xml) return;
    navigator.clipboard.writeText(this.currentProposal.diagram_drawio_xml);
    App.showToast("Draw.io XML copied to clipboard!", "success");
  },

  renderTADMarkdown(md) {
    const area = document.getElementById("build-tad-rendered-content");
    if (!area) return;

    if (typeof marked !== "undefined") {
      area.innerHTML = marked.parse(md);
    } else {
      area.innerText = md;
    }
  },

  downloadTADMarkdown() {
    if (!this.currentProposal || !this.currentProposal.full_tad_markdown) {
      App.showToast("No TAD document to download", "danger");
      return;
    }

    const blob = new Blob([this.currentProposal.full_tad_markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `TAD_${this.currentProposal.title.replace(/\s+/g, '_')}_${this.currentProposal.target_cloud}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    App.showToast("TAD Markdown downloaded!", "success");
  },

  copyTADMarkdown() {
    if (!this.currentProposal || !this.currentProposal.full_tad_markdown) return;
    navigator.clipboard.writeText(this.currentProposal.full_tad_markdown);
    App.showToast("TAD Markdown copied to clipboard!", "success");
  },

  printTAD() {
    window.print();
  },

  resetToNewBuild() {
    document.getElementById("build-input-card").style.display = "block";
    document.getElementById("build-results-card").style.display = "none";
    window.scrollTo({ top: 0, behavior: 'smooth' });
  },

  async loadPastBuilds() {
    const tbody = document.getElementById("build-history-tbody");
    if (!tbody) return;

    try {
      const builds = await App.apiRequest("/api/build/sessions");
      if (!builds || builds.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 1.5rem; color: var(--text-secondary);">No past architectures built yet.</td></tr>';
        return;
      }

      let html = "";
      builds.forEach(b => {
        const date = new Date(b.created_at).toLocaleDateString() + " " + new Date(b.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const cloudClass = (b.target_cloud || 'aws').toLowerCase();
        const cost = Number(b.total_estimated_monthly_usd || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const modalityIcon = b.input_modality === 'excel' ? '📊' : (b.input_modality === 'pdf' ? '📄' : (b.input_modality === 'word' ? '📘' : '📝'));

        html += `
          <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
            <td style="font-weight: 600; padding: 0.8rem 0.6rem;">${b.title}</td>
            <td style="padding: 0.8rem 0.6rem;"><span class="cloud-service-badge ${cloudClass}">${b.target_cloud}</span></td>
            <td style="padding: 0.8rem 0.6rem; font-size: 0.85rem; color: var(--text-secondary);">${modalityIcon} ${b.input_modality.toUpperCase()}</td>
            <td style="padding: 0.8rem 0.6rem; font-weight: 600; color: #38bdf8;">$${cost}/mo</td>
            <td style="padding: 0.8rem 0.6rem; font-size: 0.8rem; color: var(--text-secondary);">${date}</td>
            <td style="padding: 0.8rem 0.6rem; text-align: right; white-space: nowrap;">
              <button class="btn btn-secondary" style="padding: 0.25rem 0.6rem; font-size: 0.78rem; margin-right: 0.3rem;" onclick="BuildModule.viewPastBuild('${b.id}')">View</button>
              <button class="btn btn-danger" style="padding: 0.25rem 0.5rem; font-size: 0.78rem;" onclick="BuildModule.deletePastBuild('${b.id}')">✕</button>
            </td>
          </tr>
        `;
      });
      tbody.innerHTML = html;
    } catch (e) {
      console.warn("Could not load past builds:", e);
    }
  },

  async viewPastBuild(id) {
    try {
      const data = await App.apiRequest(`/api/build/sessions/${id}`);
      if (data) {
        this.currentProposal = data;
        this.renderProposalView(data);
        App.showToast(`Loaded architecture '${data.title}'`);
      }
    } catch (e) {
      App.showToast("Failed to load architecture session.", "danger");
    }
  },

  async deletePastBuild(id) {
    if (!confirm("Are you sure you want to delete this architecture proposal?")) return;
    try {
      await App.apiRequest(`/api/build/sessions/${id}`, { method: "DELETE" });
      App.showToast("Architecture proposal deleted.");
      this.loadPastBuilds();
    } catch (e) {
      App.showToast("Failed to delete proposal.", "danger");
    }
  }
};
