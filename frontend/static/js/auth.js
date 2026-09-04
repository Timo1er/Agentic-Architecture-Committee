const AuthModule = {
  activeTab: "login",

  init() {
    this.setupListeners();
  },

  setupListeners() {
    // Close dropdown on click outside
    document.addEventListener("click", (e) => {
      const dropdown = document.getElementById("user-menu-dropdown");
      const badge = document.getElementById("user-display");
      if (dropdown && badge && !badge.contains(e.target)) {
        dropdown.classList.remove("show");
      }
    });
  },

  toggleUserDropdown() {
    const dropdown = document.getElementById("user-menu-dropdown");
    if (dropdown) {
      dropdown.classList.toggle("show");
    }
  },

  showModal(tab = "login") {
    const overlay = document.getElementById("auth-overlay");
    if (!overlay) return;
    overlay.style.display = "flex";
    this.switchAuthTab(tab);
    this.clearAlerts();
  },

  hideModal() {
    const overlay = document.getElementById("auth-overlay");
    if (overlay) overlay.style.display = "none";
    this.clearAlerts();
  },

  switchAuthTab(tab) {
    this.activeTab = tab;
    const btnLogin = document.getElementById("auth-tab-btn-login");
    const btnReg = document.getElementById("auth-tab-btn-register");
    const formLogin = document.getElementById("auth-form-login");
    const formReg = document.getElementById("auth-form-register");

    if (tab === "login") {
      btnLogin?.classList.add("active");
      btnReg?.classList.remove("active");
      if (formLogin) formLogin.style.display = "block";
      if (formReg) formReg.style.display = "none";
    } else {
      btnReg?.classList.add("active");
      btnLogin?.classList.remove("active");
      if (formReg) formReg.style.display = "block";
      if (formLogin) formLogin.style.display = "none";
    }
    this.clearAlerts();
  },

  showAlert(message, type = "error") {
    const alertEl = document.getElementById("auth-alert");
    if (!alertEl) return;
    alertEl.innerText = message;
    alertEl.className = `auth-alert ${type}`;
    alertEl.style.display = "block";
  },

  clearAlerts() {
    const alertEl = document.getElementById("auth-alert");
    if (alertEl) {
      alertEl.style.display = "none";
      alertEl.innerText = "";
    }
  },

  async submitLogin(e) {
    e.preventDefault();
    this.clearAlerts();

    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const submitBtn = document.getElementById("login-submit-btn");

    if (!email || !password) {
      this.showAlert("Please enter both email and password.");
      return;
    }

    try {
      submitBtn.disabled = true;
      submitBtn.innerText = "Signing in...";

      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Authentication failed.");
      }

      App.token = data.access_token;
      localStorage.setItem("arb_token", data.access_token);
      App.currentUser = data.user;

      this.showAlert("Login successful! Loading dashboard...", "success");
      setTimeout(() => {
        this.hideModal();
        App.updateUserUI();
        App.showToast(`Welcome back, ${data.user.full_name || data.user.email}!`);
        if (typeof ReviewModule !== "undefined") {
          ReviewModule.loadPastReviews();
        }
      }, 400);
    } catch (err) {
      this.showAlert(err.message || "Failed to sign in.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerText = "Sign In";
    }
  },

  async submitRegister(e) {
    e.preventDefault();
    this.clearAlerts();

    const fullName = document.getElementById("reg-name").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;
    const confirmPassword = document.getElementById("reg-confirm-password").value;
    const submitBtn = document.getElementById("reg-submit-btn");

    if (!email || !password) {
      this.showAlert("Email and password are required.");
      return;
    }

    if (password !== confirmPassword) {
      this.showAlert("Passwords do not match.");
      return;
    }

    if (password.length < 8) {
      this.showAlert("Password must be at least 8 characters.");
      return;
    }

    try {
      submitBtn.disabled = true;
      submitBtn.innerText = "Creating account...";

      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName || null
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Registration failed.");
      }

      App.token = data.access_token;
      localStorage.setItem("arb_token", data.access_token);
      App.currentUser = data.user;

      this.showAlert("Account created successfully! Redirecting...", "success");
      setTimeout(() => {
        this.hideModal();
        App.updateUserUI();
        App.showToast(`Account created! Welcome, ${data.user.full_name || data.user.email}`);
      }, 500);
    } catch (err) {
      this.showAlert(err.message || "Failed to create account.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerText = "Create Account";
    }
  },

  async logout() {
    try {
      if (App.token) {
        await fetch("/api/auth/logout", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${App.token}`,
            "Content-Type": "application/json"
          }
        });
      }
    } catch (e) {
      console.warn("Logout request failed:", e);
    } finally {
      App.token = "";
      localStorage.removeItem("arb_token");
      App.currentUser = null;
      App.updateUserUI();
      App.switchTab("tab-home");
      this.showModal("login");
      App.showToast("Signed out successfully.");
    }
  },

  // User Profile: Change Password Modal
  openChangePasswordModal() {
    const modal = document.getElementById("modal-change-password");
    if (!modal) return;
    document.getElementById("cp-current-password").value = "";
    document.getElementById("cp-new-password").value = "";
    document.getElementById("cp-confirm-password").value = "";
    const alertEl = document.getElementById("cp-alert");
    if (alertEl) alertEl.style.display = "none";
    modal.classList.add("show");
  },

  closeChangePasswordModal() {
    const modal = document.getElementById("modal-change-password");
    if (modal) modal.classList.remove("show");
  },

  async submitChangePassword(e) {
    e.preventDefault();
    const currentPassword = document.getElementById("cp-current-password").value;
    const newPassword = document.getElementById("cp-new-password").value;
    const confirmPassword = document.getElementById("cp-confirm-password").value;
    const alertEl = document.getElementById("cp-alert");

    const showAlert = (msg, isError = true) => {
      if (alertEl) {
        alertEl.innerText = msg;
        alertEl.className = `auth-alert ${isError ? 'error' : 'success'}`;
        alertEl.style.display = "block";
      }
    };

    if (!currentPassword || !newPassword) {
      showAlert("All fields are required.");
      return;
    }

    if (newPassword !== confirmPassword) {
      showAlert("New passwords do not match.");
      return;
    }

    if (newPassword.length < 8) {
      showAlert("Password must be at least 8 characters.");
      return;
    }

    try {
      await App.apiRequest("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      });

      showAlert("Password successfully updated!", false);
      setTimeout(() => {
        this.closeChangePasswordModal();
        App.showToast("Password updated successfully");
      }, 1000);
    } catch (err) {
      showAlert(err.message || "Failed to update password.");
    }
  }
};

window.addEventListener("DOMContentLoaded", () => {
  AuthModule.init();
});
