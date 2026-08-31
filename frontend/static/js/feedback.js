const FeedbackModule = {
  currentRating: 5,

  setRating(rating) {
    this.currentRating = rating;
    document.querySelectorAll(".star-rating .star").forEach((el, idx) => {
      if (idx < rating) {
        el.classList.add("active");
      } else {
        el.classList.remove("active");
      }
    });
  },

  async submitFeedback(verdict) {
    const reviewId = document.getElementById("feedback-review-id").value || App.currentReviewId;
    if (!reviewId) {
      App.showToast("No active review selected for feedback", "danger");
      return;
    }

    const comments = document.getElementById("feedback-comments").value.trim();
    const corrections = document.getElementById("feedback-corrections").value.trim();

    try {
      // 1. Submit review verdict
      const validationRes = await App.apiRequest(`/api/reviews/${reviewId}/validate`, {
        method: "POST",
        body: JSON.stringify({
          verdict,
          rating: this.currentRating,
          comments,
          corrections
        })
      });

      // 2. Submit continuous learning feedback to vector store
      const feedbackRes = await App.apiRequest(`/api/feedback`, {
        method: "POST",
        body: JSON.stringify({
          review_id: reviewId,
          rating: this.currentRating,
          verdict,
          comments,
          corrections
        })
      });

      App.showToast(`Feedback submitted! Vector Index status: ${feedbackRes.is_indexed_in_vector_db ? 'Indexed in Qdrant' : 'Recorded'}`);

      if (verdict === "revision_requested") {
        App.showToast("Cyclical revision triggered. Updating ADR...");
        if (validationRes.adr) {
          ADRViewerModule.renderADR(validationRes.adr, reviewId);
          App.switchTab("tab-adr");
        }
      }

      this.loadHistory();
    } catch (e) {
      App.showToast(`Feedback Error: ${e.message}`, "danger");
    }
  },

  async loadHistory() {
    try {
      const history = await App.apiRequest("/api/feedback/history");
      const listEl = document.getElementById("feedback-history-list");
      if (!listEl) return;

      if (!history || history.length === 0) {
        listEl.innerHTML = "<p style='color: var(--text-secondary);'>No feedback history recorded yet.</p>";
        return;
      }

      listEl.innerHTML = history.map(item => `
        <div style="background: #0f172a; padding: 1rem; border-radius: 8px; margin-bottom: 0.8rem; border: 1px solid var(--border-color);">
          <div style="display: flex; justify-content: space-between; margin-bottom: 0.4rem;">
            <strong>${item.review_title}</strong>
            <span class="status-badge ${item.verdict === 'approved' ? 'status-completed' : (item.verdict === 'rejected' ? 'status-failed' : 'status-running')}">
              ${item.verdict.toUpperCase()} (${'★'.repeat(item.rating)})
            </span>
          </div>
          ${item.corrections ? `<p style="font-size: 0.85rem; color: var(--accent); margin-bottom: 0.3rem;"><strong>Correction:</strong> ${item.corrections}</p>` : ''}
          ${item.comments ? `<p style="font-size: 0.85rem; color: var(--text-secondary);"><strong>Comments:</strong> ${item.comments}</p>` : ''}
          <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.4rem; display: flex; justify-content: space-between;">
            <span>${new Date(item.created_at).toLocaleString()}</span>
            <span>Vector Indexed: ${item.is_indexed_in_vector_db ? '✓ Yes (Qdrant)' : 'Pending'}</span>
          </div>
        </div>
      `).join("");
    } catch (e) {
      console.error("Failed to load feedback history:", e);
    }
  }
};
