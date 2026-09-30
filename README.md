# Sakshi Finance — Autonomous Enterprise Financial Operating System

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js 14](https://img.shields.io/badge/Web-Next.js%2014-black?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![Flutter](https://img.shields.io/badge/Cross--Platform-Flutter%203.x-02569B?style=flat&logo=flutter&logoColor=white)](https://flutter.dev/)
[![Compliance](https://img.shields.io/badge/Compliance-GST%20RCM%20%7C%20Section%20195%20TDS%20%7C%20Zoho%20Books-blue)](#statutory-4-way-compliance-matrix)

**Sakshi Finance** is an autonomous, AI-driven financial operating system that automates invoice extraction, statutory tax assessment, multi-currency conversion, Chart of Accounts (COA) matching, and ERP synchronization for domestic and cross-border vendor invoices.

---

## 🏛️ Statutory 4-Way Compliance Matrix for Foreign Service Invoices

When processing foreign service invoices (e.g., SaaS subscriptions from overseas entities such as HubSpot Asia, AWS Inc., Zoom Video, Google Cloud US), the system enforces a strict 4-way statutory compliance flow:

```mermaid
graph TD
    A[Foreign Vendor Bill: $100.00 USD] --> B[Canonical Forex Conversion: ₹95.2408]
    B --> C[Assessable Subtotal: ₹9,524.08]
    
    C --> D[Side 1: Foreign Vendor Settlement]
    D --> D1[0% Vendor GST Charged Overseas]
    D1 --> D2[Gross Vendor Total: ₹9,524.08]
    D2 --> D3[Less: 20% TDS u/s 195: -₹1,904.82]
    D3 --> D4[Net Wire Remittance: ₹7,619.26 / $80.00 USD]
    
    C --> E[Side 2: Indian Recipient GST Compliance]
    E --> E1[Reverse Charge Mechanism: Section 5(3) IGST Act]
    E1 --> E2[18.0% IGST Cash Output Liability: ₹1,714.33]
    E2 --> E3[Discharged in GSTR-3B Table 3.1d via Cash Ledger]
    E3 --> E4[100% ITC Recovered: GSTR-3B Table 4A2: +₹1,714.33]
    E4 --> E5[Net GST Cash Burden: ₹0.00]
    
    C --> F[Side 3: General Ledger Books Balance]
    F --> F1[Dr. SaaS Expense P&L: ₹9,524.08]
    F --> F2[Dr. GST Input Credit Asset: ₹1,714.33]
    F --> F3[Cr. Accounts Payable Vendor: ₹7,619.26]
    F --> F4[Cr. TDS Payable IT Dept: ₹1,904.82]
    F --> F5[Cr. RCM IGST Output Liability: ₹1,714.33]
    F --> F6[Balanced: Debits ₹11,238.41 == Credits ₹11,238.41]
```

### Mathematical Breakdown
1. **Foreign Vendor Invoice Settlement**:
   $$\text{Converted Subtotal} = \$100.00 \times 95.2408 = ₹9,524.08$$
   $$\text{Vendor GST (0.0\%)} = ₹0.00$$
   $$\text{Vendor Grand Total} = ₹9,524.08$$
   $$\text{TDS Deduction (20.0\% u/s 195)} = -₹1,904.82$$
   $$\mathbf{Net\ Bank\ Wire\ Remittance} = \mathbf{₹7,619.26\ (\$80.00\ USD)}$$

2. **GST Reverse Charge Mechanism (RCM & ITC)**:
   $$\text{IGST RCM (18.0\% via GSTR-3B 3.1d)} = ₹1,714.33$$
   $$\text{100\% Input Tax Credit (ITC via GSTR-3B 4A2)} = +₹1,714.33$$
   $$\mathbf{Net\ GST\ Outflow} = \mathbf{₹0.00\ (Zero\ Net\ Tax\ Cost)}$$

---

## 🚀 Key Features

### 1. Multi-Tier Provenance & Foreign Invoice Workspace
* **3-Tier Provenance Matrix**: Transparently exposes `SYSTEM CLASSIFICATION`, `FINANCE OVERRIDE`, and `FINAL AUTHORITATIVE` origin determination.
* **Forex Conversion Engine**: Real-time RBI Reference Rates, Rule 115 SBI TT Buying Rates, and Bank Remittance overrides.
* **Dual-Currency Subtexts**: Unit prices, taxable amounts, and line item totals display original currency ($100.00 USD) alongside canonical INR.

### 2. Chart of Accounts (COA) Smart Resolver
* **Multi-Tier Resolution**:
  1. Exact `zoho_account_id` match.
  2. Exact case-insensitive name match against active Chart of Accounts.
  3. Normalized fuzzy matching (conjunctions, symbols, whitespace).
  4. AI-Proposed fallback ensuring zero dropdown mismatch errors.

### 3. Statutory Withholding (TDS) Presets
* ⚡ **Section 195 (20.0% Non-Resident)**: Standard statutory foreign service withholding.
* ⚡ **Section 195 (10.0% DTAA Relief)**: Applicable with Tax Residency Certificate (TRC) and Form 10F.
* ⚡ **Section 197 (0.0% Nil Certificate)**: Applicable with Assessing Officer Lower Deduction Certificate.
* ⚡ **Section 194J (2.0% / 10.0%)**: Domestic technical and professional services.

### 4. General Ledger Balancing
* Real-time 5-leg entry generation balancing debits and credits across Expense, Input Tax, Accounts Payable, TDS Liability, and RCM Tax Output.

---

## 📂 Project Structure

```
Sakshi_Finance/
├── backend/                  # FastAPI Python backend
│   ├── app/
│   │   ├── api/v1/           # API endpoints (invoices, auth, forex, zoho, admin)
│   │   ├── core/             # Security, configuration, JWT
│   │   ├── db/               # SQLAlchemy models & migrations
│   │   └── services/         # VLM adapter, GST/TDS engines, Forex service, Zoho client
│   └── tests/                # Automated pytest test suites
│
├── frontend/                 # Next.js 14 / React 18 Web Client
│   ├── src/
│   │   ├── app/              # App router pages (invoices, upload, admin, auth)
│   │   ├── components/       # InvoiceWorkspace, ForeignInvoiceCard, AppShell
│   │   └── lib/              # API client & TypeScript interfaces
│
└── frontend_flutter/         # Flutter 3.x Cross-Platform Client
    └── lib/
        ├── models/           # Dart data models
        ├── providers/        # Riverpod / Provider state management
        ├── screens/          # Workspace, Dashboard, Invoices, Integrations
        └── widgets/          # ForeignServiceFxCard, TdsComplianceCard, GstRcmCard
```

---

## 🛠️ Getting Started

### Prerequisites
* Python 3.10+
* Node.js 18+ and `npm`
* Flutter 3.x (Optional for mobile/desktop)
* PostgreSQL database

---

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run migrations / start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

### Next.js Web Frontend Setup

```bash
cd frontend
npm install

# Run development server
npm run dev

# Run production build validation
npm run build
```

---

### Flutter Client Setup

```bash
cd frontend_flutter
flutter pub get
flutter run -d chrome # or linux / macos / windows
```

---

## 🧪 Running Tests

```bash
# Run backend test suite
cd backend
pytest -v

# Run frontend TypeScript validation
cd frontend
npx tsc --noEmit
```

---

## 📜 License
Private and Proprietary — Sakshi Finance Team.
