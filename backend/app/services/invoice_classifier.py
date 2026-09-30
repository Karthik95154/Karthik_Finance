import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class InvoiceClassification(str, Enum):
    INDIAN = "INDIAN"
    FOREIGN_SERVICE = "FOREIGN_SERVICE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNSUPPORTED_FOREIGN_GOODS = "UNSUPPORTED_FOREIGN_GOODS"


# Backward compatibility aliases
InvoiceOrigin = InvoiceClassification


class ClassificationEvidence(BaseModel):
    vendor_country: Optional[str] = None
    vendor_country_source: Optional[str] = None
    vendor_gstin: Optional[str] = None
    gstin_type: Optional[str] = None  # DOMESTIC_01_38, OIDAR_99, INVALID, None
    vendor_pan: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    tax_id_type: Optional[str] = None  # US_EIN, EU_VAT, SG_UEN, GENERIC_FOREIGN, None
    bank_type: Optional[str] = None    # INDIAN_IFSC, INTERNATIONAL_SWIFT_IBAN, None
    entity_suffix_type: Optional[str] = None  # INDIAN_DOMESTIC, FOREIGN_INTERNATIONAL, None
    is_known_foreign_vendor: bool = False
    is_known_indian_vendor: bool = False
    nature_of_supply: Optional[str] = None  # SERVICE, PHYSICAL_GOODS, UNKNOWN
    supply_evidence: List[str] = Field(default_factory=list)
    currency: str = "INR"
    has_conflicting_evidence: bool = False
    conflict_details: Optional[str] = None


class ClassificationResult(BaseModel):
    classification: InvoiceClassification
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    source: str = "RULE_ENGINE"
    currency: str = "INR"
    evidence: ClassificationEvidence = Field(default_factory=ClassificationEvidence)
    classification_override: Optional[InvoiceClassification] = None
    classification_override_reason: Optional[str] = None
    classified_at: Optional[datetime] = None
    classified_by: Optional[str] = None


# Domestic Indian State Code GSTIN regex (01 through 38)
DOMESTIC_GSTIN_REGEX = re.compile(
    r"\b(0[1-9]|[1-2][0-9]|3[0-8])[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
    re.IGNORECASE,
)

# OIDAR / Non-Resident GSTIN regex (starts with 99)
OIDAR_GSTIN_REGEX = re.compile(
    r"\b99[A-Z0-9]{13}\b|\b99\d{2}[A-Z]{3,5}\d{3,5}",
    re.IGNORECASE,
)

# Indian PAN regex
INDIAN_PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)

# Indian IFSC regex
INDIAN_IFSC_REGEX = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)

# International SWIFT / BIC regex (8 or 11 characters)
SWIFT_BIC_REGEX = re.compile(r"\b[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?\b", re.IGNORECASE)

# IBAN regex (starts with 2-letter foreign country code followed by alphanumeric)
IBAN_REGEX = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b", re.IGNORECASE)

# Foreign Tax IDs (e.g. US EIN 12-3456789, EU VAT, Singapore UEN)
US_EIN_REGEX = re.compile(r"\b\d{2}-\d{7}\b")
SG_UEN_REGEX = re.compile(r"\b\d{9,10}[A-Z]\b|\bT\d{2}[A-Z]{2}\d{4}[A-Z]\b", re.IGNORECASE)
EU_VAT_REGEX = re.compile(r"\b(AT|BE|BG|CY|CZ|DE|DK|EE|EL|ES|FI|FR|HR|HU|IE|IT|LT|LU|LV|MT|NL|PL|PT|RO|SE|SI|SK|GB|CHE|CH)[A-Z0-9]{6,14}\b", re.IGNORECASE)

KNOWN_FOREIGN_VENDORS = [
    "hubspot", "google asia pacific", "google ireland", "amazon web services",
    "aws", "stripe payments", "figma", "github", "zoom video", "openai",
    "atlassian", "slack technologies", "twilio", "digitalocean", "cloudflare",
    "miro", "notion labs", "canva", "adobe systems", "microsoft ireland",
    "godaddy", "vercel", "mongodb", "datadog", "new relic", "docker",
    "gitlab", "dropbox", "salesforce.com inc", "zendesk", "intercom"
]

KNOWN_INDIAN_DOMESTIC_VENDORS = [
    "google cloud india", "amazon seller services private limited",
    "microsoft corporation india", "infosys", "tata consultancy services",
    "wipro", "tcs", "reliance", "bharti airtel", "airtel", "hcl technologies",
    "swiggy", "zomato", "razorpay software", "zoho corporation private limited"
]

