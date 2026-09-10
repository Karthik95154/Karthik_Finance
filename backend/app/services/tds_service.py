import logging
from typing import Any, Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class TDSService:
    """
    Service for TDS assessment using AI model output and local deterministic TDS engine.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url

    async def check_health(self) -> bool:
        """Check if TDS service is active."""
        return True

    async def check_health_detailed(self) -> Dict[str, Any]:
        """Check status of TDS assessment subsystem."""
        return {
            "name": "Local TDS Assessment Engine",
            "status": "online",
            "status_code": 200,
            "message": "200 OK - Active & Responsive",
            "latency_ms": 0.0,
            "endpoint": "local",
        }

    async def assess_tds(self, invoice_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Consumes TDS suggestions from normalized model output or local review fallback.
        Bypasses redundant external HTTP calls to retired legacy endpoints.
        """
        if not isinstance(invoice_json, dict) or not invoice_json:
            raise ValueError("invoice_json must be a non-empty dictionary")

        if isinstance(invoice_json.get("tds_assessment"), dict) and invoice_json["tds_assessment"]:
            logger.info("[TDS-SERVICE] Returning normalized TDS suggestions from ModelResponseAdapter.")
            return {"tds_assessment": invoice_json["tds_assessment"]}

        # Check if tds_support exists in invoice_json or in raw extraction
        tds_sup = invoice_json.get("tds_support")
        if not tds_sup and isinstance(invoice_json.get("raw_vlm_output"), dict):
            tds_sup = invoice_json["raw_vlm_output"].get("tds_support")

        if isinstance(tds_sup, dict) and tds_sup:
            from app.services.model_response_adapter import ModelResponseAdapter
            pseudo_kimi = {
                "tds_support": tds_sup,
                "vendor_details": invoice_json.get("vendor_details") or {
                    "vendor_pan": invoice_json.get("vendor_pan"),
                    "vendor_gstin": invoice_json.get("vendor_gstin"),
                },
                "financial_details": invoice_json.get("financial_details") or {
                    "subtotal": invoice_json.get("subtotal"),
                    "total_amount": invoice_json.get("total_amount"),
                },
            }
            norm = ModelResponseAdapter.normalize_model_response(pseudo_kimi)
            norm_tds = norm.get("normalized_accounting", {}).get("tds_assessment")
            if norm_tds:
                logger.info("[TDS-SERVICE] Successfully evaluated statutory TDS from tds_support.")
                return {"tds_assessment": norm_tds}

        logger.info("[TDS-SERVICE] Bypassing legacy TDS endpoint. Returning default assessment for local engine.")
        return self._build_unavailable_response("Model-based TDS assessment applied")

    def _build_unavailable_response(self, error_reason: str) -> Dict[str, Any]:
        """Builds explicit review-required structure without fabricating values."""
        return {
            "tds_assessment": {
                "tds_applicable": None,
                "nature_of_payment": None,
                "tds_provision": None,
                "tds_section": None,
                "tds_rate": None,
                "tds_base_amount": None,
                "proposed_tds_amount": None,
                "tds_needs_review": True,
                "tds_reasoning": f"TDS service status: {error_reason}",
            }
        }


tds_service = TDSService()
