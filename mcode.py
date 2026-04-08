from flask import Flask, request, jsonify
from flask_cors import CORS
import ast
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            result TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()


# ---------------- BASIC CHECKS ----------------
def basic_checks(code):
    issues = []
    lines = code.split("\n")

    expect_indent = False
    last_indent = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not stripped:
            continue

        indent = len(line) - len(line.lstrip(" "))

        # ---------- Missing colon ----------
        if stripped.startswith(("if ", "for ", "while ", "def ", "elif ", "else")):
            if not stripped.endswith(":"):
                issues.append({
                    "type": "Error",
                    "message": "Missing ':'",
                    "line": i,
                    "reason": "Control statements must end with ':'",
                    "impact": "Block structure breaks.",
                    "fix": "Add ':' at the end."
                })

        # ---------- Incomplete elif ----------
        if stripped == "elif":
            issues.append({
                "type": "Error",
                "message": "Incomplete 'elif'",
                "line": i,
                "reason": "Condition is missing.",
                "impact": "Invalid syntax.",
                "fix": "Use 'elif condition:'"
            })

        # ---------- Expected indentation ----------
        if expect_indent:
            if indent <= last_indent:
                issues.append({
                    "type": "Error",
                    "message": "Expected indentation after ':'",
                    "line": i,
                    "reason": "Block should be indented.",
                    "impact": "Python will raise indentation error.",
                    "fix": "Indent this line (usually 4 spaces)."
                })
            expect_indent = False

        # ---------- Wrong indentation jump ----------
        if indent - last_indent > 4:
            issues.append({
                "type": "Warning",
                "message": "Too much indentation",
                "line": i,
                "reason": "Indentation jumped unexpectedly.",
                "impact": "Code structure becomes unclear.",
                "fix": "Align with previous block."
            })

        # ---------- elif/else alignment ----------
        if stripped.startswith(("elif", "else")):
            if indent != last_indent:
                issues.append({
                    "type": "Error",
                    "message": "Misaligned elif/else",
                    "line": i,
                    "reason": "Must align with its 'if'.",
                    "impact": "Syntax error.",
                    "fix": "Align with 'if' block."
                })

        # ---------- Infinite loop ----------
        if stripped.startswith("while") and ("True" in stripped or "1" in stripped):
            issues.append({
                "type": "Warning",
                "message": "Possible infinite loop",
                "line": i,
                "reason": "Condition always true.",
                "impact": "Program may not stop.",
                "fix": "Add exit condition."
            })

        # ---------- Track block ----------
        if stripped.endswith(":"):
            expect_indent = True
            last_indent = indent
        else:
            last_indent = indent

    return issues

# ---------------- AST ANALYZER ----------------
class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.issues = []
        self.defined = set()
        self.used = set()

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.defined.add(target.id)
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used.add(node.id)

            if node.id not in self.defined and node.id not in dir(__builtins__):
                self.issues.append({
                    "type": "Error",
                    "message": f"Undefined variable '{node.id}'",
                    "line": node.lineno,
                    "reason": "Used before definition.",
                    "impact": "Will crash at runtime.",
                    "fix": "Define the variable first."
                })

        self.generic_visit(node)

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Div):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.issues.append({
                    "type": "Error",
                    "message": "Division by zero",
                    "line": node.lineno,
                    "reason": "Cannot divide by zero.",
                    "impact": "Program crashes.",
                    "fix": "Ensure denominator is not zero."
                })
        self.generic_visit(node)

    def finalize(self):
        unused = self.defined - self.used
        for var in unused:
            self.issues.append({
                "type": "Warning",
                "message": f"Unused variable '{var}'",
                "line": "N/A",
                "reason": "Declared but never used.",
                "impact": "Reduces readability.",
                "fix": "Remove or use it."
            })


# ---------------- ENHANCEMENT ----------------
def enhance(issues):
    for item in issues:
        msg = item["message"].lower()

        if "missing" in msg:
            item["analogy"] = "Like forgetting punctuation in a sentence."
            item["learning_tip"] = "Pay attention to syntax rules."

        elif "indentation" in msg:
            item["analogy"] = "Like misaligned paragraphs in writing."
            item["learning_tip"] = "Indentation defines structure in Python."

        elif "undefined" in msg:
            item["analogy"] = "Like using a name never introduced."
            item["learning_tip"] = "Always define variables before use."

        elif "unused" in msg:
            item["analogy"] = "Like writing something and not using it."
            item["learning_tip"] = "Keep code clean."

        elif "infinite" in msg:
            item["analogy"] = "Like a loop with no exit door."
            item["learning_tip"] = "Always define stopping condition."

        else:
            item["analogy"] = "A small issue affecting execution."
            item["learning_tip"] = "Review logic carefully."

    return issues


# ---------------- API ----------------
@app.route("/api/analyze", methods=["POST"])
def analyze():
    code = request.json.get("code", "")

    issues = []

    issues.extend(basic_checks(code))

    try:
        compile(code, "<user_code>", "exec")
    except SyntaxError as e:
        issues.append({
            "type": "Error",
            "message": "Syntax Error",
            "line": e.lineno,
            "reason": e.msg,
            "impact": "Code cannot run.",
            "fix": "Fix syntax errors."
        })

    # Safe AST (does not block)
    try:
        tree = ast.parse(code)
        analyzer = CodeAnalyzer()
        analyzer.visit(tree)
        analyzer.finalize()
        issues.extend(analyzer.issues)
    except:
        pass

    issues = enhance(issues)

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO analyses (code, result, created_at)
        VALUES (?, ?, ?)
    """, (code, json.dumps(issues), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()

    return jsonify({"issues": issues})


@app.route("/api/history", methods=["GET"])
def history():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM analyses ORDER BY id DESC")
    rows = cursor.fetchall()

    data = []
    for row in rows:
        data.append({
            "code": row[1],
            "created_at": row[3]
        })

    conn.close()
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)