
/* =========================================================
   VerifyAI | SIH 2026
   Main frontend JavaScript
   File: static/js/app.js
   ========================================================= */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    initializeNavigation();
    initializeFlashMessages();
    initializeFormValidation();
    initializeFileUpload();
    initializeConfirmationPrompts();
    initializeVerifyAIAssistant();
    initializeDashboardInteractions();
});

/* ---------------------------------------------------------
   1. NAVIGATION
   --------------------------------------------------------- */

function initializeNavigation() {
    const menuButton = document.querySelector(
        "[data-menu-toggle], #menu-toggle, .menu-toggle"
    );

    const navigation = document.querySelector(
        "[data-navigation], #sidebar, .sidebar, .nav-menu"
    );

    if (menuButton && navigation) {
        menuButton.addEventListener("click", () => {
            const isOpen = navigation.classList.toggle("is-open");
            navigation.classList.toggle("active", isOpen);
            menuButton.setAttribute("aria-expanded", String(isOpen));
        });
    }

    // Highlight the navigation link matching the current page.
    const currentPath = window.location.pathname.replace(/\/$/, "") || "/";

    document.querySelectorAll("a[href]").forEach((link) => {
        try {
            const linkUrl = new URL(link.href, window.location.origin);

            if (linkUrl.origin !== window.location.origin) return;

            const linkPath = linkUrl.pathname.replace(/\/$/, "") || "/";

            if (linkPath === currentPath) {
                link.classList.add("active");
                link.setAttribute("aria-current", "page");
            }
        } catch (_) {
            // Ignore invalid or nonstandard links.
        }
    });
}

/* ---------------------------------------------------------
   2. FLASH MESSAGES
   --------------------------------------------------------- */

function initializeFlashMessages() {
    document.querySelectorAll(
        "[data-auto-dismiss], .flash-message, .alert-dismissible"
    ).forEach((message) => {
        const dismissButton = message.querySelector(
            "[data-dismiss], .btn-close, .close"
        );

        if (dismissButton) {
            dismissButton.addEventListener("click", () => {
                message.remove();
            });
        }
    });
}

/* ---------------------------------------------------------
   3. FORM VALIDATION
   --------------------------------------------------------- */

function initializeFormValidation() {
    document.querySelectorAll("form").forEach((form) => {
        form.addEventListener("submit", (event) => {
            // Leave forms with their own explicit validation rules
            // to the browser and their existing submit handlers.
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();

                form.classList.add("was-validated");

                const firstInvalid = form.querySelector(":invalid");
                if (firstInvalid) {
                    firstInvalid.focus();
                    firstInvalid.reportValidity();
                }
            }
        });
    });
}

/* ---------------------------------------------------------
   4. DOCUMENT UPLOAD
   --------------------------------------------------------- */

function initializeFileUpload() {
    const fileInputs = document.querySelectorAll(
        'input[type="file"]'
    );

    fileInputs.forEach((input) => {
        input.addEventListener("change", () => {
            const file = input.files && input.files[0];

            const label = document.querySelector(
                `[data-file-name-for="${input.id}"]`
            );

            const nearbyLabel = input.parentElement
                ? input.parentElement.querySelector(
                    "[data-file-name], .file-name"
                )
                : null;

            const output = label || nearbyLabel;

            if (output) {
                output.textContent = file
                    ? file.name
                    : "No file selected";
            }

            if (!file) return;

            const maxSizeMB = Number(
                input.dataset.maxSizeMb || 20
            );

            const maxSizeBytes = maxSizeMB * 1024 * 1024;

            if (file.size > maxSizeBytes) {
                alert(
                    `The selected file is too large. ` +
                    `Maximum allowed size: ${maxSizeMB} MB.`
                );

                input.value = "";

                if (output) {
                    output.textContent = "No file selected";
                }

                return;
            }

            // Optional client-side extension check.
            // The backend must independently validate every upload.
            const allowedExtensions = (
                input.dataset.allowedExtensions ||
                ".pdf,.png,.jpg,.jpeg,.docx"
            )
                .split(",")
                .map((extension) => extension.trim().toLowerCase());

            const extension = "." +
                file.name.split(".").pop().toLowerCase();

            if (
                allowedExtensions.length &&
                !allowedExtensions.includes(extension)
            ) {
                alert(
                    "Unsupported file type. Please select an " +
                    "approved document format."
                );

                input.value = "";

                if (output) {
                    output.textContent = "No file selected";
                }
            }
        });
    });
}

