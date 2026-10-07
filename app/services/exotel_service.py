import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger


class ExotelService:
    """
    Service client for Exotel Telephony APIs.
    Provides methods to initiate outbound calls with bidirectional AgentStream WebSockets.
    Uses HTTP Basic Auth (EXOTEL_API_KEY:EXOTEL_API_TOKEN).
    """

    def __init__(self):
        pass

    @property
    def is_configured(self) -> bool:
        """Check whether minimum Exotel credentials and caller ID are configured."""
        return bool(
            settings.EXOTEL_API_KEY
            and settings.EXOTEL_API_TOKEN
            and settings.EXOTEL_ACCOUNT_SID
        )

    def get_base_url(self) -> str:
        """Resolve Exotel API base URL from EXOTEL_SUBDOMAIN or default to api.exotel.com."""
        subdomain = (settings.EXOTEL_SUBDOMAIN or "").strip().rstrip("/")
        if not subdomain:
            return "https://api.exotel.com"
        if subdomain.startswith("http://") or subdomain.startswith("https://"):
            return subdomain
        if "exotel." in subdomain:
            return f"https://{subdomain}"
        return f"https://{subdomain}.exotel.com"

    async def initiate_outbound_call(
        self,
        to_phone: str,
        caller_id: Optional[str] = None,
        stream_url: Optional[str] = None,
        custom_field: Optional[str] = None,
        status_callback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call to destination number and connect to Exotel AgentStream.

        POST /v1/Accounts/{EXOTEL_ACCOUNT_SID}/Calls/connect
        Authentication: HTTP Basic Auth (EXOTEL_API_KEY : EXOTEL_API_TOKEN)
        Parameters:
            From: destination mobile number
            CallerId: EXOTEL_CALLER_ID
            StreamUrl: EXOTEL_PUBLIC_WSS_URL
            StreamType: 'bidirectional'
        """
        if not self.is_configured:
            logger.warning("Exotel outbound call aborted: Exotel credentials not configured in settings.")
            return {
                "success": False,
                "error": "Exotel credentials (EXOTEL_API_KEY, EXOTEL_API_TOKEN, EXOTEL_ACCOUNT_SID) are not fully configured.",
                "status_code": 400
            }

        effective_caller_id = caller_id or settings.EXOTEL_CALLER_ID
        if not effective_caller_id:
            logger.warning("Exotel outbound call aborted: EXOTEL_CALLER_ID is not configured.")
            return {
                "success": False,
                "error": "EXOTEL_CALLER_ID is required to place an outbound call.",
                "status_code": 400
            }

        effective_stream_url = stream_url or settings.effective_exotel_stream_url
        if not effective_stream_url or "example.com" in effective_stream_url:
            logger.warning(f"Exotel outbound call: StreamUrl '{effective_stream_url}' might not be publicly reachable.")

        endpoint_url = f"{self.get_base_url()}/v1/Accounts/{settings.EXOTEL_ACCOUNT_SID}/Calls/connect"

        payload = {
            "From": to_phone.strip(),
            "CallerId": effective_caller_id.strip(),
            "StreamUrl": effective_stream_url.strip(),
            "StreamType": "bidirectional",
        }
        if custom_field:
            payload["CustomField"] = custom_field
        if status_callback:
            payload["StatusCallback"] = status_callback

        # Log sanitized information without leaking secrets
        logger.info(
            f"Initiating Exotel outbound call to {payload['From']} (CallerId={payload['CallerId']}, "
            f"StreamUrl={payload['StreamUrl']})"
        )

        auth = httpx.BasicAuth(username=settings.EXOTEL_API_KEY, password=settings.EXOTEL_API_TOKEN)
        headers = {"Accept": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    endpoint_url,
                    data=payload,
                    auth=auth,
                    headers=headers
                )

            status_code = response.status_code
            resp_body = response.text

            # Parse JSON or XML response
            parsed_data: Dict[str, Any] = {}
            call_sid: Optional[str] = None

            try:
                parsed_data = response.json()
                call_obj = parsed_data.get("Call") or parsed_data
                call_sid = call_obj.get("Sid") or call_obj.get("CallSid") or call_obj.get("sid")
            except Exception:
                try:
                    root = ET.fromstring(resp_body)
                    xml_dict: Dict[str, Any] = {}
                    for elem in root.iter():
                        tag = elem.tag
                        tag_lower = tag.lower()
                        if elem.text and elem.text.strip() and len(elem) == 0:
                            xml_dict[tag] = elem.text.strip()
                            if "sid" in tag_lower and not call_sid:
                                call_sid = elem.text.strip()
                    parsed_data = xml_dict
                    parsed_data["raw_xml"] = resp_body
                except Exception:
                    parsed_data = {"raw_text": resp_body}

            is_success = 200 <= status_code < 300
            error_message: Optional[str] = None

            if is_success:
                logger.info(f"Exotel outbound call placed successfully (CallSid: {call_sid}, Status: {status_code})")
            else:
                if isinstance(parsed_data, dict):
                    error_message = (
                        parsed_data.get("Message")
                        or parsed_data.get("message")
                        or (parsed_data.get("RestException", {}).get("Message") if isinstance(parsed_data.get("RestException"), dict) else None)
                        or parsed_data.get("error")
                    )
                if not error_message:
                    error_message = f"Exotel API returned HTTP {status_code}"
                logger.error(f"Exotel outbound call failed (Status: {status_code}, Error: {error_message})")

            resp_result: Dict[str, Any] = {
                "success": is_success,
                "status_code": status_code,
                "call_sid": call_sid,
                "data": parsed_data
            }
            if error_message:
                resp_result["error"] = error_message

            return resp_result

        except Exception as exc:
            logger.error(f"Exception during Exotel outbound call request: {exc}", exc_info=True)
            return {
                "success": False,
                "error": str(exc),
                "status_code": 500
            }


exotel_service = ExotelService()