FOREIGN_COUNTRIES = {
    "UNITED STATES", "USA", "US", "U.S.A.", "U.S.", "SINGAPORE", "IRELAND",
    "UNITED KINGDOM", "UK", "U.K.", "GREAT BRITAIN", "GERMANY", "DEUTSCHLAND",
    "FRANCE", "AUSTRALIA", "CANADA", "NETHERLANDS", "JAPAN", "UNITED ARAB EMIRATES",
    "UAE", "U.A.E.", "DUBAI", "SWITZERLAND", "SWEDEN", "SPAIN", "ITALY",
    "HONG KONG", "NEW ZEALAND", "ISRAEL", "POLAND", "DENMARK", "FINLAND",
    "NORWAY", "BELGIUM", "AUSTRIA", "SOUTH KOREA", "KOREA"
}

FOREIGN_CITIES_STATES = {
    "DELAWARE", "CALIFORNIA", "SAN FRANCISCO", "SEATTLE", "AUSTIN", "NEW YORK",
    "DUBLIN", "LONDON", "SYDNEY", "MELBOURNE", "BERLIN", "MUNICH", "AMSTERDAM",
    "TOKYO", "TORONTO", "VANCOUVER", "PARIS", "SINGAPORE", "SAN JOSE",
    "MENLO PARK", "PALO ALTO", "CAMBRIDGE", "BOSTON", "CHICAGO", "REDMOND"
}

FOREIGN_ENTITY_SUFFIXES = [
    "inc.", "inc", "llc", "corp.", "corp", "corporation", "gmbh", "pte ltd",
    "pte. ltd.", "pty ltd", "pty. ltd.", "s.a.r.l.", "sarl", "b.v.", "bv",
    "limited (ireland)", "limited (uk)", "co., ltd.", "co. ltd"
]

INDIAN_ENTITY_SUFFIXES = [
    "pvt ltd", "pvt. ltd.", "private limited", "limited", "ltd.", "ltd",
    "llp", "limited liability partnership", "enterprises", "solutions pvt"
]

PHYSICAL_GOODS_INDICATORS = [
    "bill of lading", "airway bill", "awb", "bill of entry", "boe",
    "customs duty", "freight forwarder", "port of loading", "port of discharge",
    "fob", "cif", "cfr", "exw", "fca", "dap", "ddp", "shipping weight",
    "gross weight", "net weight", "container no", "container number",
    "packing list", "delivery challan", "consignment note", "hardware unit",
    "physical shipment", "machinery parts", "raw material", "spare parts",
    "cartons", "pallets", "pieces shipped", "hs code 84", "hs code 85", "hs code 72"
]

SERVICE_INDICATORS = [
    "software", "saas", "subscription", "cloud hosting", "cloud platform", "cloud server",
    "cloud", "server", "hosting", "cluster", "infrastructure",
    "api access", "api credits", "developer plan", "license", "licensing",
    "consulting", "professional services", "technical support", "advisory",
    "digital marketing", "advertising credits", "maintenance services",
    "web services", "data processing", "hosting fees", "legal services",
    "accounting services", "management fee", "service period", "sac 99", "sac code"
]


