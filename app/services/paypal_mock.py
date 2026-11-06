"""PayPal Sandbox Mock Service.

Simulates PayPal Orders, Captures, and Customer Disputes APIs with realistic
HATEOAS links and payload structures for testing and demonstration purposes.
No paid APIs or real payment credentials required.
"""

from datetime import datetime, timedelta
import uuid
from typing import Dict, Any, Optional, List


class PayPalMock:
    """In-process demo stub only; production and multi-worker state use PayPal's API."""

    def __init__(self) -> None:
        """Initialize in-memory mock repository."""
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._captures: Dict[str, Dict[str, Any]] = {}
        self._disputes: Dict[str, Dict[str, Any]] = {}
        self._evidence_submissions: Dict[str, List[Dict[str, Any]]] = {}

    def create_order(
        self,
        amount: float,
        currency: str = "USD",
        intent: str = "CAPTURE",
        return_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulate creating a PayPal checkout order (v2/checkout/orders).

        Args:
            amount: Order monetary amount.
            currency: Three-character currency code.
            intent: Order intent, default 'CAPTURE'.
            return_url: Buyer return URL after approval.
            cancel_url: Buyer cancel URL.

        Returns:
            Simulated PayPal Order response object with HATEOAS links.
        """
        order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.utcnow().isoformat() + "Z"

        response = {
            "id": order_id,
            "status": "CREATED",
            "intent": intent,
            "create_time": now,
            "purchase_units": [
                {
                    "reference_id": f"ref_{order_id}",
                    "amount": {
                        "currency_code": currency.upper(),
                        "value": f"{amount:.2f}",
                    },
                    "payee": {
                        "merchant_id": "MERCHANT_SENTINEL_DEMO",
                        "email_address": "merchant@sentinel-demo.local",
                    },
                }
            ],
            "links": [
                {
                    "href": f"https://api.sandbox.paypal.com/v2/checkout/orders/{order_id}",
                    "rel": "self",
                    "method": "GET",
                },
                {
                    "href": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}",
                    "rel": "approve",
                    "method": "GET",
                },
                {
                    "href": f"https://api.sandbox.paypal.com/v2/checkout/orders/{order_id}/capture",
                    "rel": "capture",
                    "method": "POST",
                },
            ],
        }

        self._orders[order_id] = response
        return response

    def capture_order(self, order_id: str) -> Dict[str, Any]:
        """Simulate capturing an authorized PayPal order (v2/checkout/orders/{id}/capture).

        Args:
            order_id: PayPal order ID to capture.

        Returns:
            Simulated PayPal capture confirmation payload.
        """
        capture_id = f"CAP-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.utcnow().isoformat() + "Z"

        order = self._orders.get(order_id)
        amount_val = "100.00"
        currency_val = "USD"
        if order and "purchase_units" in order and order["purchase_units"]:
            amt_info = order["purchase_units"][0].get("amount", {})
            amount_val = amt_info.get("value", amount_val)
            currency_val = amt_info.get("currency_code", currency_val)

        response = {
            "id": order_id,
            "status": "COMPLETED",
            "payment_source": {
                "paypal": {
                    "account_id": "BUYER_TEST_ACCOUNT",
                    "email_address": "buyer@example.com",
                }
            },
            "purchase_units": [
                {
                    "reference_id": f"ref_{order_id}",
                    "payments": {
                        "captures": [
                            {
                                "id": capture_id,
                                "status": "COMPLETED",
                                "amount": {
                                    "currency_code": currency_val,
                                    "value": amount_val,
                                },
                                "final_capture": True,
                                "seller_protection": {
                                    "status": "ELIGIBLE",
                                    "dispute_categories": [
                                        "ITEM_NOT_RECEIVED",
                                        "UNAUTHORIZED_TRANSACTION",
                                    ],
                                },
                                "create_time": now,
                                "update_time": now,
                            }
                        ]
                    },
                }
            ],
            "links": [
                {
                    "href": f"https://api.sandbox.paypal.com/v2/checkout/orders/{order_id}",
                    "rel": "self",
                    "method": "GET",
                },
                {
                    "href": f"https://api.sandbox.paypal.com/v2/payments/captures/{capture_id}/refund",
                    "rel": "refund",
                    "method": "POST",
                },
            ],
        }

        if order_id in self._orders:
            self._orders[order_id]["status"] = "COMPLETED"
        self._captures[capture_id] = response
        return response

    def create_dispute(
        self,
        transaction_id: str,
        reason: str,
        amount: Optional[float] = None,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """Simulate filing a buyer dispute against a transaction (v1/customer/disputes).

        Args:
            transaction_id: The disputed seller transaction ID.
            reason: PayPal dispute reason (e.g. 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED', 'UNAUTHORISED').
            amount: Disputed amount (defaults to 75.00 if unspecified).
            currency: Currency code.

        Returns:
            Simulated PayPal dispute object.
        """
        dispute_id = f"PP-D-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow().isoformat() + "Z"
        val = f"{(amount if amount is not None else 75.0):.2f}"

        response = {
            "dispute_id": dispute_id,
            "create_time": now,
            "update_time": now,
            "disputed_transactions": [
                {
                    "seller_transaction_id": transaction_id,
                    "create_time": now,
                    "transaction_status": "COMPLETED",
                    "gross_amount": {
                        "currency_code": currency.upper(),
                        "value": val,
                    },
                }
            ],
            "reason": reason,
            "status": "UNDER_REVIEW",
            "dispute_state": "REQUIRED_ACTION",
            "dispute_amount": {
                "currency_code": currency.upper(),
                "value": val,
            },
            "dispute_channel": "INTERNAL",
            "dispute_life_cycle_stage": "CHARGEBACK",
            "seller_response_due_date": (
                datetime.utcnow().replace(microsecond=0) + timedelta(days=10)
            ).isoformat() + "Z",
            "links": [
                {
                    "href": f"https://api.sandbox.paypal.com/v1/customer/disputes/{dispute_id}",
                    "rel": "self",
                    "method": "GET",
                },
                {
                    "href": f"https://api.sandbox.paypal.com/v1/customer/disputes/{dispute_id}/provide-evidence",
                    "rel": "provide_evidence",
                    "method": "POST",
                },
                {
                    "href": f"https://api.sandbox.paypal.com/v1/customer/disputes/{dispute_id}/accept-claim",
                    "rel": "accept_claim",
                    "method": "POST",
                },
            ],
        }

        self._disputes[dispute_id] = response
        return response

    def submit_evidence(self, dispute_id: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate submitting defense evidence to PayPal Disputes API.

        Args:
            dispute_id: Target PayPal dispute ID.
            evidence: Structured merchant defense evidence bundle.

        Returns:
            Simulated acknowledgement payload with submission confirmation.
        """
        ack_code = f"ACK-PP-EV-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.utcnow().isoformat() + "Z"

        if dispute_id not in self._evidence_submissions:
            self._evidence_submissions[dispute_id] = []

        submission_entry = {
            "submission_id": ack_code,
            "timestamp": now,
            "evidence": evidence,
        }
        self._evidence_submissions[dispute_id].append(submission_entry)

        # Update dispute status in mock repository
        if dispute_id in self._disputes:
            self._disputes[dispute_id]["status"] = "UNDER_REVIEW"
            self._disputes[dispute_id]["dispute_state"] = "RESOLVING"

        return {
            "dispute_id": dispute_id,
            "status": "EVIDENCE_SUBMITTED",
            "acknowledgement_code": ack_code,
            "submission_time": now,
            "notes": (
                "Evidence bundle successfully logged in PayPal dispute resolution center. "
                "Dispute deflection evaluation in progress."
            ),
            "evidence_received_summary": {
                "keys_provided": list(evidence.keys()),
                "has_fulfillment_evidence": "fulfillment_evidence" in evidence or "tracking_number" in evidence,
                "has_device_fingerprint": "device_fingerprint" in evidence or "identity_evidence" in evidence,
                "has_compelling_evidence_factors": "ce3_inspired_evidence" in evidence or "qualifying_transactions" in evidence,
            },
            "links": [
                {
                    "href": f"https://api.sandbox.paypal.com/v1/customer/disputes/{dispute_id}",
                    "rel": "self",
                    "method": "GET",
                },
                {
                    "href": f"https://api.sandbox.paypal.com/v1/customer/disputes/{dispute_id}/appeal",
                    "rel": "appeal",
                    "method": "POST",
                },
            ],
        }
