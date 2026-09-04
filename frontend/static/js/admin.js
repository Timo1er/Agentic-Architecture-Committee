const AdminModule = {
  currentSubTab: "admin-sub-users",
  cachedUsers: [],
  cachedGuidelines: [],
  cachedSources: [],

  escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  },

  async loadAdminData() {
    this.loadStats();
    this.loadUsers();
    this.loadAuditLogs();
    this.loadProviders();
    this.loadGuidelines();
    this.loadSources();
    this.loadSSO();
  },

  switchAdminSubTab(tabId) {
    this.currentSubTab = tabId;
    document.querySelectorAll(".admin-sub-tab").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-subtab") === tabId);
    });
    document.querySelectorAll(".admin-sub-content").forEach(el => {
      el.style.display = el.id === tabId ? "block" : "none";
    });
  },

  // --------------------------------------------------------------------------
  // User Management & Statistics
  // --------------------------------------------------------------------------
  async loadStats() {
    try {
      const stats = await App.apiRequest("/api/admin/stats");
      const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val !== undefined ? val : "-";
      };
      setVal("stat-total-users", stats.total_users);
      setVal("stat-active-users", stats.active_users);
      setVal("stat-admin-users", stats.admin_users);
      setVal("stat-reviewer-users", stats.reviewer_users);
      setVal("stat-total-reviews", stats.total_reviews);
    } catch (e) {
      console.warn("Failed to load admin stats:", e);
    }
  },

  async loadUsers() {
    const tableBody = document.getElementById("admin-users-table-body");
    if (!tableBody) return;

    const search = document.getElementById("user-search-input")?.value?.trim() || "";
    const roleFilter = document.getElementById("user-role-filter")?.value || "";
    const statusFilter = document.getElementById("user-status-filter")?.value || "";

    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (roleFilter) params.append("role", roleFilter);
    if (statusFilter !== "") params.append("is_active", statusFilter);

    try {
      const users = await App.apiRequest(`/api/admin/users?${params.toString()}`);
      this.cachedUsers = users;

      if (!users || users.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2rem; color: var(--text-secondary);">No users found matching query.</td></tr>`;
        return;
      }

      tableBody.innerHTML = users.map(u => {
        const isSelf = App.currentUser && App.currentUser.id === u.id;
        const initials = (u.full_name || u.email).slice(0, 2).toUpperCase();
        const roleClass = u.role.toLowerCase() === "admin" ? "admin" : "reviewer";
        const statusClass = u.is_active ? "active" : "inactive";
        const statusText = u.is_active ? "Active" : "Disabled";
        const lastLogin = u.last_login_at ? new Date(u.last_login_at).toLocaleString() : '<span style="color: var(--text-secondary);">Never</span>';
        const createdDate = u.created_at ? new Date(u.created_at).toLocaleDateString() : '-';

        return `
          <tr style="border-bottom: 1px solid var(--border-color);">
            <td style="padding: 0.9rem 0.6rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <div class="user-avatar" style="width: 32px; height: 32px; font-size: 0.8rem;">${initials}</div>
                <div>
                  <div style="font-weight: 600; color: var(--text-primary); display: flex; align-items: center; gap: 0.4rem;">
                    ${u.full_name || u.email.split('@')[0]}
                    ${isSelf ? '<span style="font-size: 0.7rem; color: #38bdf8; background: rgba(56,189,248,0.15); padding: 0.1rem 0.35rem; border-radius: 4px;">You</span>' : ''}
                  </div>
                  <div style="font-size: 0.78rem; color: var(--text-secondary);">${u.email}</div>
                </div>
              </div>
            </td>
            <td style="padding: 0.9rem 0.6rem;">
              <span class="role-tag ${roleClass}">${u.role}</span>
            </td>
            <td style="padding: 0.9rem 0.6rem;">
              <span class="status-pill ${statusClass}">${statusText}</span>
            </td>
            <td style="padding: 0.9rem 0.6rem; font-size: 0.82rem; color: var(--text-secondary);">
              ${lastLogin}
            </td>
            <td style="padding: 0.9rem 0.6rem; font-size: 0.82rem; color: var(--text-secondary);">
              ${u.reviews_count || 0} reviews
            </td>
            <td style="padding: 0.9rem 0.6rem; text-align: right;">
              <div style="display: inline-flex; gap: 0.4rem;">
                <button class="btn btn-secondary" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;" onclick="AdminModule.openEditUserModal('${u.id}')" title="Edit details">
                  ✏️ Edit
                </button>
                <button class="btn btn-secondary" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;" onclick="AdminModule.openResetPasswordModal('${u.id}', '${u.email}')" title="Reset password">
                  🔑 Reset
                </button>
                ${!isSelf ? `
                  <button class="btn ${u.is_active ? 'btn-warning' : 'btn-success'}" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;" onclick="AdminModule.toggleUserStatus('${u.id}', ${u.is_active})" title="${u.is_active ? 'Deactivate account' : 'Activate account'}">
                    ${u.is_active ? '⏸ Disable' : '▶ Enable'}
                  </button>
                  <button class="btn btn-danger" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;" onclick="AdminModule.deleteUser('${u.id}', '${u.email}')" title="Delete account">
                    🗑️ Delete
                  </button>
                ` : ''}
              </div>
            </td>
          </tr>
        `;
      }).join("");
    } catch (e) {
      console.error("Error loading users:", e);
      tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 1.5rem; color: #f87171;">Failed to load users: ${e.message}</td></tr>`;
    }
  },

  // --------------------------------------------------------------------------
  // Create User Modal & Actions
  // --------------------------------------------------------------------------
  openCreateUserModal() {
    const modal = document.getElementById("modal-create-user");
    if (!modal) return;
    document.getElementById("cu-name").value = "";
    document.getElementById("cu-email").value = "";
    document.getElementById("cu-password").value = "";
    document.getElementById("cu-role").value = "Reviewer";
    document.getElementById("cu-active").checked = true;
    const alertEl = document.getElementById("cu-alert");
    if (alertEl) alertEl.style.display = "none";
    modal.classList.add("show");
  },

  closeCreateUserModal() {
    const modal = document.getElementById("modal-create-user");
    if (modal) modal.classList.remove("show");
  },

  async submitCreateUser(e) {
    e.preventDefault();
    const full_name = document.getElementById("cu-name").value.trim();
    const email = document.getElementById("cu-email").value.trim();
    const password = document.getElementById("cu-password").value;
    const role = document.getElementById("cu-role").value;
    const is_active = document.getElementById("cu-active").checked;
    const alertEl = document.getElementById("cu-alert");

    const showAlert = (msg) => {
      if (alertEl) {
        alertEl.innerText = msg;
        alertEl.className = "auth-alert error";
        alertEl.style.display = "block";
      }
    };

    if (!email || !password) {
      showAlert("Email and password are required.");
      return;
    }
    if (password.length < 8) {
      showAlert("Password must be at least 8 characters.");
      return;
    }

    try {
      await App.apiRequest("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          full_name: full_name || null,
          role,
          is_active
        })
      });

      App.showToast(`User ${email} created successfully`);
      this.closeCreateUserModal();
      this.loadUsers();
      this.loadStats();
      this.loadAuditLogs();
    } catch (err) {
      showAlert(err.message || "Failed to create user.");
    }
  },

  // --------------------------------------------------------------------------
  // Edit User Modal & Actions
  // --------------------------------------------------------------------------
  openEditUserModal(userId) {
    const user = this.cachedUsers.find(u => u.id === userId);
    if (!user) return;

    const modal = document.getElementById("modal-edit-user");
    if (!modal) return;

    document.getElementById("eu-user-id").value = user.id;
    document.getElementById("eu-name").value = user.full_name || "";
    document.getElementById("eu-email").value = user.email;
    document.getElementById("eu-role").value = user.role;
    document.getElementById("eu-active").checked = !!user.is_active;

    const alertEl = document.getElementById("eu-alert");
    if (alertEl) alertEl.style.display = "none";
    modal.classList.add("show");
  },

  closeEditUserModal() {
    const modal = document.getElementById("modal-edit-user");
    if (modal) modal.classList.remove("show");
  },

  async submitEditUser(e) {
    e.preventDefault();
    const userId = document.getElementById("eu-user-id").value;
    const full_name = document.getElementById("eu-name").value.trim();
    const email = document.getElementById("eu-email").value.trim();
    const role = document.getElementById("eu-role").value;
    const is_active = document.getElementById("eu-active").checked;
    const alertEl = document.getElementById("eu-alert");

    const showAlert = (msg) => {
      if (alertEl) {
        alertEl.innerText = msg;
        alertEl.className = "auth-alert error";
        alertEl.style.display = "block";
      }
    };

    try {
      await App.apiRequest(`/api/admin/users/${userId}`, {
        method: "PUT",
        body: JSON.stringify({
          full_name: full_name || null,
          email,
          role,
          is_active
        })
      });

      App.showToast("User details updated successfully");
      this.closeEditUserModal();
      this.loadUsers();
      this.loadStats();
      this.loadAuditLogs();

      // If updating self, refresh profile
      if (App.currentUser && App.currentUser.id === userId) {
        App.checkAuth();
      }
    } catch (err) {
      showAlert(err.message || "Failed to update user.");
    }
  },

  // --------------------------------------------------------------------------
  // Toggle Status & Delete
  // --------------------------------------------------------------------------
  async toggleUserStatus(userId, currentStatus) {
    const action = currentStatus ? "disable" : "activate";
    if (!confirm(`Are you sure you want to ${action} this user account?`)) return;

    try {
      await App.apiRequest(`/api/admin/users/${userId}/status`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !currentStatus })
      });
      App.showToast(`User account ${!currentStatus ? 'activated' : 'disabled'}`);
      this.loadUsers();
      this.loadStats();
      this.loadAuditLogs();
    } catch (err) {
      App.showToast(`Failed to update status: ${err.message}`, "danger");
    }
  },

  async deleteUser(userId, userEmail) {
    if (!confirm(`Are you sure you want to permanently delete user ${userEmail}? This action cannot be undone.`)) return;

    try {
      await App.apiRequest(`/api/admin/users/${userId}`, {
        method: "DELETE"
      });
      App.showToast(`User ${userEmail} deleted`);
      this.loadUsers();
      this.loadStats();
      this.loadAuditLogs();
    } catch (err) {
      App.showToast(`Failed to delete user: ${err.message}`, "danger");
    }
  },

  // --------------------------------------------------------------------------
  // Reset Password Modal & Actions
  // --------------------------------------------------------------------------
  openResetPasswordModal(userId, userEmail) {
    const modal = document.getElementById("modal-reset-password");
    if (!modal) return;
    document.getElementById("rp-user-id").value = userId;
    document.getElementById("rp-user-email").innerText = userEmail;
    document.getElementById("rp-new-password").value = "";
    const alertEl = document.getElementById("rp-alert");
    if (alertEl) alertEl.style.display = "none";
    modal.classList.add("show");
  },

  closeResetPasswordModal() {
    const modal = document.getElementById("modal-reset-password");
    if (modal) modal.classList.remove("show");
  },

  async submitResetPassword(e) {
    e.preventDefault();
    const userId = document.getElementById("rp-user-id").value;
    const new_password = document.getElementById("rp-new-password").value;
    const alertEl = document.getElementById("rp-alert");

    const showAlert = (msg) => {
      if (alertEl) {
        alertEl.innerText = msg;
        alertEl.className = "auth-alert error";
        alertEl.style.display = "block";
      }
    };

    if (!new_password || new_password.length < 8) {
      showAlert("New password must be at least 8 characters.");
      return;
    }

    try {
      await App.apiRequest(`/api/admin/users/${userId}/reset-password`, {
        method: "POST",
        body: JSON.stringify({ new_password })
      });

      App.showToast("User password reset successfully");
      this.closeResetPasswordModal();
      this.loadAuditLogs();
    } catch (err) {
      showAlert(err.message || "Failed to reset password.");
    }
  },

  // --------------------------------------------------------------------------
  // Security & Audit Logs
  // --------------------------------------------------------------------------
  async loadAuditLogs(actionFilter = "") {
    const container = document.getElementById("admin-audit-logs-table-body");
    if (!container) return;

    try {
      const url = actionFilter ? `/api/admin/audit-logs?limit=50&action=${encodeURIComponent(actionFilter)}` : "/api/admin/audit-logs?limit=50";
      const logs = await App.apiRequest(url);

      if (!logs || logs.length === 0) {
        container.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 1.5rem; color: var(--text-secondary);">No audit logs recorded yet.</td></tr>`;
        return;
      }

      container.innerHTML = logs.map(l => {
        let badgeClass = "login";
        if (l.action.includes("CREATE")) badgeClass = "created";
        else if (l.action.includes("UPDATE") || l.action.includes("STATUS") || l.action.includes("ROLE")) badgeClass = "updated";
        else if (l.action.includes("DELETE")) badgeClass = "deleted";
        else if (l.action.includes("BLOCKED") || l.action.includes("FAILED")) badgeClass = "security";

        const timeStr = l.timestamp ? new Date(l.timestamp).toLocaleString() : '-';

        return `
          <tr style="border-bottom: 1px solid var(--border-color); font-size: 0.85rem;">
            <td style="padding: 0.6rem 0.5rem; color: var(--text-secondary); white-space: nowrap;">${timeStr}</td>
            <td style="padding: 0.6rem 0.5rem; font-weight: 500;">${l.user_email || 'System'}</td>
            <td style="padding: 0.6rem 0.5rem;">
              <span class="audit-badge ${badgeClass}">${l.action}</span>
            </td>
            <td style="padding: 0.6rem 0.5rem; color: var(--text-secondary);">${l.details || '-'}</td>
            <td style="padding: 0.6rem 0.5rem; font-family: monospace; font-size: 0.8rem; color: var(--text-secondary);">${l.ip_address || '-'}</td>
          </tr>
        `;
      }).join("");
    } catch (e) {
      console.warn("Failed to load audit logs:", e);
      container.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 1rem; color: #f87171;">Error loading audit trail.</td></tr>`;
    }
  },

  // --------------------------------------------------------------------------
  // LLM Providers & Guidelines & SSO (Existing Features Retained)
  // --------------------------------------------------------------------------
  async loadProviders() {
    try {
      const providers = await App.apiRequest("/api/admin/providers");
      const container = document.getElementById("admin-providers-list");
      if (!container) return;

      container.innerHTML = providers.map(p => `
        <div style="display: flex; justify-content: space-between; align-items: center; background: #0f172a; padding: 0.8rem 1rem; border-radius: 8px; margin-bottom: 0.6rem; border: 1px solid var(--border-color);">
          <div>
            <strong style="text-transform: uppercase;">${p.provider_name}</strong>
            <div style="font-size: 0.8rem; color: var(--text-secondary);">
              Key: ${p.masked_key || '<span style="color: #f59e0b;">Not Set (Using Env / Mock)</span>'}
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 0.8rem;">
            <label style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; margin: 0;">
              <input type="checkbox" ${p.is_enabled ? 'checked' : ''} ${!p.has_api_key ? 'disabled' : ''} onchange="AdminModule.toggleProvider('${p.provider_name}', this.checked)">
              Enabled
            </label>
            <button class="btn btn-secondary" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;" onclick="AdminModule.promptApiKey('${p.provider_name}')">
              Set Key
            </button>
          </div>
        </div>
      `).join("");
    } catch (e) {
      console.error("Error loading providers:", e);
    }
  },

  async toggleProvider(name, isEnabled) {
    try {
      await App.apiRequest(`/api/admin/providers/${name}`, {
        method: "PUT",
        body: JSON.stringify({ is_enabled: isEnabled })
      });
      App.showToast(`Updated ${name.toUpperCase()} status`);
    } catch (e) {
      App.showToast("Failed to update provider", "danger");
    }
  },

  async promptApiKey(name) {
    const key = prompt(`Enter API Key for ${name.toUpperCase()}:`);
    if (key === null) return;
    try {
      await App.apiRequest(`/api/admin/providers/${name}`, {
        method: "PUT",
        body: JSON.stringify({ is_enabled: true, api_key: key })
      });
      App.showToast(`API Key saved securely for ${name.toUpperCase()}`);
      this.loadProviders();
    } catch (e) {
      App.showToast("Failed to save API key", "danger");
    }
  },

  // --------------------------------------------------------------------------
  // Architecture Guidelines & Tenets Management
  // --------------------------------------------------------------------------
  async loadGuidelines() {
    try {
      const guidelines = await App.apiRequest("/api/admin/guidelines");
      this.cachedGuidelines = Array.isArray(guidelines) ? guidelines : [];
      const listEl = document.getElementById("admin-guidelines-list");
      if (!listEl) return;

      if (!this.cachedGuidelines || this.cachedGuidelines.length === 0) {
        listEl.innerHTML = `<p style="color: var(--text-secondary); text-align: center; padding: 2rem;">No corporate guidelines defined yet. Click <strong>+ Add Guideline</strong> above to create one.</p>`;
        return;
      }

      listEl.innerHTML = this.cachedGuidelines.map(g => {
        const cat = (g.category || "general").toLowerCase();
        const statusClass = g.is_active ? "active" : "inactive";
        const statusText = g.is_active ? "Active" : "Disabled";
        const updatedDate = g.updated_at ? new Date(g.updated_at).toLocaleDateString() : (g.created_at ? new Date(g.created_at).toLocaleDateString() : "");

        return `
          <div class="guideline-card">
            <div style="flex: 1; min-width: 0;">
              <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.5rem;">
                <strong style="font-size: 1.02rem; color: var(--text-primary);">${this.escapeHtml(g.title)}</strong>
                <span class="category-tag ${cat}">${this.escapeHtml(g.category || "general")}</span>
                <span class="status-pill ${statusClass}">${statusText}</span>
                ${updatedDate ? `<span style="font-size: 0.76rem; color: var(--text-secondary); margin-left: auto;">Updated: ${updatedDate}</span>` : ''}
              </div>
              <p style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.5; margin: 0; white-space: pre-wrap; word-break: break-word;">${this.escapeHtml(g.content)}</p>
            </div>
            <div style="display: inline-flex; gap: 0.4rem; flex-shrink: 0; align-self: flex-start;">
              <button class="btn btn-secondary" style="padding: 0.28rem 0.65rem; font-size: 0.78rem;" onclick="AdminModule.openEditGuidelineModal('${g.id}')" title="Edit guideline details">
                ✏️ Edit
              </button>
              <button class="btn ${g.is_active ? 'btn-warning' : 'btn-success'}" style="padding: 0.28rem 0.65rem; font-size: 0.78rem;" onclick="AdminModule.toggleGuidelineStatus('${g.id}', ${g.is_active})" title="${g.is_active ? 'Deactivate tenet' : 'Activate tenet'}">
                ${g.is_active ? '⏸ Disable' : '▶ Enable'}
              </button>
              <button class="btn btn-danger" style="padding: 0.28rem 0.65rem; font-size: 0.78rem;" onclick="AdminModule.deleteGuideline('${g.id}')" title="Delete guideline">
                🗑️ Delete
              </button>
            </div>
          </div>
        `;
      }).join("");
    } catch (e) {
      console.error("Error loading guidelines:", e);
      const listEl = document.getElementById("admin-guidelines-list");
      if (listEl) {
        listEl.innerHTML = `<p style="color: #f87171; padding: 1rem;">Failed to load guidelines: ${e.message}</p>`;
      }
    }
  },

  openAddGuidelineModal() {
    const modal = document.getElementById("modal-add-guideline");
    if (!modal) return;
    document.getElementById("ag-title").value = "";
    document.getElementById("ag-category").value = "architecture";
    document.getElementById("ag-content").value = "";
    document.getElementById("ag-active").checked = true;
    const alertEl = document.getElementById("ag-alert");
    if (alertEl) {
      alertEl.style.display = "none";
      alertEl.innerText = "";
    }
    modal.classList.add("show");
  },

  closeAddGuidelineModal() {
    const modal = document.getElementById("modal-add-guideline");
    if (modal) modal.classList.remove("show");
  },

  async submitAddGuideline(e) {
    e.preventDefault();
    const title = document.getElementById("ag-title").value.trim();
    const category = document.getElementById("ag-category").value;
    const content = document.getElementById("ag-content").value.trim();
    const is_active = document.getElementById("ag-active").checked;
    const alertEl = document.getElementById("ag-alert");

    const showAlert = (msg) => {
      if (alertEl) {
        alertEl.innerText = msg;
        alertEl.className = "auth-alert error";
        alertEl.style.display = "block";
      }
    };

    if (!title || !content) {
      showAlert("Both title and content are required.");
      return;
    }

    try {
      await App.apiRequest("/api/admin/guidelines", {
        method: "POST",
        body: JSON.stringify({ title, content, category, is_active })
      });
      App.showToast("Guideline added successfully");
      this.closeAddGuidelineModal();
      this.loadGuidelines();
      this.loadAuditLogs();
    } catch (err) {
      showAlert(err.message || "Failed to create guideline.");
    }
  },

  addGuideline() {
    this.openAddGuidelineModal();
  },

  openEditGuidelineModal(guidelineId) {
    const guideline = this.cachedGuidelines.find(g => g.id === guidelineId);
    if (!guideline) {
      App.showToast("Guideline not found", "danger");
      return;
    }

    const modal = document.getElementById("modal-edit-guideline");
    if (!modal) return;

    document.getElementById("eg-id").value = guideline.id;
    document.getElementById("eg-title").value = guideline.title || "";
    document.getElementById("eg-category").value = (guideline.category || "general").toLowerCase();
    document.getElementById("eg-content").value = guideline.content || "";
    document.getElementById("eg-active").checked = !!guideline.is_active;

    const alertEl = document.getElementById("eg-alert");
    if (alertEl) {
      alertEl.style.display = "none";
      alertEl.innerText = "";
    }
    modal.classList.add("show");
  },

  closeEditGuidelineModal() {
    const modal = document.getElementById("modal-edit-guideline");
    if (modal) modal.classList.remove("show");
  },

  async submitEditGuideline(e) {
    e.preventDefault();
    const id = document.getElementById("eg-id").value;
    const title = document.getElementById("eg-title").value.trim();
    const category = document.getElementById("eg-category").value;
    const content = document.getElementById("eg-content").value.trim();
    const is_active = document.getElementById("eg-active").checked;
    const alertEl = document.getElementById("eg-alert");

    const showAlert = (msg) => {
      if (alertEl) {
        alertEl.innerText = msg;
        alertEl.className = "auth-alert error";
        alertEl.style.display = "block";
      }
    };

    if (!id) {
      showAlert("Missing guideline identifier.");
      return;
    }
    if (!title) {
      showAlert("Guideline title cannot be empty.");
      return;
    }
    if (!content) {
      showAlert("Guideline content cannot be empty.");
      return;
    }

    try {
      await App.apiRequest(`/api/admin/guidelines/${id}`, {
        method: "PUT",
        body: JSON.stringify({ title, content, category, is_active })
      });
      App.showToast("Guideline updated successfully");
      this.closeEditGuidelineModal();
      this.loadGuidelines();
      this.loadAuditLogs();
    } catch (err) {
      showAlert(err.message || "Failed to update guideline.");
    }
  },

  async toggleGuidelineStatus(id, currentActive) {
    const newStatus = !currentActive;
    try {
      await App.apiRequest(`/api/admin/guidelines/${id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: newStatus })
      });
      App.showToast(`Guideline ${newStatus ? 'activated' : 'disabled'} successfully`);
      this.loadGuidelines();
      this.loadAuditLogs();
    } catch (e) {
      App.showToast("Failed to change guideline status: " + e.message, "danger");
    }
  },

  async deleteGuideline(id) {
    if (!confirm("Are you sure you want to delete this guideline? This action cannot be undone.")) return;
    try {
      await App.apiRequest(`/api/admin/guidelines/${id}`, { method: "DELETE" });
      App.showToast("Guideline removed successfully");
      this.loadGuidelines();
      this.loadAuditLogs();
    } catch (e) {
      App.showToast("Failed to delete guideline: " + e.message, "danger");
    }
  },

  // --------------------------------------------------------------------------
  // Architecture Sources (Excel, PDF, Word, URL) Management
  // --------------------------------------------------------------------------
  getAgentLabel(agentKey) {
    const labels = {
      global: "🌐 Global (All Agents)",
      lead_architect: "🏛️ Lead Architect",
      secops_compliance: "🛡️ SecOps & Compliance",
      finops: "💰 FinOps",
      synthesis_validator: "⚖️ Synthesis & Validator"
    };
    return labels[agentKey] || agentKey;
  },

  getSourceTypeLabel(typeKey) {
    const labels = {
      excel: "📊 Excel (.xlsx)",
      pdf: "📄 PDF Document",
      word: "📝 Word Document",
      url: "🔗 Web URL"
    };
    return labels[typeKey] || typeKey;
  },

  formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  },

  async loadSources() {
    try {
      const sources = await App.apiRequest("/api/admin/sources");
      this.cachedSources = sources || [];
      this.renderSources();
    } catch (e) {
      console.error("Error loading sources:", e);
      const container = document.getElementById("admin-sources-list");
      if (container) {
        container.innerHTML = `<p style="color: var(--danger);">Failed to load reference sources: ${this.escapeHtml(e.message)}</p>`;
      }
    }
  },

  filterSources() {
    this.renderSources();
  },

  renderSources() {
    const container = document.getElementById("admin-sources-list");
    if (!container) return;

    const agentFilter = (document.getElementById("filter-source-agent")?.value || "").trim().toLowerCase();
    const typeFilter = (document.getElementById("filter-source-type")?.value || "").trim().toLowerCase();

    let filtered = this.cachedSources;
    if (agentFilter) {
      filtered = filtered.filter(s => (s.target_agent || "global").toLowerCase() === agentFilter);
    }
    if (typeFilter) {
      filtered = filtered.filter(s => (s.source_type || "").toLowerCase() === typeFilter);
    }

    const counter = document.getElementById("sources-counter");
    if (counter) {
      counter.innerText = `Showing ${filtered.length} of ${this.cachedSources.length} sources`;
    }

    if (!filtered || filtered.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2.5rem 1rem; border: 1px dashed var(--border-color); border-radius: 8px; color: var(--text-secondary);">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">📚</div>
          <p style="margin-bottom: 0.8rem; font-size: 0.92rem;">No reference sources found matching the current filters.</p>
          <button class="btn btn-secondary" style="font-size: 0.82rem;" onclick="AdminModule.openAddSourceModal()">+ Add New Source</button>
        </div>
      `;
      return;
    }

    container.innerHTML = filtered.map(s => {
      const isUrl = s.source_type === "url";
      const statusBadge = s.is_active
        ? '<span style="color: #4ade80; font-size: 0.76rem; font-weight: 600; display: inline-flex; align-items: center; gap: 0.3rem;"><span style="width: 7px; height: 7px; border-radius: 50%; background: #4ade80; display: inline-block;"></span> Active</span>'
        : '<span style="color: #94a3b8; font-size: 0.76rem; font-weight: 600; display: inline-flex; align-items: center; gap: 0.3rem;"><span style="width: 7px; height: 7px; border-radius: 50%; background: #64748b; display: inline-block;"></span> Disabled</span>';

      const fileOrUrlMarkup = isUrl && s.url
        ? `<div style="font-size: 0.82rem; margin-top: 0.2rem;">
             <a href="${this.escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer" style="color: var(--accent); text-decoration: underline; display: inline-flex; align-items: center; gap: 0.3rem;">
               🔗 ${this.escapeHtml(s.url)}
             </a>
           </div>`
        : (s.filename
            ? `<div style="font-size: 0.82rem; color: #94a3b8; margin-top: 0.2rem; display: flex; align-items: center; gap: 0.5rem;">
                 <span>📁 ${this.escapeHtml(s.filename)} (${this.formatBytes(s.file_size)})</span>
                 <a href="/api/admin/sources/${s.id}/download" style="color: var(--accent); font-size: 0.76rem; text-decoration: underline;" download>Download</a>
               </div>`
            : "");

      const descriptionMarkup = s.description
        ? `<div style="font-size: 0.85rem; color: var(--text-secondary); line-height: 1.45; margin-top: 0.3rem;">
             ${this.escapeHtml(s.description)}
           </div>`
        : "";

      return `
        <div class="source-card">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 250px;">
              <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.3rem;">
                <h4 style="margin: 0; font-size: 0.98rem; font-weight: 600; color: var(--text-primary);">
                  ${this.escapeHtml(s.name)}
                </h4>
                <span class="source-tag ${s.source_type}">${this.getSourceTypeLabel(s.source_type)}</span>
                <span class="agent-tag ${s.target_agent}">${this.getAgentLabel(s.target_agent)}</span>
                ${statusBadge}
              </div>
              ${fileOrUrlMarkup}
              ${descriptionMarkup}
            </div>
            <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap;">
              <button class="btn btn-secondary" style="padding: 0.28rem 0.65rem; font-size: 0.78rem;" onclick="AdminModule.openPreviewSourceModal('${s.id}')" title="Preview extracted content">
                👁️ Preview
              </button>
              <button class="btn btn-secondary" style="padding: 0.28rem 0.65rem; font-size: 0.78rem;" onclick="AdminModule.openEditSourceModal('${s.id}')" title="Edit source details">
                ✏️ Edit
              </button>
              <button class="btn btn-secondary" style="padding: 0.28rem 0.65rem; font-size: 0.78rem;" onclick="AdminModule.toggleSourceStatus('${s.id}', ${s.is_active})" title="${s.is_active ? 'Disable' : 'Enable'} source">
                ${s.is_active ? '⏸ Disable' : '▶ Enable'}
              </button>
              <button class="btn btn-danger" style="padding: 0.28rem 0.65rem; font-size: 0.78rem;" onclick="AdminModule.deleteSource('${s.id}')" title="Delete source">
                🗑️ Delete
              </button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  },

  onSourceTypeChange(mode) {
    const isEdit = mode === "edit";
    const typeSelect = document.getElementById(isEdit ? "es-type" : "as-type");
    const urlGroup = document.getElementById(isEdit ? "es-url-group" : "as-url-group");
    const fileGroup = document.getElementById(isEdit ? "es-file-group" : "as-file-group");
    const fileInput = document.getElementById(isEdit ? "es-file" : "as-file");
    const fileHint = document.getElementById("as-file-hint");

    if (!typeSelect) return;
    const type = typeSelect.value;

    if (type === "url") {
      if (urlGroup) urlGroup.style.display = "block";
      if (fileGroup) fileGroup.style.display = "none";
    } else {
      if (urlGroup) urlGroup.style.display = "none";
      if (fileGroup) fileGroup.style.display = "block";
      if (fileInput) {
        if (type === "excel") {
          fileInput.accept = ".xlsx,.xls";
          if (fileHint) fileHint.innerText = "Accepted formats: .xlsx, .xls spreadsheets";
        } else if (type === "pdf") {
          fileInput.accept = ".pdf";
          if (fileHint) fileHint.innerText = "Accepted format: .pdf documents";
        } else if (type === "word") {
          fileInput.accept = ".docx,.doc";
          if (fileHint) fileHint.innerText = "Accepted formats: .docx, .doc documents";
        }
      }
    }
  },

  openAddSourceModal() {
    const modal = document.getElementById("modal-add-source");
    if (!modal) return;

    const alertEl = document.getElementById("as-alert");
    if (alertEl) {
      alertEl.style.display = "none";
      alertEl.innerText = "";
    }
    const nameEl = document.getElementById("as-name");
    if (nameEl) nameEl.value = "";
    const typeEl = document.getElementById("as-type");
    if (typeEl) typeEl.value = "url";
    const agentEl = document.getElementById("as-agent");
    if (agentEl) agentEl.value = "global";
    const urlEl = document.getElementById("as-url");
    if (urlEl) urlEl.value = "";
    const fileEl = document.getElementById("as-file");
    if (fileEl) fileEl.value = "";
    const descEl = document.getElementById("as-description");
    if (descEl) descEl.value = "";
    const extEl = document.getElementById("as-extracted-text");
    if (extEl) extEl.value = "";
    const activeEl = document.getElementById("as-active");
    if (activeEl) activeEl.checked = true;

    this.onSourceTypeChange("add");
    modal.classList.add("show");
  },

  closeAddSourceModal() {
    const modal = document.getElementById("modal-add-source");
    if (modal) {
      modal.classList.remove("show");
      modal.classList.remove("active");
    }
  },

  async submitAddSource(event) {
    event.preventDefault();
    const alertEl = document.getElementById("as-alert");
    const submitBtn = document.getElementById("as-submit-btn");

    const name = document.getElementById("as-name").value.trim();
    const source_type = document.getElementById("as-type").value;
    const target_agent = document.getElementById("as-agent").value;
    const url = document.getElementById("as-url").value.trim();
    const fileInput = document.getElementById("as-file");
    const description = document.getElementById("as-description").value.trim();
    const extracted_text = document.getElementById("as-extracted-text").value.trim();
    const is_active = document.getElementById("as-active").checked;

    if (!name) {
      alertEl.innerText = "Source name is required.";
      alertEl.style.display = "block";
      return;
    }

    if (source_type === "url" && !url) {
      alertEl.innerText = "Please provide a valid web URL.";
      alertEl.style.display = "block";
      return;
    }

    if (source_type !== "url" && (!fileInput.files || fileInput.files.length === 0)) {
      alertEl.innerText = `Please select a ${source_type.toUpperCase()} file to upload.`;
      alertEl.style.display = "block";
      return;
    }

    try {
      submitBtn.disabled = true;
      submitBtn.innerText = "Uploading & Ingesting...";

      const formData = new FormData();
      formData.append("name", name);
      formData.append("source_type", source_type);
      formData.append("target_agent", target_agent);
      if (url) formData.append("url", url);
      if (description) formData.append("description", description);
      if (extracted_text) formData.append("extracted_text", extracted_text);
      formData.append("is_active", is_active ? "true" : "false");

      if (fileInput.files && fileInput.files[0]) {
        formData.append("file", fileInput.files[0]);
      }

      const res = await fetch("/api/admin/sources", {
        method: "POST",
        headers: {
          "Authorization": "Bearer " + (AuthModule.token || localStorage.getItem("arb_token"))
        },
        body: formData
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to create reference source.");
      }

      this.closeAddSourceModal();
      App.showToast("Reference source added and ingested successfully");
      this.loadSources();
      this.loadAuditLogs();
    } catch (err) {
      alertEl.innerText = err.message || "Failed to add source";
      alertEl.style.display = "block";
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerText = "Add Source";
    }
  },

  openEditSourceModal(id) {
    const s = this.cachedSources.find(item => item.id === id);
    if (!s) return;

    const modal = document.getElementById("modal-edit-source");
    if (!modal) return;

    const alertEl = document.getElementById("es-alert");
    if (alertEl) {
      alertEl.style.display = "none";
      alertEl.innerText = "";
    }

    const idEl = document.getElementById("es-id");
    if (idEl) idEl.value = s.id;
    const nameEl = document.getElementById("es-name");
    if (nameEl) nameEl.value = s.name || "";
    const typeEl = document.getElementById("es-type");
    if (typeEl) typeEl.value = s.source_type || "url";
    const agentEl = document.getElementById("es-agent");
    if (agentEl) agentEl.value = s.target_agent || "global";
    const urlEl = document.getElementById("es-url");
    if (urlEl) urlEl.value = s.url || "";
    const fileEl = document.getElementById("es-file");
    if (fileEl) fileEl.value = "";
    const descEl = document.getElementById("es-description");
    if (descEl) descEl.value = s.description || "";
    const extEl = document.getElementById("es-extracted-text");
    if (extEl) extEl.value = s.extracted_text || "";
    const activeEl = document.getElementById("es-active");
    if (activeEl) activeEl.checked = !!s.is_active;

    const fileInfo = document.getElementById("es-current-file-info");
    if (fileInfo) {
      fileInfo.innerText = s.filename ? `Current file: ${s.filename} (${this.formatBytes(s.file_size)})` : "No file attached";
    }

    this.onSourceTypeChange("edit");
    modal.classList.add("show");
  },

  closeEditSourceModal() {
    const modal = document.getElementById("modal-edit-source");
    if (modal) {
      modal.classList.remove("show");
      modal.classList.remove("active");
    }
  },

  async submitEditSource(event) {
    event.preventDefault();
    const alertEl = document.getElementById("es-alert");
    const submitBtn = document.getElementById("es-submit-btn");

    const id = document.getElementById("es-id").value;
    const name = document.getElementById("es-name").value.trim();
    const source_type = document.getElementById("es-type").value;
    const target_agent = document.getElementById("es-agent").value;
    const url = document.getElementById("es-url").value.trim();
    const fileInput = document.getElementById("es-file");
    const description = document.getElementById("es-description").value.trim();
    const extracted_text = document.getElementById("es-extracted-text").value.trim();
    const is_active = document.getElementById("es-active").checked;

    if (!name) {
      alertEl.innerText = "Source name cannot be empty.";
      alertEl.style.display = "block";
      return;
    }

    try {
      submitBtn.disabled = true;
      submitBtn.innerText = "Saving Changes...";

      const formData = new FormData();
      formData.append("name", name);
      formData.append("source_type", source_type);
      formData.append("target_agent", target_agent);
      if (url) formData.append("url", url);
      if (description) formData.append("description", description);
      if (extracted_text) formData.append("extracted_text", extracted_text);
      formData.append("is_active", is_active ? "true" : "false");

      if (fileInput.files && fileInput.files[0]) {
        formData.append("file", fileInput.files[0]);
      }

      const res = await fetch(`/api/admin/sources/${id}`, {
        method: "PUT",
        headers: {
          "Authorization": "Bearer " + (AuthModule.token || localStorage.getItem("arb_token"))
        },
        body: formData
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to update source.");
      }

      this.closeEditSourceModal();
      App.showToast("Reference source updated successfully");
      this.loadSources();
      this.loadAuditLogs();
    } catch (err) {
      alertEl.innerText = err.message || "Failed to update source";
      alertEl.style.display = "block";
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerText = "Save Changes";
    }
  },

  async toggleSourceStatus(id, currentActive) {
    try {
      await App.apiRequest(`/api/admin/sources/${id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !currentActive })
      });
      App.showToast(`Source ${!currentActive ? 'enabled' : 'disabled'} successfully`);
      this.loadSources();
    } catch (e) {
      App.showToast("Failed to toggle source: " + e.message, "danger");
    }
  },

  async deleteSource(id) {
    if (!confirm("Are you sure you want to delete this reference source? It will no longer be provided to AI agents during evaluations.")) return;
    try {
      await App.apiRequest(`/api/admin/sources/${id}`, { method: "DELETE" });
      App.showToast("Source removed successfully");
      this.loadSources();
      this.loadAuditLogs();
    } catch (e) {
      App.showToast("Failed to delete source: " + e.message, "danger");
    }
  },

  openPreviewSourceModal(id) {
    const s = this.cachedSources.find(item => item.id === id);
    if (!s) return;

    const modal = document.getElementById("modal-preview-source");
    if (!modal) return;

    const titleEl = document.getElementById("ps-title");
    if (titleEl) titleEl.innerText = s.name;
    const badges = document.getElementById("ps-badges");
    if (badges) {
      badges.innerHTML = `
        <span class="source-tag ${s.source_type}">${this.getSourceTypeLabel(s.source_type)}</span>
        <span class="agent-tag ${s.target_agent}">${this.getAgentLabel(s.target_agent)}</span>
        ${s.is_active ? '<span style="color: #4ade80; font-size: 0.76rem; font-weight: 600;">Active</span>' : '<span style="color: #94a3b8; font-size: 0.76rem;">Disabled</span>'}
        ${s.url ? `<a href="${this.escapeHtml(s.url)}" target="_blank" style="color: var(--accent); font-size: 0.76rem; text-decoration: underline; margin-left: 0.5rem;">Visit URL ↗</a>` : ''}
        ${s.filename ? `<span style="color: #94a3b8; font-size: 0.76rem; margin-left: 0.5rem;">File: ${this.escapeHtml(s.filename)} (${this.formatBytes(s.file_size)})</span>` : ''}
      `;
    }
    const descBox = document.getElementById("ps-description-box");
    if (descBox) {
      descBox.innerText = s.description || "No specific instructions entered.";
    }
    const contentBox = document.getElementById("ps-content");
    if (contentBox) {
      contentBox.innerText = s.extracted_text || "(No extracted text available)";
    }

    modal.classList.add("show");
  },

  closePreviewSourceModal() {
    const modal = document.getElementById("modal-preview-source");
    if (modal) {
      modal.classList.remove("show");
      modal.classList.remove("active");
    }
  },

  async loadSSO() {
    try {
      const sso = await App.apiRequest("/api/admin/sso");
      document.getElementById("sso-enabled").checked = !!sso.is_enabled;
      document.getElementById("sso-provider").value = sso.provider_type || "okta";
      document.getElementById("sso-domain").value = sso.domain || "";
      document.getElementById("sso-client-id").value = sso.client_id || "";
      document.getElementById("sso-redirect-uri").value = sso.redirect_uri || "http://localhost:8000/api/auth/sso/callback";
    } catch (e) {
      console.error("Error loading SSO settings:", e);
    }
  },

  async saveSSO() {
    const is_enabled = document.getElementById("sso-enabled").checked;
    const provider_type = document.getElementById("sso-provider").value;
    const domain = document.getElementById("sso-domain").value.trim();
    const client_id = document.getElementById("sso-client-id").value.trim();
    const client_secret = document.getElementById("sso-client-secret").value.trim();
    const redirect_uri = document.getElementById("sso-redirect-uri").value.trim();

    try {
      await App.apiRequest("/api/admin/sso", {
        method: "PUT",
        body: JSON.stringify({
          is_enabled,
          provider_type,
          domain,
          client_id,
          client_secret: client_secret || null,
          redirect_uri
        })
      });
      App.showToast("SSO configuration updated");
    } catch (e) {
      App.showToast("Failed to update SSO", "danger");
    }
  }
};