/* ---------------------------------------------------------
   5. CONFIRMATION PROMPTS
   --------------------------------------------------------- */

function initializeConfirmationPrompts() {
    document.querySelectorAll("[data-confirm]").forEach((element) => {
        element.addEventListener("click", (event) => {
            const message =
                element.dataset.confirm ||
                "Are you sure you want to continue?";

            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });
}

/* ---------------------------------------------------------
   6. VERIFYAI EXPLANATION ASSISTANT
   --------------------------------------------------------- */

function initializeVerifyAIAssistant() {
    const caseContainer = document.querySelector("#verifyai-case");

    if (!caseContainer) return;

    let findings = [];

    try {
        findings = JSON.parse(
            caseContainer.dataset.findings || "[]"
        );
    } catch (error) {
        console.error(
            "VerifyAI: Unable to read case findings.",
            error
        );
    }

    if (!Array.isArray(findings)) {
        findings = [];
    }

    // Find the assistant elements if they already exist in the HTML.
    let assistantForm = document.querySelector(
        "#verifyai-form, [data-verifyai-form]"
    );

    let questionInput = document.querySelector(
        "#verifyai-question, [data-verifyai-question]"
    );

    let answerContainer = document.querySelector(
        "#verifyai-answer, [data-verifyai-answer]"
    );

    let suggestions = document.querySelectorAll(
        "[data-verifyai-question-text]"
    );

    // Create a simple assistant interface if the template has not
    // provided one. This makes the feature work without extra markup.
    if (!assistantForm || !questionInput || !answerContainer) {
        const panel = document.createElement("section");
        panel.className = "verifyai-assistant";
        panel.setAttribute("aria-labelledby", "verifyai-heading");

        const heading = document.createElement("h3");
        heading.id = "verifyai-heading";
        heading.textContent = "Ask VerifyAI";

        const description = document.createElement("p");
        description.textContent =
            "Ask why a finding was flagged, what evidence was recorded, " +
            "or what action may be needed next.";

        assistantForm = document.createElement("form");
        assistantForm.id = "verifyai-form";

        questionInput = document.createElement("input");
        questionInput.id = "verifyai-question";
        questionInput.type = "text";
        questionInput.placeholder =
            "e.g. Why was this document flagged?";
        questionInput.autocomplete = "off";
        questionInput.required = true;

        const askButton = document.createElement("button");
        askButton.type = "submit";
        askButton.textContent = "Ask";

        answerContainer = document.createElement("div");
        answerContainer.id = "verifyai-answer";
        answerContainer.setAttribute("role", "status");
        answerContainer.setAttribute("aria-live", "polite");

        assistantForm.append(questionInput, askButton);
        panel.append(
            heading,
            description,
            assistantForm,
            answerContainer
        );

        caseContainer.appendChild(panel);
    }

    // Avoid duplicate event handlers if this initializer is called again.
    if (assistantForm.dataset.initialized === "true") return;
    assistantForm.dataset.initialized = "true";

    assistantForm.addEventListener("submit", (event) => {
        event.preventDefault();

        const question = questionInput.value.trim();

        if (!question) {
            showAssistantAnswer(
                answerContainer,
                "Please enter a question about this application."
            );
            return;
        }

        const response = generateCaseExplanation(
            question,
            findings,
            caseContainer.dataset
        );

        showAssistantAnswer(answerContainer, response);
    });

    suggestions.forEach((suggestion) => {
        suggestion.addEventListener("click", () => {
            const question =
                suggestion.dataset.verifyaiQuestionText;

            if (!question) return;

            questionInput.value = question;
            assistantForm.requestSubmit();
        });
    });
}

function generateCaseExplanation(question, findings, caseData) {
    const q = question.toLowerCase();

    const riskLevel = caseData.riskLevel || "Not specified";
    const riskScore = caseData.riskScore || "Not available";
    const caseStatus = caseData.status || "Not specified";
    const reference = caseData.reference || "Not available";

    if (
        q.includes("hello") ||
        q.includes("hi") ||
        q.includes("help")
    ) {
        return (
            "Hello! I can explain the findings recorded for this case. " +
            "Try asking: “Why was this flagged?”, “What evidence was found?” " +
            "or “What should be done next?”"
        );
    }

    if (
        q.includes("risk score") ||
        q.includes("risk level") ||
        q.includes("overall risk")
    ) {
        return (
            `Case reference: ${reference}\n` +
            `Risk level: ${riskLevel}\n` +
            `Risk score: ${riskScore}\n` +
            `Case status: ${caseStatus}\n\n` +
            "The displayed risk assessment is a screening aid. " +
            "It is not, by itself, proof of non-compliance or fraud."
        );
    }

    if (
        q.includes("how many") ||
        q.includes("list finding") ||
        q.includes("all finding") ||
        q.includes("all issue") ||
        q.includes("summary")
    ) {
        if (!findings.length) {
            return (
                "No findings are available in the case data currently " +
                "provided to this assistant. Check the case record and " +
                "document-processing results."
            );
        }

        const summary = findings.map((finding, index) => {
            const title = finding.title || finding.code || "Finding";
            const severity = finding.severity || "Unspecified severity";
            const status = finding.status || "Status not recorded";

            return (
                `${index + 1}. ${title}\n` +
                `Severity: ${severity}\n` +
                `Status: ${status}`
            );
        });

        return (
            `This case contains ${findings.length} recorded finding(s):\n\n` +
            summary.join("\n\n")
        );
    }

    if (
        q.includes("why") ||
        q.includes("flag") ||
        q.includes("reason")
    ) {
        const relevant = findRelevantFinding(q, findings);

        if (relevant) {
            return formatFindingExplanation(relevant);
        }

        if (!findings.length) {
            return (
                "There are no recorded findings available to explain. " +
                "Check whether document processing has completed."
            );
        }

        return (
            "I could not identify one specific finding from your question. " +
            "Here are the recorded findings:\n\n" +
            findings.map((finding, index) =>
                `${index + 1}. ${finding.title || finding.code || "Finding"}`
            ).join("\n") +
            "\n\nAsk about a particular finding to see its evidence " +
            "and recommended action."
        );
    }

    if (
        q.includes("evidence") ||
        q.includes("proof") ||
        q.includes("detected")
    ) {
        const relevant = findRelevantFinding(q, findings);

        if (relevant) {
            return (
                `Finding: ${relevant.title || relevant.code || "Finding"}\n\n` +
                `Recorded evidence: ${relevant.evidence || "No specific evidence recorded."}\n\n` +
                `Details: ${relevant.detail || "No additional details recorded."}\n\n` +
                "Review the original document and supporting records before " +
                "drawing a conclusion."
            );
        }

        if (!findings.length) {
            return "No finding evidence is currently available in this case.";
        }

        return (
            "The evidence recorded for this case is:\n\n" +
            findings.map((finding, index) =>
                `${index + 1}. ${finding.title || finding.code || "Finding"}: ` +
                `${finding.evidence || finding.detail || "No evidence details recorded."}`
            ).join("\n\n")
        );
    }

    if (
        q.includes("what next") ||
        q.includes("next step") ||
        q.includes("recommend") ||
        q.includes("fix") ||
        q.includes("resolve") ||
        q.includes("action") ||
        q.includes("how to correct")
    ) {
        const relevant = findRelevantFinding(q, findings);

        if (relevant) {
            return (
                `Finding: ${relevant.title || relevant.code || "Finding"}\n\n` +
                `Recommended action: ${relevant.recommendation || "Refer the finding to an authorized reviewer for assessment."}\n\n` +
                "Confirm the required action against the applicable rules " +
                "and official source records."
            );
        }

        if (!findings.length) {
            return (
                "No findings are available to guide a corrective action. " +
                "Review the application checklist and document-processing status."
            );
        }

        return (
            "Recommended actions recorded for this case:\n\n" +
            findings.map((finding, index) =>
                `${index + 1}. ${finding.title || finding.code || "Finding"}\n` +
                `Action: ${finding.recommendation || "Refer for manual review."}`
            ).join("\n\n")
        );
    }

    if (
        q.includes("status") ||
        q.includes("pending") ||
        q.includes("approved") ||
        q.includes("rejected")
    ) {
        return (
            `Case reference: ${reference}\n` +
            `Current recorded status: ${caseStatus}\n\n` +
            "Use the case record for the latest status. VerifyAI screening " +
            "does not replace the final decision of an authorized AICTE official."
        );
    }

    if (
        q.includes("fraud") ||
        q.includes("fake") ||
        q.includes("forged") ||
        q.includes("tamper")
    ) {
        return (
            "A screening flag is not proof of fraud, forgery, or tampering. " +
            "Review the specific evidence, compare the document with an " +
            "authorized issuer or official record when available, and refer " +
            "uncertain cases for manual verification. Do not make an adverse " +
            "decision based on an automated flag alone."
        );
    }

    return (
        "I can explain the findings recorded for this case. Try asking:\n\n" +
        "• Why was this document flagged?\n" +
        "• What evidence was recorded?\n" +
        "• What action is recommended?\n" +
        "• What is the current case status?\n\n" +
        "This assistant uses the case information available in this page. " +
        "It does not independently verify records against live AICTE or issuer systems."
    );
}

function findRelevantFinding(question, findings) {
    if (!findings.length) return null;

    // First try to match a finding's title, code, or description
    // against the words the user entered.
    const normalizedQuestion = question
        .toLowerCase()
        .replace(/[^\w\s-]/g, " ");

    let bestFinding = null;
    let bestScore = 0;

    findings.forEach((finding) => {
        const searchableText = [
            finding.title,
            finding.code,
            finding.detail,
            finding.evidence
        ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();

        const words = normalizedQuestion
            .split(/\s+/)
            .filter((word) => word.length > 3);

        let score = 0;

        words.forEach((word) => {
            if (searchableText.includes(word)) {
                score += 1;
            }
        });

        if (score > bestScore) {
            bestScore = score;
            bestFinding = finding;
        }
    });

    // If the question refers generally to findings, explain the first one.
    return bestFinding || findings[0];
}

function formatFindingExplanation(finding) {
    return (
        `Finding: ${finding.title || finding.code || "Finding"}\n\n` +
        `Severity: ${finding.severity || "Not specified"}\n\n` +
        `Why it was flagged: ${finding.detail || "No explanation recorded."}\n\n` +
        `Evidence: ${finding.evidence || "No specific evidence recorded."}\n\n` +
        `Recommended action: ${finding.recommendation || "Refer the item for manual review."}\n\n` +
        `Source or rule: ${finding.source || "No source recorded."}\n\n` +
        "This flag indicates an item for review, not a confirmed violation."
    );
}

function showAssistantAnswer(container, message) {
    // textContent prevents user input and stored finding text from
    // being interpreted as executable HTML.
    container.textContent = message;
    container.style.whiteSpace = "pre-line";
    container.setAttribute("role", "status");
    container.setAttribute("aria-live", "polite");
}

/* ---------------------------------------------------------
   7. DASHBOARD INTERACTIONS
   --------------------------------------------------------- */

function initializeDashboardInteractions() {
    // Search/filter tables that use these optional attributes.
    const searchInputs = document.querySelectorAll(
        "[data-table-search]"
    );

    searchInputs.forEach((input) => {
        input.addEventListener("input", () => {
            const targetSelector = input.dataset.tableSearch;
            const table = document.querySelector(targetSelector);

            if (!table) return;

            const query = input.value.trim().toLowerCase();

            table.querySelectorAll("tbody tr").forEach((row) => {
                row.hidden = !row.textContent
                    .toLowerCase()
                    .includes(query);
            });
        });
    });

    // Toggle visibility for elements with data-toggle-target.
    document.querySelectorAll("[data-toggle-target]").forEach((button) => {
        button.addEventListener("click", () => {
            const target = document.querySelector(
                button.dataset.toggleTarget
            );

            if (!target) return;

            const willShow = target.hidden;

            target.hidden = !willShow;
            button.setAttribute("aria-expanded", String(willShow));
        });
    });
});
