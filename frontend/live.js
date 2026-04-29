
let _lastAnalysis = { code: "", diagnostics: [] };


document.getElementById("file-upload").addEventListener("change", function () {
    const file = this.files[0];
    if (!file) return;

    if (!file.name.endsWith(".py")) {
        setStatus("Only .py files are supported.", "red");
        this.value = "";
        return;
    }

    const reader = new FileReader();
    reader.onload = function (e) {
        document.getElementById("code").value = e.target.result;
        document.getElementById("file-name").textContent = file.name;
        setStatus("File loaded — click Analyze Code to run.", "#aaa");
    };
    reader.onerror = function () {
        setStatus("Could not read the file.", "red");
    };
    reader.readAsText(file);
});


function analyzeCode() {
    const code = document.getElementById("code").value;

    if (!code.trim()) {
        setStatus("Please enter some code first.", "orange");
        return false;
    }

    document.getElementById("results").innerHTML = "Analyzing...";
    document.getElementById("enhance-btn").disabled = true;
    setStatus("", "");

    fetch("http://127.0.0.1:5000/api/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            document.getElementById("results").innerHTML =
                `<p style='color:red;'>Backend error: ${data.error}</p>`;
            return;
        }

        const diagnostics = data.diagnostics || [];
        _lastAnalysis = { code, diagnostics };

        renderDiagnostics(diagnostics);

        // Only enable enhance if there are real diagnostics (not the "no issues" notice)
        const hasRealIssues = diagnostics.some(d => d.severity !== "notice");
        document.getElementById("enhance-btn").disabled = !hasRealIssues;

        if (hasRealIssues) {
            setStatus("Analysis complete. Click ✦ Enhance Explanations for AI commentary.", "#aaa");
        }
    })
    .catch(err => {
        document.getElementById("results").innerHTML =
            `<p style='color:red;'>Connection error: ${err.message}</p>`;
    });

    return false;
}


function renderDiagnostics(diagnostics) {
    if (!diagnostics || diagnostics.length === 0) {
        document.getElementById("results").innerHTML =
            "<p style='color:lightgreen;'>No issues found!</p>";
        return;
    }

    let output = "";
    diagnostics.forEach(d => {
        // Normalise severity → CSS class (backend returns error / warning / notice)
        const sev = (d.severity || "notice").toLowerCase();
        const severityClass = ["error", "warning", "notice"].includes(sev) ? sev : "notice";

        // Inline badge colour so it's visible even if CSS class is unexpected
        const badgeColor = sev === "error"   ? "#e74c3c"
                         : sev === "warning" ? "orange"
                         :                     "#00b894";

        output += `
            <div class="card ${severityClass}" id="card-${d.code}-${d.line}">
                <h3>[${d.code}] ${d.summary}</h3>
                <p>
                    <strong>Severity:</strong>
                    <span style="color:${badgeColor}; font-weight:bold; text-transform:uppercase;">${sev}</span>
                    &nbsp;|&nbsp; <strong>Line:</strong> ${d.line}
                </p>
                <p><strong>Detail:</strong> ${d.detail}</p>
                <p><strong>Fix:</strong> ${d.remedy}</p>
                ${d.analogy ? `<p><em>${d.analogy}</em></p>` : ""}
                ${d.tip    ? `<p>💡 ${d.tip}</p>` : ""}
            </div>
        `;
    });

    document.getElementById("results").innerHTML = output;
}



function enhanceExplanations() {
    const { code, diagnostics } = _lastAnalysis;

    if (!code || !diagnostics.length) {
        setStatus("Run an analysis first.", "orange");
        return;
    }

    const btn = document.getElementById("enhance-btn");
    btn.disabled = true;
    setStatus("Fetching AI explanations…", "#a29bfe");

    // Only send diagnostics that actually have issues (skip I001 notice)
    const toExplain = diagnostics.filter(d => d.severity !== "notice");

    fetch("http://127.0.0.1:5000/api/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, diagnostics: toExplain }),
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            setStatus("AI explanation unavailable: " + data.error, "orange");
            btn.disabled = false;
            return;
        }

        injectAIExplanations(data.explanations || []);
        setStatus("AI explanations added below each issue.", "#a29bfe");
    })
    .catch(err => {
        setStatus("Could not reach explanation service: " + err.message, "red");
        btn.disabled = false;
    });
}

function injectAIExplanations(explanations) {
    // Backend now returns { code, line, explanation } per entry —
    // key by "CODE-LINE" so duplicate-code cards each get their own unique text.
    const lookup = {};
    explanations.forEach(e => { lookup[`${e.code}-${e.line}`] = e.explanation; });

    _lastAnalysis.diagnostics.forEach(d => {
        const key = `${d.code}-${d.line}`;
        if (!lookup[key]) return;

        // Card IDs are built the same way in renderDiagnostics
        const card = document.getElementById(`card-${d.code}-${d.line}`);
        if (!card) return;

        // Avoid injecting twice if enhance is somehow triggered again
        if (card.querySelector(".ai-explanation")) return;

        const aiDiv = document.createElement("div");
        aiDiv.className = "ai-explanation";
        aiDiv.textContent = lookup[key];
        card.appendChild(aiDiv);
    });
}



function loadHistory() {
    fetch("http://127.0.0.1:5000/api/history")
    .then(res => res.json())
    .then(data => {
        let output = "";

        data.forEach((item, index) => {
            // Backend returns source_code + recorded_at (not item.code / item.created_at)
            const src = item.source_code;
            if (!src) return;

            const preview = src.split("\n").slice(0, 2).join("<br>");
            // Escape backticks so loadCode template literal doesn't break
            const escaped = src.replace(/\\/g, "\\\\").replace(/`/g, "\\`");

            output += `
                <div class="history-item" onclick="toggleHistory(${index})">
                    <small>${item.recorded_at || ""}</small>
                    <div>${preview}</div>
                    <div id="full-${index}" style="display:none; margin-top:5px;">
                        <pre style="white-space:pre-wrap;">${escapeHtml(src)}</pre>
                    </div>
                </div>
            `;
        });

        document.getElementById("history").innerHTML = output || "<p style='color:#aaa;'>No history yet.</p>";
    })
    .catch(err => {
        document.getElementById("history").innerHTML =
            `<p style='color:red;'>Failed to load history: ${err.message}</p>`;
    });
}

function toggleHistory(index) {
    const el = document.getElementById(`full-${index}`);
    el.style.display = (el.style.display === "none") ? "block" : "none";
}

function loadCode(code) {
    document.getElementById("code").value = code;
    document.getElementById("file-name").textContent = "loaded from history";
    setStatus("Code loaded. Click Analyze Code to run.", "#aaa");
}


function setStatus(msg, color) {
    const el = document.getElementById("status");
    el.textContent = msg;
    el.style.color = color || "#aaa";
}

function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}