class InvoiceClassifier:
    """
    Unified, deterministic multi-evidence classifier for Sakshi Finance invoices.
    Evaluates evidence to classify invoices into:
    - INDIAN
    - FOREIGN_SERVICE
    - REVIEW_REQUIRED
    - UNSUPPORTED_FOREIGN_GOODS
    """

    @classmethod
    def analyze_evidence(
        cls,
        invoice_data: Dict[str, Any],
        raw_document_text: Optional[str] = None,
    ) -> ClassificationEvidence:
        evidence = ClassificationEvidence()

        v_name = (invoice_data.get("vendor_name") or "").strip().lower()
        v_addr = (invoice_data.get("vendor_address") or "").strip().lower()
        v_country_field = (invoice_data.get("vendor_country") or "").strip().upper()
        v_gstin = (invoice_data.get("vendor_gstin") or "").strip().upper()
        v_pan = (invoice_data.get("vendor_pan") or "").strip().upper()
        v_tax_id = (invoice_data.get("vendor_tax_id") or "").strip()
        bank_details = invoice_data.get("bank_details") or {}
        line_items = invoice_data.get("line_items") or []
        doc_currency = str(invoice_data.get("currency") or "INR").strip().upper()
        service_desc = (invoice_data.get("service_description") or invoice_data.get("category") or "").strip().lower()

        doc_text = (raw_document_text or "").lower()
        full_text_corpus = f"{v_name} {v_addr} {doc_text} {service_desc}"

        # 1. Currency evidence
        c_gstin = (invoice_data.get("customer_gstin") or invoice_data.get("buyer_gstin") or "").strip().upper()
        c_pan = (invoice_data.get("customer_pan") or invoice_data.get("buyer_pan") or "").strip().upper()

        # 1. Currency evidence
        evidence.currency = doc_currency

        # 2. Known Vendor Matches
        if any(kv in v_name for kv in KNOWN_FOREIGN_VENDORS):
            evidence.is_known_foreign_vendor = True
        elif any(kv in v_name for kv in KNOWN_INDIAN_DOMESTIC_VENDORS):
            evidence.is_known_indian_vendor = True

        # 3. Vendor Country Determination (First check explicit field & vendor address)
        if v_country_field:
            if v_country_field in ("INDIA", "IN", "BHARAT"):
                evidence.vendor_country = "INDIA"
                evidence.vendor_country_source = "EXPLICIT_FIELD"
            elif v_country_field in FOREIGN_COUNTRIES:
                evidence.vendor_country = v_country_field
                evidence.vendor_country_source = "EXPLICIT_FIELD"
            else:
                evidence.vendor_country = v_country_field
                evidence.vendor_country_source = "EXPLICIT_FIELD"

        if not evidence.vendor_country:
            # Check vendor address for explicit country names
            for fc in FOREIGN_COUNTRIES:
                if re.search(r"\b" + re.escape(fc.lower()) + r"\b", v_addr):
                    evidence.vendor_country = fc
                    evidence.vendor_country_source = "VENDOR_ADDRESS"
                    break

        if not evidence.vendor_country and v_addr:
            if re.search(r"\bindia\b", v_addr):
                evidence.vendor_country = "INDIA"
                evidence.vendor_country_source = "VENDOR_ADDRESS"
            else:
                for fcity in FOREIGN_CITIES_STATES:
                    if re.search(r"\b" + re.escape(fcity.lower()) + r"\b", v_addr):
                        evidence.vendor_country = f"FOREIGN ({fcity})"
                        evidence.vendor_country_source = "VENDOR_CITY_STATE"
                        break

        # Fallback: Check raw document text for explicit foreign vendor addresses/cities if vendor_address was not separated
        if not evidence.vendor_country and doc_text:
            for fc in FOREIGN_COUNTRIES:
                if fc in ("USA", "US", "UNITED STATES", "SINGAPORE", "IRELAND", "UNITED KINGDOM", "GERMANY", "AUSTRALIA"):
                    # Only match if near vendor name or header area
                    if re.search(r"\b" + re.escape(fc.lower()) + r"\b", doc_text[:500]):
                        evidence.vendor_country = fc
                        evidence.vendor_country_source = "DOCUMENT_HEADER_TEXT"
                        break

        # 4. Vendor GSTIN Classification (Exclude buyer/customer GSTIN)
        if v_gstin and (not c_gstin or v_gstin != c_gstin):
            evidence.vendor_gstin = v_gstin
            if OIDAR_GSTIN_REGEX.search(v_gstin) or v_gstin.startswith("99"):
                evidence.gstin_type = "OIDAR_99"
            elif DOMESTIC_GSTIN_REGEX.search(v_gstin):
                # If vendor location is proven foreign and this GSTIN matches customer, do not treat as vendor domestic GSTIN
                if evidence.vendor_country and evidence.vendor_country != "INDIA" and v_gstin == c_gstin:
                    evidence.vendor_gstin = None
                    evidence.gstin_type = None
                else:
                    evidence.gstin_type = "DOMESTIC_01_38"
            else:
                evidence.gstin_type = "INVALID"
        elif doc_text and not (evidence.vendor_country and evidence.vendor_country != "INDIA"):
            oidar_m = OIDAR_GSTIN_REGEX.search(doc_text)
            dom_m = DOMESTIC_GSTIN_REGEX.search(doc_text)
            if oidar_m:
                evidence.vendor_gstin = oidar_m.group(0).upper()
                evidence.gstin_type = "OIDAR_99"
            elif dom_m:
                found_gst = dom_m.group(0).upper()
                if not c_gstin or found_gst != c_gstin:
                    evidence.vendor_gstin = found_gst
                    evidence.gstin_type = "DOMESTIC_01_38"

        # 5. Indian PAN / Domestic Tax Identification
        if v_pan and (not c_pan or v_pan != c_pan) and INDIAN_PAN_REGEX.search(v_pan):
            if not (evidence.vendor_country and evidence.vendor_country != "INDIA"):
                evidence.vendor_pan = v_pan.upper()
        elif evidence.vendor_gstin and evidence.gstin_type == "DOMESTIC_01_38" and len(evidence.vendor_gstin) == 15:
            evidence.vendor_pan = evidence.vendor_gstin[2:12]

        # 6. Foreign Tax Identification (EIN, VAT, UEN)
        if v_tax_id:
            evidence.vendor_tax_id = v_tax_id
            if US_EIN_REGEX.search(v_tax_id):
                evidence.tax_id_type = "US_EIN"
            elif SG_UEN_REGEX.search(v_tax_id):
                evidence.tax_id_type = "SG_UEN"
            elif EU_VAT_REGEX.search(v_tax_id):
                evidence.tax_id_type = "EU_VAT"
            else:
                evidence.tax_id_type = "GENERIC_FOREIGN"
        else:
            ein_m = US_EIN_REGEX.search(doc_text)
            vat_m = EU_VAT_REGEX.search(doc_text)
            uen_m = SG_UEN_REGEX.search(doc_text)
            if ein_m:
                evidence.vendor_tax_id = ein_m.group(0)
                evidence.tax_id_type = "US_EIN"
            elif uen_m:
                evidence.vendor_tax_id = uen_m.group(0).upper()
                evidence.tax_id_type = "SG_UEN"
            elif vat_m:
                evidence.vendor_tax_id = vat_m.group(0).upper()
                evidence.tax_id_type = "EU_VAT"

        # 7. Entity Name Suffixes
        for suff in INDIAN_ENTITY_SUFFIXES:
            if re.search(r"\b" + re.escape(suff) + r"\b", v_name):
                evidence.entity_suffix_type = "INDIAN_DOMESTIC"
                break

        if not evidence.entity_suffix_type:
            for suff in FOREIGN_ENTITY_SUFFIXES:
                if re.search(r"\b" + re.escape(suff) + r"\b", v_name):
                    evidence.entity_suffix_type = "FOREIGN_INTERNATIONAL"
                    break

        # 8. Bank Details (IFSC vs SWIFT/IBAN)
        if isinstance(bank_details, dict):
            b_ifsc = bank_details.get("ifsc_code") or bank_details.get("ifsc")
            b_swift = bank_details.get("swift_bic") or bank_details.get("swift_code") or bank_details.get("swift")
            b_iban = bank_details.get("iban")
            if b_ifsc and INDIAN_IFSC_REGEX.search(str(b_ifsc)):
                evidence.bank_type = "INDIAN_IFSC"
            elif b_swift and SWIFT_BIC_REGEX.search(str(b_swift)):
                evidence.bank_type = "INTERNATIONAL_SWIFT_IBAN"
            elif b_iban and IBAN_REGEX.search(str(b_iban)):
                evidence.bank_type = "INTERNATIONAL_SWIFT_IBAN"

        # 9. Supply Nature: Goods vs Service
        goods_matches = []
        service_matches = []

        # Check line items and service descriptions
        item_text_list = [service_desc]
        for item in line_items:
            if isinstance(item, dict):
                desc = (item.get("description") or "").lower()
                hsn = str(item.get("hsn_code") or item.get("sac_code") or item.get("sac") or item.get("hsn_sac") or "").strip()
                item_text_list.append(f"{desc} {hsn}")
                if hsn.startswith("99"):
                    service_matches.append(f"SAC {hsn}")
                elif hsn and len(hsn) >= 2 and hsn[:2].isdigit() and int(hsn[:2]) < 90:
                    goods_matches.append(f"HS Code {hsn}")

        items_corpus = " ".join(item_text_list) + " " + full_text_corpus

        for ind in PHYSICAL_GOODS_INDICATORS:
            if re.search(r"\b" + re.escape(ind) + r"\b", items_corpus):
                goods_matches.append(ind)

        for ind in SERVICE_INDICATORS:
            if re.search(r"\b" + re.escape(ind) + r"\b", items_corpus):
                service_matches.append(ind)

        if goods_matches and not service_matches:
            evidence.nature_of_supply = "PHYSICAL_GOODS"
            evidence.supply_evidence = list(set(goods_matches))
        elif service_matches:
            evidence.nature_of_supply = "SERVICE"
            evidence.supply_evidence = list(set(service_matches))
        else:
            evidence.nature_of_supply = "UNKNOWN"

        # 10. Conflict Detection
        # E.g. Indian domestic GSTIN (01-38) with explicit foreign country/address outside India
        if evidence.gstin_type == "DOMESTIC_01_38" and evidence.vendor_country and evidence.vendor_country != "INDIA" and not evidence.is_known_indian_vendor:
            evidence.has_conflicting_evidence = True
            evidence.conflict_details = f"Contradiction: Domestic Indian GSTIN '{evidence.vendor_gstin}' found, but vendor location indicates '{evidence.vendor_country}'."
        elif evidence.tax_id_type in ("US_EIN", "EU_VAT", "SG_UEN") and evidence.gstin_type == "DOMESTIC_01_38":
            evidence.has_conflicting_evidence = True
            evidence.conflict_details = f"Contradiction: Foreign Tax ID ({evidence.tax_id_type}) and Domestic GSTIN both present."

        return evidence

    @classmethod
    def classify(
        cls,
        invoice_data: Dict[str, Any],
        raw_document_text: Optional[str] = None,
        doc_classification: Optional[Any] = None,
    ) -> ClassificationResult:
        """
        Executes multi-evidence deterministic classification.
        Never relies on currency alone.
        """
        evidence = cls.analyze_evidence(invoice_data, raw_document_text)
        currency = evidence.currency

        # ── GATE 1: Conflicting Evidence Check ──
        if evidence.has_conflicting_evidence:
            return ClassificationResult(
                classification=InvoiceClassification.REVIEW_REQUIRED,
                confidence=0.50,
                reason=f"Conflicting classification evidence detected: {evidence.conflict_details}",
                source="RULE_ENGINE",
                currency=currency,
                evidence=evidence,
                classified_at=datetime.now(timezone.utc),
            )

        # ── GATE 2: Strong Indian Vendor Classification ──
        # Indian entity with Domestic GSTIN (01-38) or Indian PAN / Address / Suffix
        is_domestic_gstin = evidence.gstin_type == "DOMESTIC_01_38"
        is_indian_country = evidence.vendor_country == "INDIA"
        is_indian_bank = evidence.bank_type == "INDIAN_IFSC"
        is_indian_suffix = evidence.entity_suffix_type == "INDIAN_DOMESTIC"

        has_strong_indian_vendor = (
            is_domestic_gstin
            or (evidence.is_known_indian_vendor and evidence.gstin_type != "OIDAR_99")
            or (is_indian_country and (is_indian_suffix or evidence.vendor_pan or is_indian_bank))
        )

        if has_strong_indian_vendor and evidence.gstin_type != "OIDAR_99":
            # Indian vendor billing in USD/EUR is STILL INDIAN (e.g. Indian IT export or domestic foreign-currency billing)
            if currency not in ("INR", "RS", "RUPEES", "₹"):
                reason = f"Indian domestic vendor ({invoice_data.get('vendor_name') or 'Domestic Entity'}) billing in foreign currency ({currency}). Preserved as INDIAN invoice."
            else:
                reason = f"Indian domestic invoice verified via Indian vendor identification (GSTIN: {evidence.vendor_gstin or 'Domestic'}, Country: INDIA)."
            
            return ClassificationResult(
                classification=InvoiceClassification.INDIAN,
                confidence=0.98 if is_domestic_gstin else 0.90,
                reason=reason,
                source="RULE_ENGINE",
                currency=currency,
                evidence=evidence,
                classified_at=datetime.now(timezone.utc),
            )

        # ── GATE 3: Foreign Vendor Classification ──
        is_foreign_country = bool(evidence.vendor_country and evidence.vendor_country != "INDIA")
        is_oidar = evidence.gstin_type == "OIDAR_99"
        is_foreign_tax = evidence.tax_id_type in ("US_EIN", "EU_VAT", "SG_UEN", "GENERIC_FOREIGN")
        is_foreign_entity = evidence.entity_suffix_type == "FOREIGN_INTERNATIONAL" or evidence.is_known_foreign_vendor
        is_foreign_bank = evidence.bank_type == "INTERNATIONAL_SWIFT_IBAN"

        has_foreign_vendor = (
            is_foreign_country
            or is_oidar
            or is_foreign_tax
            or (is_foreign_entity and (currency != "INR" or is_foreign_bank))
        )

        if has_foreign_vendor:
            # Check Goods vs Services for Foreign Vendor
            if evidence.nature_of_supply == "PHYSICAL_GOODS":
                return ClassificationResult(
                    classification=InvoiceClassification.UNSUPPORTED_FOREIGN_GOODS,
                    confidence=0.95,
                    reason=(
                        f"Foreign vendor ({evidence.vendor_country or 'International'}) detected with physical goods indicators "
                        f"({', '.join(evidence.supply_evidence[:3])}). Physical goods imports are not supported in foreign service pipeline."
                    ),
                    source="RULE_ENGINE",
                    currency=currency,
                    evidence=evidence,
                    classified_at=datetime.now(timezone.utc),
                )

            if evidence.nature_of_supply == "SERVICE":
                return ClassificationResult(
                    classification=InvoiceClassification.FOREIGN_SERVICE,
                    confidence=0.95,
                    reason=(
                        f"Foreign service invoice verified: Vendor origin ({evidence.vendor_country or 'Foreign/OIDAR'}) "
                        f"with service supply nature ({', '.join(evidence.supply_evidence[:3])})."
                    ),
                    source="RULE_ENGINE",
                    currency=currency,
                    evidence=evidence,
                    classified_at=datetime.now(timezone.utc),
                )

            # If foreign vendor is confirmed but supply nature is ambiguous (neither clearly service nor physical goods)
            # Do NOT guess!
            return ClassificationResult(
                classification=InvoiceClassification.REVIEW_REQUIRED,
                confidence=0.60,
                reason=(
                    f"Foreign vendor ({evidence.vendor_country or 'International'}) identified, but supply nature (service vs physical goods) "
                    f"is ambiguous. Manual finance review required."
                ),
                source="RULE_ENGINE",
                currency=currency,
                evidence=evidence,
                classified_at=datetime.now(timezone.utc),
            )

        # ── GATE 4: Ambiguous / Missing Evidence (Fail-safe: Never Guess) ──
        # If currency alone is foreign (e.g. USD) but vendor location/identity is completely unknown
        if currency not in ("INR", "RS", "RUPEES", "₹"):
            return ClassificationResult(
                classification=InvoiceClassification.REVIEW_REQUIRED,
                confidence=0.40,
                reason=(
                    f"Invoice currency is {currency}, but vendor country and corporate identity are missing or inconclusive. "
                    f"Manual finance review required."
                ),
                source="RULE_ENGINE",
                currency=currency,
                evidence=evidence,
                classified_at=datetime.now(timezone.utc),
            )

        # If country is completely unknown and no GSTIN/tax info exists
        if not evidence.vendor_country and not evidence.vendor_gstin and not evidence.vendor_pan:
            return ClassificationResult(
                classification=InvoiceClassification.REVIEW_REQUIRED,
                confidence=0.30,
                reason="Vendor country and tax identification are unavailable. Manual finance review required.",
                source="RULE_ENGINE",
                currency=currency,
                evidence=evidence,
                classified_at=datetime.now(timezone.utc),
            )

        # Default fallback for standard domestic with minor missing fields
        return ClassificationResult(
            classification=InvoiceClassification.INDIAN,
            confidence=0.75,
            reason="Domestic Indian invoice default based on available evidence and INR currency.",
            source="RULE_ENGINE",
            currency=currency,
            evidence=evidence,
            classified_at=datetime.now(timezone.utc),
        )

    @classmethod
    def apply_classification_override(
        cls,
        system_result: ClassificationResult,
        override_classification: InvoiceClassification,
        override_reason: str,
        user_id: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Applies Finance classification override while strictly preserving system classification and reasons.
        """
        if not override_reason or not override_reason.strip():
            raise ValueError("An explicit reason is required when overriding invoice classification.")

        overridden = system_result.model_copy(deep=True)
        overridden.classification_override = override_classification
        overridden.classification_override_reason = override_reason.strip()
        overridden.classified_by = user_id
        overridden.classified_at = datetime.now(timezone.utc)
        return overridden


invoice_classifier = InvoiceClassifier()
