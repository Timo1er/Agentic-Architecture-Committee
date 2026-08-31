const AdminModule = {
  async loadAdminData() {
    this.loadProviders();
    this.loadGuidelines();
    this.loadSSO();
    this.loadUsers();
  },

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
              <input type="checkbox" ${p.is_enabled ? 'checked' : ''} onchange="AdminModule.toggleProvider('${p.provider_name}', this.checked)">
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

  async loadGuidelines() {
    try {
      const guidelines = await App.apiRequest("/api/admin/guidelines");
      const listEl = document.getElementById("admin-guidelines-list");
      if (!listEl) return;

      listEl.innerHTML = guidelines.map(g => `
        <div style="background: #0f172a; padding: 0.8rem; border-radius: 8px; margin-bottom: 0.6rem; border: 1px solid var(--border-color); display: flex; justify-content: space-between;">
          <div>
            <strong>${g.title}</strong>
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.2rem;">${g.content}</p>
          </div>
          <button class="btn btn-danger" style="padding: 0.2rem 0.5rem; font-size: 0.75rem; align-self: flex-start;" onclick="AdminModule.deleteGuideline('${g.id}')">
            Delete
          </button>
        </div>
      `).join("");
    } catch (e) {
      console.error("Error loading guidelines:", e);
    }
  },

  async addGuideline() {
    const title = prompt("Enter Guideline Title:");
    if (!title) return;
    const content = prompt("Enter Guideline Content / Architecture Rule:");
    if (!content) return;

    try {
      await App.apiRequest("/api/admin/guidelines", {
        method: "POST",
        body: JSON.stringify({ title, content, category: "architecture", is_active: true })
      });
      App.showToast("Guideline added");
      this.loadGuidelines();
    } catch (e) {
      App.showToast("Failed to add guideline", "danger");
    }
  },

  async deleteGuideline(id) {
    if (!confirm("Are you sure you want to delete this guideline?")) return;
    try {
      await App.apiRequest(`/api/admin/guidelines/${id}`, { method: "DELETE" });
      App.showToast("Guideline removed");
      this.loadGuidelines();
    } catch (e) {
      App.showToast("Failed to delete guideline", "danger");
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
  },

  async loadUsers() {
    try {
      const users = await App.apiRequest("/api/admin/users");
      const listEl = document.getElementById("admin-users-list");
      if (!listEl) return;

      listEl.innerHTML = users.map(u => `
        <div style="display: flex; justify-content: space-between; align-items: center; background: #0f172a; padding: 0.6rem 1rem; border-radius: 8px; margin-bottom: 0.5rem; border: 1px solid var(--border-color);">
          <div>
            <strong>${u.full_name || u.email}</strong> <span style="font-size: 0.8rem; color: var(--text-secondary);">(${u.email})</span>
          </div>
          <div style="display: flex; align-items: center; gap: 0.6rem;">
            <select style="padding: 0.3rem 0.5rem; font-size: 0.8rem;" onchange="AdminModule.updateUserRole('${u.id}', this.value)">
              <option value="Admin" ${u.role === 'Admin' ? 'selected' : ''}>Admin</option>
              <option value="Reviewer" ${u.role === 'Reviewer' ? 'selected' : ''}>Reviewer</option>
            </select>
          </div>
        </div>
      `).join("");
    } catch (e) {
      console.error("Error loading users:", e);
    }
  },

  async updateUserRole(userId, role) {
    try {
      await App.apiRequest(`/api/admin/users/${userId}/role`, {
        method: "PUT",
        body: JSON.stringify({ role })
      });
      App.showToast(`Updated user role to ${role}`);
    } catch (e) {
      App.showToast("Failed to update role", "danger");
    }
  }
};
