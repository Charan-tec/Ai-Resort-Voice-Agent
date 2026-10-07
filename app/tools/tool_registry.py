import json
from typing import Any, Callable, Coroutine, Dict, List, Optional
from app.core.logging import logger
from app.tools.availability import check_availability
from app.tools.pricing import calculate_price
from app.tools.booking import create_booking, save_booking
from app.tools.email import send_confirmation_email
from app.tools.retrieval import search_resort_knowledge

# Define the EXACT 6 Tool Schemas formatted for OpenAI / LLM Function Calling
TOOLS_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check luxury resort room availability for given dates and guest count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format (e.g. '2026-10-01')"
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format (e.g. '2026-10-04')"
                    },
                    "room_type": {
                        "type": "string",
                        "enum": ["villa", "suite", "bungalow"],
                        "description": "Optional specific room category requested by guest"
                    },
                    "guests": {
                        "type": "integer",
                        "default": 2,
                        "description": "Number of adult/child guests staying in room"
                    }
                },
                "required": ["check_in", "check_out"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_price",
            "description": "Compute comprehensive pricing quote including lodging rate, resort fees, taxes, and add-on services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_id": {
                        "type": "string",
                        "description": "The room_id of the room being priced (e.g. 'villa-ocean-101')"
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date (YYYY-MM-DD)"
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date (YYYY-MM-DD)"
                    },
                    "booking_id": {
                        "type": "string",
                        "description": "Optional booking ID or confirmation number to retrieve details from existing reservation"
                    },
                    "add_ons": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional extras: 'breakfast', 'spa_credit', 'airport_shuttle', 'champagne'"
                    }
                },
                "required": ["room_id", "check_in", "check_out"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_booking",
            "description": "Stage 1 of reservation: Places a 15-minute tentative hold on the room and returns a pending_token. Does NOT confirm.",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_id": {
                        "type": "string",
                        "description": "The room_id chosen by the guest"
                    },
                    "guest_name": {
                        "type": "string",
                        "description": "Full legal name of primary guest"
                    },
                    "guest_email": {
                        "type": "string",
                        "description": "Guest contact email address"
                    },
                    "guest_phone": {
                        "type": "string",
                        "description": "Guest contact phone number"
                    },
                    "check_in": {
                        "type": "string",
                        "description": "Check-in date (YYYY-MM-DD)"
                    },
                    "check_out": {
                        "type": "string",
                        "description": "Check-out date (YYYY-MM-DD)"
                    },
                    "total_price": {
                        "type": "number",
                        "description": "Total agreed quoted price in USD from calculate_price"
                    },
                    "guests": {
                        "type": "integer",
                        "default": 2
                    },
                    "add_ons": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["room_id", "check_in", "check_out"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_booking",
            "description": "Stage 2 of reservation: Confirms the tentative hold into an official confirmed booking using the pending_token. Idempotent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pending_token": {
                        "type": "string",
                        "description": "The pending hold token issued by create_booking"
                    }
                },
                "required": ["pending_token"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_confirmation_email",
            "description": "Dispatches official booking confirmation and resort itinerary email to customer asynchronously.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {
                        "type": "string",
                        "description": "The confirmed booking reference code (e.g. 'RES-A1B2C3D4')"
                    },
                    "customer_email": {
                        "type": "string",
                        "description": "Destination email address for itinerary"
                    }
                },
                "required": ["booking_id", "customer_email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_resort_knowledge",
            "description": "Searches resort knowledge base for policies, check-in/out hours, pool rules, spa menus, and dining details. Probes fast prefetch cache first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Specific question or topic (e.g. 'infinity pool hours', 'cancellation fee')"
                    },
                    "top_k": {
                        "type": "integer",
                        "default": 3,
                        "description": "Number of snippets to retrieve"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


import inspect
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal


class ToolRegistry:
    """
    Central registry managing EXACTLY the six required agent tools.
    Provides schema definitions for LLM binding and dispatches function execution.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable[..., Coroutine]] = {
            "check_availability": check_availability,
            "calculate_price": calculate_price,
            "create_booking": create_booking,
            "save_booking": save_booking,
            "send_confirmation_email": send_confirmation_email,
            "search_resort_knowledge": search_resort_knowledge,
        }

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return the six function schemas for LLM binding."""
        return TOOLS_SCHEMAS

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        db_session: Optional[AsyncSession] = None
    ) -> dict:
        """Execute the requested tool with validated arguments and safe session propagation."""
        handler = self._handlers.get(tool_name)
        if not handler:
            error_msg = f"Unknown tool requested: '{tool_name}'"
            logger.error(error_msg)
            return {
                "ok": False,
                "error": error_msg,
                "spoken_hint": "I encountered an error executing that request."
            }

        logger.info(f"Executing tool '{tool_name}' with args: {arguments}")

        # Inspect if handler accepts db_session dependency
        sig = inspect.signature(handler)
        accepts_db = "db_session" in sig.parameters

        tool_args = dict(arguments)

        if not accepts_db:
            try:
                result = await handler(**tool_args)
                return result
            except Exception as exc:
                logger.error(f"Error executing tool '{tool_name}': {exc}", exc_info=True)
                return {
                    "ok": False,
                    "error": str(exc),
                    "spoken_hint": f"I had trouble processing that action: {exc}"
                }

        # Tool accepts db_session: apply session ownership policy
        caller_owns_session = (db_session is not None)
        session_ctx = None if caller_owns_session else AsyncSessionLocal()
        session = db_session if caller_owns_session else await session_ctx.__aenter__()

        try:
            tool_args["db_session"] = session
            result = await handler(**tool_args)
            if not caller_owns_session:
                await session.commit()
            return result
        except Exception as exc:
            if not caller_owns_session:
                await session.rollback()
            logger.error(f"Error executing tool '{tool_name}': {exc}", exc_info=True)
            return {
                "ok": False,
                "error": str(exc),
                "spoken_hint": f"I had trouble processing that action: {exc}"
            }
        finally:
            if not caller_owns_session and session_ctx:
                await session_ctx.__aexit__(None, None, None)


tool_registry = ToolRegistry()
