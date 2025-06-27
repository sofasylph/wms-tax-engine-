# WMS Tax Engine

This module provides:
- **Compensation Cess** calculations (dynamic HSN‐based rules)  
- **GST** calculations (CGST/SGST/IGST)  
- A **Flask** API endpoint for on-the-fly tax lookups  
- **Error handling**, **logging**, **UoM conversion**, **currency stub**

## 📁 Directory Structure

```text
your-wms-tax-module/
├── tax_engine.py
├── cess_rules.json
├── requirements.txt
├── README.md
├── tests/
│   └── test_tax_engine.py
└── .github/
    └── workflows/
        └── ci.yml
```

## ⚙️ Installation

1. Clone or copy this folder.  
2. Create a virtualenv (optional):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
3. Install dependencies:
    pip install -r requirements.txt

