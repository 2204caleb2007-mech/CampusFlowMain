# ============================================================
# campus/role_system.py — Role-Aware Response System
# ============================================================
# Defines role-specific behaviors, tones, and access controls
# for the CampusFlow autonomous agent.
# ============================================================

from typing import Optional

# ── ROLE DEFINITIONS ────────────────────────────────────────────────

ROLES = {
    "student": {
        "name": "Student",
        "display_name": "Student",
        "description": "A student requesting lab bookings, leave, room bookings, or reporting complaints.",
        "tone": "friendly, supportive, simple",
        "language_level": "non-technical",
        "behavior": "Guide, suggest, explain clearly with step-by-step help",
        "icon": "🎓",
    },
    "teacher": {
        "name": "Teacher",
        "display_name": "Teacher",
        "description": "A teacher who reviews requests, monitors students, and enforces policies.",
        "tone": "professional, instructional",
        "language_level": "moderately technical",
        "behavior": "Provide actionable insights, enforce academic policies, assist in decision-making",
        "icon": "👨‍🏫",
    },
    "admin": {
        "name": "Admin",
        "display_name": "Administrator",
        "description": "An administrator who needs system-level insights and operational control.",
        "tone": "concise, authoritative, operational",
        "language_level": "technical and system-oriented",
        "behavior": "Focus on control, overrides, summaries, KPIs, and system-level insights",
        "icon": "⚙️",
    },
}

DEFAULT_ROLE = "student"


# ── ROLE-BASED SYSTEM PROMPTS ────────────────────────────────────────

def get_role_system_prompt(role: str, context: Optional[dict] = None) -> str:
    """
    Generate a role-specific system prompt that gets injected into every LLM call.
    
    Args:
        role: The current user role (student, teaching_assistant, admin)
        context: Optional context about the current workflow (workflow_type, etc.)
    
    Returns:
        A complete system prompt with role injection
    """
    role_info = ROLES.get(role, ROLES[DEFAULT_ROLE])
    
    base_prompt = f"""You are CampusFlow's autonomous campus assistant."""
    
    role_instruction = f"""
## ROLE CONTEXT
You are responding as: **{role_info['display_name']}**
- **Tone**: {role_info['tone']}
- **Language Level**: {role_info['language_level']}
- **Behavior**: {role_info['behavior']}

### Role-Specific Guidelines:

"""
    
    # Role-specific instructions
    if role == "student":
        role_instruction += """\
**For STUDENTS:**
- Use friendly, conversational language that is easy to understand
- Explain technical terms when you use them
- Provide step-by-step guidance for any process
- Be encouraging and supportive
- Always explain the "why" behind decisions
- When approving/rejecting requests, clearly state what happens next
- Suggest alternatives if the first option isn't available
- Use emojis appropriately to keep the tone light and approachable
"""
    elif role == "teacher":
        role_instruction += """\
**For TEACHERS:**
- Maintain a professional, instructional tone
- Be concise but thorough — Teachers appreciate efficiency
- Reference academic policies and rules when relevant
- Provide actionable next steps
- When escalate is needed, clearly explain the escalation path
- Offer insights that help with course management
- Include relevant policy details in your responses
- Be direct
"""
    elif role == "admin":
        role_instruction += """\
**For ADMINISTRATORS:**
- Be concise, authoritative, and operational
- Focus on system-level insights, KPIs, and operational data
- Use technical terminology freely
- Include relevant system IDs, timestamps, and metrics
- When showing data, present it in a structured, summary format
- Highlight any policy violations or anomalies
- Provide override capabilities when relevant
- Include audit-relevant information (who, what, when)
- Focus on efficiency and actionable outcomes
"""

    # Add workflow context if provided
    if context:
        workflow = context.get("workflow_type", "")
        if workflow:
            role_instruction += f"""
### Current Workflow Context
You are currently handling a **{workflow.replace('_', ' ').title()}** request.
"""

    return base_prompt + role_instruction


# ── ROLE-BASED RESPONSE MODULATION ────────────────────────────────────

def modulate_response(base_response: str, role: str, workflow_type: str = "") -> str:
    """
    Modulate a response based on the current role.
    This function can adjust the tone and content of pre-generated responses.
    
    Args:
        base_response: The original response content
        role: The current user role
        workflow_type: The current workflow type
    
    Returns:
        A modulated response string
    """
    role_info = ROLES.get(role, ROLES[DEFAULT_ROLE])
    
    # For admin, we can add system-level metadata
    if role == "admin" and workflow_type:
        admin_footer = f"""
---
*[{role_info['icon']} View in Automation tab for detailed logs, audit trail, and KPIs.]*"""
        return base_response + admin_footer
    
    # For students, add friendly footer
    elif role == "student":
        student_footer = f"""
---
{role_info['icon']} Need help with anything else? Feel free to ask!"""
        return base_response + student_footer
    
    elif role == "teacher":
        ta_footer = f"""
---
{role_info['icon']} View full details in the Automation tab."""
        return base_response + ta_footer
    
    return base_response


