
document.addEventListener("DOMContentLoaded", () => {
  // Close notification messages
  document.querySelectorAll(".flash-close").forEach(btn => {
    btn.addEventListener("click", () => btn.closest(".flash")?.remove());
  });

  // Show or hide password
  const showPassword = document.querySelector(".show-password");

  if (showPassword) {
    showPassword.addEventListener("click", () => {
      const input = document.querySelector("#password");
      if (!input) return;

      const showing = input.type === "password";
      input.type = showing ? "text" : "password";

      showPassword.innerHTML = showing
        ? '<i class="bi bi-eye-slash"></i>'
        : '<i class="bi bi-eye"></i>';

      showPassword.setAttribute(
        "aria-label",
        showing ? "Hide password" : "Show password"
      );
    });
  }

  // Demo account selection
  document.querySelectorAll("[data-demo-user]").forEach(btn => {
    btn.addEventListener("click", () => {
      const username = document.querySelector("#username");
      const password = document.querySelector("#password");

      if (username) username.value = btn.dataset.demoUser;

      if (password) {
        password.value = "";
        password.focus();
      }

      document.querySelectorAll("[data-demo-user]").forEach(button => {
        button.classList.toggle("selected", button === btn);
      });
    });
  });

  // Document upload display
  const fileInput = document.querySelector("#document");
  const fileName = document.querySelector("#file-name");
  const dropzone = document.querySelector("#dropzone");

  if (fileInput && fileName) {
    fileInput.addEventListener("change", () => {
      const file = fileInput.files?.[0];

      fileName.textContent = file
        ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB`
        : "No file selected";

      if (dropzone) {
        dropzone.classList.toggle("has-file", !!file);
      }
    });
  }

  // Drag-and-drop document upload
  if (dropzone && fileInput) {
    ["dragenter", "dragover"].forEach(eventName => {
      dropzone.addEventListener(eventName, event => {
        event.preventDefault();
        dropzone.classList.add("dragging");
      });
    });

    ["dragleave", "drop"].forEach(eventName => {
      dropzone.addEventListener(eventName, event => {
        event.preventDefault();
        dropzone.classList.remove("dragging");
      });
    });

    dropzone.addEventListener("drop", event => {
      const files = event.dataTransfer?.files;

      if (files?.length) {
        fileInput.files = files;
        fileInput.dispatchEvent(
          new Event("change", { bubbles: true })
        );
      }
    });
  }

  // VerifyAI case assistant
  const findingsNode = document.querySelector("#case-findings-data");
  const answer = document.querySelector("#assistant-answer");

  if (findingsNode && answer) {
    let findings = [];

    try {
      findings = JSON.parse(findingsNode.textContent || "[]");
    } catch (error) {
      findings = [];
    }

    const responses = {
      why: () => findings.length
        ? "The rule engine produced " +
          findings.length +
          " finding(s): " +
          findings.map(f => f.title + " (" + f.severity + ")").join("; ") +
          ". Check each finding against the original source. These are triage signals, not a fraud verdict."
        : "No configured findings were returned. Continue standard human review; this is not proof of authenticity.",

      missing: () => {
        const relevant = findings.filter(f =>
          /MISSING|NO_TEXT|EXPIRED|DUPLICATE|DATE/i.test(f.code || "")
        );

        return relevant.length
          ? relevant.map(f => f.title + ": " + f.recommendation).join(" ")
          : "No missing-field or expiry finding was raised by the configured checks. Verify the source document and follow the normal review checklist.";
      },

      risk: () =>
        "The score is a rule-based triage index from 0 to 100. High means review is recommended, not that fraud is proven. OCR can misread text and the configured rules are limited; a qualified human reviewer must make the final decision."
    };

    document.querySelectorAll("[data-question]").forEach(btn => {
      btn.addEventListener("click", () => {
        const response = responses[btn.dataset.question] ||
          (() => "No response available.");

        answer.innerHTML = '<i class="bi bi-stars"></i><span></span>';
        answer.querySelector("span").textContent = response();

        document.querySelectorAll("[data-question]").forEach(button => {
          button.classList.toggle("selected", button === btn);
        });
      });
    });
  }
});

