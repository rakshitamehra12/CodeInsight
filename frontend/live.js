function analyzeCode() {
    const code = document.getElementById("code").value;

    document.getElementById("results").innerHTML = "Analyzing...";

    fetch("http://127.0.0.1:5000/api/analyze", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ code: code })
    })
    .then(res => res.json())
    .then(data => {

        let output = "";

        data.issues.forEach(item => {
            output += `
                <div class="card ${item.type.toLowerCase()}">
                    <h3>${item.type}</h3>
                    <p>Line: ${item.line}</p>
                    <p>${item.message}</p>
                    <p>${item.reason}</p>
                    <p>${item.impact}</p>
                    <p>${item.fix}</p>
                    <p>${item.analogy}</p>
                    <p>${item.learning_tip}</p>
                </div>
            `;
        });

        document.getElementById("results").innerHTML = output;
    });
}

function loadHistory() {
    fetch("http://127.0.0.1:5000/api/history")
    .then(res => res.json())
    .then(data => {

        let output = "";

        data.forEach((item, index) => {

            let preview = item.code.split("\n").slice(0, 2).join("<br>");

            output += `
                <div style="background:#2c2c54; padding:10px; margin-bottom:10px; cursor:pointer;"
                     onclick="toggleHistory(${index})">
                     
                    <small>${item.created_at}</small>
                    <div>${preview}</div>

                    <div id="full-${index}" style="display:none; margin-top:5px;">
                        <pre style="white-space:pre-wrap;">${item.code}</pre>
                        <button onclick="loadCode(\`${item.code}\`)">Load</button>
                    </div>
                </div>
            `;
        });

        document.getElementById("history").innerHTML = output;
    });
}

function toggleHistory(index) {
    let el = document.getElementById(`full-${index}`);
    el.style.display = (el.style.display === "none") ? "block" : "none";
}
function loadCode(code) {
    document.getElementById("code").value = code;
}
