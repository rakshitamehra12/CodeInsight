
#  Python Static Code Analyzer (Web Application)

##  Overview

This project is a **web-based Python static code analyzer** designed to help users detect common coding mistakes **without executing code**.

It focuses on **beginner-friendly explanations**, combining rule-based checks, syntax validation, and AST-based inspection to provide meaningful, structured feedback.

The system is designed with a **modular architecture**, making it scalable and easy to extend with advanced features like AI-based explanations.

##  Objectives

- Detect syntax and logical issues in Python code
- Provide categorized feedback (Errors, Warnings, Notices)
- Offer clear, structured explanations
- Store user analysis history
- Enable optional AI-powered explanations
- Maintain a scalable and clean architecture

##  Key Features

###  Multi-Layer Code Analysis

The system follows a **3-layer analysis pipeline**:

#### 1. Basic Rule-Based Analysis
- Missing `:` detection
- Indentation validation
- Block structure errors
- Misaligned `else/elif`
- Infinite loop warnings

#### 2. Syntax Validation
- Uses Python’s built-in `compile()` function
- Detects real syntax errors with line numbers

#### 3. AST-Based Analysis
- Undefined variables
- Unused variables
- Division by zero detection


###  Structured Error Reporting

Each issue includes:

- Type (Error / Warning / Notice)
- Error Code (e.g., E101, W301)
- Line number
- Description
- Detailed explanation
- Suggested fix
- Analogy (for easier understanding)
- Extra tips

###  Optional AI Explanation Layer

- Uses LLM via OpenRouter API
- Generates beginner-friendly explanations
- Runs **per diagnostic** (ensures unique explanations)
- Fully **decoupled from core analysis**
- Does NOT modify original results (safe design)

---

###  History Tracking

- Stores analyzed code in **SQLite database**
- Sidebar UI for quick access
- Expandable history view
- Reload previous code easily


### Web Interface

- Built using HTML, CSS, JavaScript
- Responsive sidebar-based layout
- File upload support (`.py`)
- Clean and beginner-friendly UI

##  Architecture Overview

The system follows a modular pipeline:

1. **Syntax Check Layer**  
   Detects compile-time errors using Python parser

2. **Rule Engine**  
   Applies custom static analysis rules

3. **AST Inspection Layer**  
   Analyzes variable usage and logic

4. **Enrichment Layer**  
   Adds analogies and learning tips

5. **Orchestrator**  
   Combines all analysis layers

6. **Optional AI Layer**  
   Generates human-friendly explanations ( a separate service)

 This separation ensures **scalability, maintainability, and clean design**.


##  Technologies Used

### Backend
- Python
- Flask
- SQLite
- AST (Abstract Syntax Tree)

### Frontend
- HTML
- CSS
- JavaScript (Fetch API)


##  Project Structure

```

project/
│
├── backend/
│   └── app.py
│
├── frontend/
│   ├── index.html
│   └── jsfi.js
│
├── README.md

````

##  How to Run the Project

### 1. Install Dependencies

```bash
pip install flask flask-cors
````

### 2. Set Environment Variable (for AI feature)

#### Linux / Mac:

```bash
export OPENROUTER_API_KEY=your_api_key
```

#### Windows:

```bash
set OPENROUTER_API_KEY=your_api_key
```


### 3. Start Backend

```bash
cd backend
python app.py
```

### 4. Run Frontend

* Open `frontend/index.html` using Live Server
  **OR**
* Open directly in browser


## API Endpoints

### Analyze Code

```
POST /api/analyse
```

**Request Body:**

```json
{
  "code": "print('Hello World')"
}
```


### AI Explanation layer (Optional)

```
POST /api/explain
```

**Request Body:**

```json
{
  "code": "...",
  "diagnostics": [...]
}
```


### Get History

```
GET /api/history
```



##  Limitations

* Static analysis only (no runtime execution)
* Limited deep semantic understanding
* No multi-file analysis
* AI explanations depend on external API availability

##  Future Enhancements

* Code optimization suggestions
* Time complexity analysis
* Syntax highlighting with inline error markers
* Multi-language support
* Improved AI reasoning layer


## Learning Outcomes

This project demonstrates:

* Static code analysis techniques
* AST parsing in Python
* Backend API design using Flask
* Frontend-backend integration
* Database handling with SQLite
* Modular software architecture design


##  Conclusion

This project provides a **complete workflow from code input to structured analysis**, helping users understand not just:

*  *What is wrong*
*  *Why it is wrong*
*  *How to improve it*

It is designed as a **scalable foundation** for building advanced developer tools with AI-assisted learning.

---

```

---