# ── ROLE-BASED DATA ACCESS CONTROL ────────────────────────────────────

def get_visible_fields(role: str, data_type: str) -> list[str]:
    """
    Get the list of fields visible to a specific role for a given data type.
    
    Args:
        role: The current user role
        data_type: The type of data being accessed (e.g., 'request', 'session', 'kpi')
    
    Returns:
        List of field names that are visible to this role
    """
    # All roles can see basic fields
    basic_fields = ["id", "type", "status", "created_at"]
    
    if data_type == "request":
        if role == "student":
            # Students see limited info about their own requests
            return basic_fields + ["workflow_type", "policy_result", "policy_reason"]
        elif role == "teacher":
            # Teachers see more detail but not system internals
            return basic_fields + ["workflow_type", "policy_result", "policy_reason", 
                                   "schema_json", "alternatives"]
        else:  # admin
            # Admins see everything
            return basic_fields + ["workflow_type", "policy_result", "policy_reason", 
                                   "schema_json", "alternatives", "actor_role", "audit_trail"]
    
    elif data_type == "session":
        if role == "student":
            return basic_fields + ["title", "workflow_type"]
        elif role == "teacher":
            return basic_fields + ["title", "workflow_type", "role"]
        else:  # admin
            return basic_fields + ["title", "workflow_type", "role", "all_metadata"]
    
    elif data_type == "kpi":
        if role == "student":
            # Students don't see KPIs
            return []
        elif role == "teacher":
            # Teachers see basic KPIs
            return ["total_requests", "resolution_rate_pct"]
        else:  # admin
            # Admins see all KPIs
            return ["total_requests", "resolution_rate_pct", "avg_resolution_mins",
                    "resolved", "by_workflow", "escalation_rate", "rejection_rate"]
    
    elif data_type == "logs":
        if role == "student":
            return ["timestamp", "message"]  # Only basic log info
        elif role == "teacher":
            return ["timestamp", "message", "level"]
        else:  # admin
            return ["timestamp", "message", "level", "stack_trace", "metadata"]
    
    return basic_fields


def can_access(role: str, resource: str, action: str = "read") -> bool:
    """
    Check if a role has permission to access a resource for a given action.
    
    Args:
        role: The current user role
        resource: The type of resource being accessed
        action: The action being performed (read, write, delete, admin)
    
    Returns:
        True if access is allowed, False otherwise
    """
    # Define role permissions
    permissions = {
        "student": {
            "request": ["read", "write"],
            "session": ["read", "write"],
            "logs": ["read"],
            "kpi": [],  # No KPI access
            "admin": [],
        },
        "teacher": {
            "request": ["read", "write", "admin"],
            "session": ["read", "write"],
            "logs": ["read", "write"],
            "kpi": ["read"],
            "admin": [],
        },
        "admin": {
            "request": ["read", "write", "delete", "admin"],
            "session": ["read", "write", "delete"],
            "logs": ["read", "write", "delete"],
            "kpi": ["read", "admin"],
            "admin": ["read", "write", "delete", "admin"],
        },
    }
    
    role_perms = permissions.get(role, {})
    resource_perms = role_perms.get(resource, [])
    
    return action in resource_perms


def get_access_denied_message(role: str, resource: str, action: str) -> str:
    """Return a role-appropriate message when access is denied."""
    messages = {
        "student": {
            "kpi": "KPI data is only available to staff and administrators.",
            "admin": "You don't have permission to access administrative functions.",
        },
        "teacher": {
            "admin": "You don't have permission to access administrative functions.",
        },
        "admin": {},
    }
    
    return messages.get(role, {}).get(resource, 
        f"Access denied: You don't have permission to {action} {resource}.")


# ── ROLE SWITCHING ────────────────────────────────────────────────────

def validate_role(role: str) -> bool:
    """Check if a role is valid."""
    return role in ROLES


def get_role_choices() -> list[tuple[str, str]]:
    """Return list of (role_key, display_name) tuples for UI dropdowns."""
    return [(key, val["display_name"]) for key, val in ROLES.items()]


def get_role_icon(role: str) -> str:
    """Get the icon for a role."""
    return ROLES.get(role, ROLES[DEFAULT_ROLE]).get("icon", "👤")
