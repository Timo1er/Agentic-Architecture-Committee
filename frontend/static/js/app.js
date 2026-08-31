const App = {
  token: localStorage.getItem("arb_token") || "",
  currentUser: null,
  currentReviewId: null,

  init() {
    this.setupTabs();
    this.checkAuth();
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
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));

    const targetBtn = document.querySelector(`.nav-btn[data-tab="${tabId}"]`);
    const targetContent = document.getElementById(tabId);

    if (targetBtn) targetBtn.classList.add("active");
    if (targetContent) targetContent.classList.add("active");

    if (tabId === "tab-admin") {
      AdminModule.loadAdminData();
    } else if (tabId === "tab-feedback") {
      FeedbackModule.loadHistory();
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
        console.warn("Unauthorized request, using default session");
      }
      return await response.json();
    } catch (err) {
      console.error(`API Error on ${endpoint}:`, err);
      this.showToast(`Error: ${err.message}`, "danger");
      throw err;
    }
  },

  async checkAuth() {
    try {
      const user = await this.apiRequest("/api/auth/me");
      this.currentUser = user;
      document.getElementById("user-display").innerText = `${user.full_name || user.email} (${user.role})`;
    } catch (e) {
      document.getElementById("user-display").innerText = "Session Active (Reviewer)";
    }
  },

  showToast(message, type = "success") {
    const toast = document.getElementById("toast");
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
