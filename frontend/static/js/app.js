const App = {
  token: localStorage.getItem("arb_token") || "",
  currentUser: null,
  currentReviewId: null,

  init() {
    this.setupTabs();
    this.checkAuth();
    this.loadActiveProviders();
    if (typeof BuildModule !== "undefined") {
      BuildModule.init();
    }
  },

  async loadActiveProviders() {
    try {
      const health = await this.apiRequest("/api/health");
      if (health && health.active_providers) {
        ["llm-provider-select", "build-llm-provider-select"].forEach(selectId => {
          const select = document.getElementById(selectId);
          if (select) {
            let hasEnabledOptions = false;
            Array.from(select.options).forEach(option => {
              if (!health.active_providers.includes(option.value)) {
                option.disabled = true;
                if (!option.text.includes("(Not Configured)")) {
                  option.text += " (Not Configured)";
                }
              } else {
                hasEnabledOptions = true;
              }
            });
            
            if (select.selectedOptions.length > 0 && select.selectedOptions[0].disabled && hasEnabledOptions) {
              const firstEnabled = Array.from(select.options).find(o => !o.disabled);
              if (firstEnabled) {
                select.value = firstEnabled.value;
              }
            }
          }
        });
      }
    } catch (e) {
      console.warn("Notice: Health check provider query:", e);
    }
  },

  setupTabs() {
    const navButtons = document.querySelectorAll(".nav-btn");
    navButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const targetTab = btn.getAttribute("data-tab");
        this.switchTab(targetTab);
      });
    });
  },

  switchTab(tabId) {
    // RBAC Check for Administration tab
    if (tabId === "tab-admin") {
      if (!this.currentUser || this.currentUser.role !== "Admin") {
        this.showToast("Access Denied: Administrator role required.", "danger");
        if (!this.currentUser) {
          AuthModule.showModal("login");
        }
        return;
      }
    }

    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));

    const targetBtns = document.querySelectorAll(`.nav-btn[data-tab="${tabId}"]`);
    const targetContent = document.getElementById(tabId);

    targetBtns.forEach(btn => btn.classList.add("active"));
    if (targetContent) targetContent.classList.add("active");

    const reviewTabs = ["tab-input", "tab-board", "tab-adr", "tab-feedback"];
    const subNav = document.getElementById("review-sub-nav");
    if (subNav) {
      if (reviewTabs.includes(tabId)) {
        subNav.style.display = "flex";
      } else {
        subNav.style.display = "none";
      }
    }

    if (tabId === "tab-admin") {
      if (typeof AdminModule !== "undefined") {
        AdminModule.loadAdminData();
      }
    } else if (tabId === "tab-feedback") {
      if (typeof FeedbackModule !== "undefined") {
        FeedbackModule.loadHistory();
      }
    } else if (tabId === "tab-input") {
      if (typeof ReviewModule !== "undefined") {
        ReviewModule.loadPastReviews();
      }
    } else if (tabId === "tab-build") {
      if (typeof BuildModule !== "undefined") {
        BuildModule.loadPastBuilds();
      }
    }
  },

  async apiRequest(endpoint, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(this.token ? { "Authorization": `Bearer ${this.token}` } : {}),
      ...(options.headers || {})
    };

    try {
      const response = await fetch(endpoint, { ...options, headers });
      
      if (response.status === 401) {
        // Session expired or unauthenticated
        if (this.token) {
          this.showToast("Session expired. Please sign in again.", "danger");
        }
        this.token = "";
        localStorage.removeItem("arb_token");
        this.currentUser = null;
        this.updateUserUI();
        if (typeof AuthModule !== "undefined") {
          AuthModule.showModal("login");
        }
        const errorData = await response.json().catch(() => ({ detail: "Unauthorized" }));
        throw new Error(errorData.detail || "Unauthorized request");
      }

      if (response.status === 403) {
        const errorData = await response.json().catch(() => ({ detail: "Forbidden" }));
        this.showToast(errorData.detail || "Access Denied: Insufficient privileges", "danger");
        throw new Error(errorData.detail || "Forbidden");
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
        throw new Error(errorData.detail || `Request failed with status ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      throw err;
    }
  },

  async checkAuth() {
    if (!this.token) {
      this.currentUser = null;
      this.updateUserUI();
      if (typeof AuthModule !== "undefined") {
        AuthModule.showModal("login");
      }
      return false;
    }

    try {
      const res = await fetch("/api/auth/me", {
        headers: { "Authorization": `Bearer ${this.token}` }
      });

      if (!res.ok) {
        throw new Error("Invalid session");
      }

      const user = await res.json();
      this.currentUser = user;
      this.updateUserUI();
      if (typeof AuthModule !== "undefined") {
        AuthModule.hideModal();
      }
      return true;
    } catch (e) {
      console.warn("Session validation failed:", e);
      this.token = "";
      localStorage.removeItem("arb_token");
      this.currentUser = null;
      this.updateUserUI();
      if (typeof AuthModule !== "undefined") {
        AuthModule.showModal("login");
      }
      return false;
    }
  },

  updateUserUI() {
    const userDisplay = document.getElementById("user-display");
    const adminNavBtn = document.querySelector('.nav-btn[data-tab="tab-admin"]');

    if (this.currentUser) {
      const name = this.currentUser.full_name || this.currentUser.email.split("@")[0];
      const initials = (name.split(" ").map(n => n[0]).join("") || "U").slice(0, 2).toUpperCase();
      const role = this.currentUser.role || "Reviewer";
      const roleClass = role.toLowerCase() === "admin" ? "admin" : "reviewer";

      if (userDisplay) {
        userDisplay.innerHTML = `
          <div class="user-avatar">${initials}</div>
          <span>${name}</span>
          <span class="role-tag ${roleClass}">${role}</span>
          <span style="font-size: 0.7rem; margin-left: 0.2rem;">▼</span>
          <div class="user-menu-dropdown" id="user-menu-dropdown">
            <div class="user-menu-header">
              <div class="user-name">${this.currentUser.full_name || name}</div>
              <div class="user-email">${this.currentUser.email}</div>
            </div>
            <div class="user-menu-item" onclick="AuthModule.openChangePasswordModal()">
              <span>🔑</span> Change Password
            </div>
            ${role === "Admin" ? `
            <div class="user-menu-item" onclick="App.switchTab('tab-admin')">
              <span>⚙️</span> User & System Admin
            </div>` : ''}
            <div class="user-menu-item danger" onclick="AuthModule.logout()">
              <span>🚪</span> Sign Out
            </div>
          </div>
        `;
        userDisplay.onclick = (e) => {
          if (!e.target.closest(".user-menu-item")) {
            AuthModule.toggleUserDropdown();
          }
        };
      }

      // Show or hide admin tab based on RBAC
      if (adminNavBtn) {
        if (role === "Admin") {
          adminNavBtn.style.display = "inline-flex";
        } else {
          adminNavBtn.style.display = "none";
          // If reviewer is currently on admin tab, switch to home
          const currentActive = document.querySelector(".tab-content.active");
          if (currentActive && currentActive.id === "tab-admin") {
            this.switchTab("tab-home");
          }
        }
      }
    } else {
      if (userDisplay) {
        userDisplay.innerHTML = `
          <button class="btn btn-primary" style="padding: 0.3rem 0.8rem; font-size: 0.82rem;" onclick="AuthModule.showModal('login')">
            Sign In / Register
          </button>
        `;
        userDisplay.onclick = null;
      }
      if (adminNavBtn) {
        adminNavBtn.style.display = "none";
      }
      // If unauthenticated on admin tab, switch to home
      const currentActive = document.querySelector(".tab-content.active");
      if (currentActive && currentActive.id === "tab-admin") {
        this.switchTab("tab-home");
      }
    }
  },

  showToast(message, type = "success") {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.innerText = message;
    toast.style.display = "block";
    toast.style.borderColor = type === "danger" ? "#ef4444" : "#38bdf8";
    setTimeout(() => {
      toast.style.display = "none";
    }, 4000);
  }
};

window.addEventListener("DOMContentLoaded", () => {
  App.init();
});
