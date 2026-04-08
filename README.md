

# Python Static Code Analyzer (Web Application)

##  Overview

This project is a **web-based Python static code analyzer** designed to help users identify common coding mistakes without executing the code. It focuses on beginner-friendly error detection and provides structured explanations to improve understanding.

The system combines **rule-based analysis, syntax validation, and AST-based inspection** to deliver meaningful feedback.

---

##  Objectives

* Detect syntax and logical issues in Python code
* Provide categorized feedback (Errors, Warnings, Suggestions)
* Offer clear explanations for each issue
* Store user analysis history for future reference
* Build a scalable base for AI-enhanced explanations

##  Key Features
## Multi-Layer Code Analysis
The system uses a **3-layer approach**:

1. **Basic Text Analysis**
    * Missing `:` detection
   * Indentation validation
   * Incomplete statements (e.g., `elif`)
   * Infinite loop warnings

2. **Syntax Validation**
   * Uses Python’s built-in `compile()` function
   * Detects real syntax errors with line numbers

3. **AST-Based Analysis**
   * Undefined variables
   * Unused variables
   * Division by zero detection
   
###  Structured Error Reporting

Each issue includes:
* Type (Error / Warning)
* Line number
* Description
* Reason
* Impact
* Analogy (for easier understanding)
###  History Tracking
* Stores analyzed code in a **SQLite database**
* Sidebar UI for quick access
* Click to reload previous code
* Expandable view for better readability

###  Web Interface
* Built using HTML, CSS, JavaScript
* Sidebar-based layout
* Interactive and responsive UI
* Clean and beginner-friendly design

##  Technologies Used

### Backend

* Python
* Flask
* SQLite (Database)
* AST (Abstract Syntax Tree)

### Frontend

* HTML
* CSS (inline styling)
* JavaScript (Fetch API)
##  Project Structure
```
project/
│
├── backend/
│   └── app.py
│
├── frontend/
│   ├── index.html
│   └── script.js
```
##  How to Run the Project

### 1. Install Dependencies

```bash
pip install flask flask-cors
```

---

### 2. Start Backend

```bash
cd backend
python app.py
```
### 3. Run Frontend

 Open `frontend/index.html` using Live Server
  OR
 Open directly in browser

##  API Endpoints

### Analyze Code

```
POST /api/analyze
```

### Get History

```
GET /api/history
```


##  Future Enhancements

* AI-based explanation layer (advanced suggestions)
* Code optimization and time complexity analysis
* Syntax highlighting with error marking

##  Assumptions

* Users provide Python code input
* Focus is limited to Python language
* Static analysis does not cover runtime behavior fully
* Internet required only for future AI integration

##  Learning Outcome

This project demonstrates:

* Static code analysis techniques
* AST parsing in Python
* REST API development using Flask
* Frontend-backend integration
* Database handling using SQLite

## Conclusion
This project provides a **complete workflow from code input to structured analysis**, helping users understand not just *what is wrong*, but *why it is wrong and how to improve it*.
