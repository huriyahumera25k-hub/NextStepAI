import streamlit as st
import requests
import json
import re
import sqlite3
import base64
import uuid
import html

from datetime import datetime, date, timedelta
from urllib.parse import urlparse


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="NextStep AI",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

DATABASE_FILE = "nextstep_ai.db"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

REQUEST_TIMEOUT = 45


LANGUAGE_CODES = {
    "English": "en-IN",
    "Hindi": "hi-IN",
    "Telugu": "te-IN",
    "Tamil": "ta-IN",
    "Kannada": "kn-IN",
    "Malayalam": "ml-IN",
    "Marathi": "mr-IN",
    "Bengali": "bn-IN",
    "Gujarati": "gu-IN",
    "Urdu": "ur-IN",
}


TTS_SUPPORTED = {
    "English",
    "Hindi",
    "Telugu",
    "Tamil",
    "Kannada",
    "Malayalam",
    "Marathi",
    "Bengali",
    "Gujarati",
}


# ============================================================
# OFFICIAL SERVICE REGISTRY
# ============================================================
#
# These are intentionally direct, known official resources.
# The app does NOT invent a government submission endpoint.
#
# Actual authentication, OTP, CAPTCHA, payment and final
# submission remain on the official government portal.
#

SERVICE_REGISTRY = {

    "income_certificate": {
        "keywords": [
            "income certificate",
            "income cert",
            "income proof",
            "annual income certificate",
            "income document",
            "income certificate telangana",
            "income certificate ts",
        ],
        "service_name": "Income Certificate",
        "service_category": "Certificate",
        "jurisdiction": "Telangana",
        "department": "Revenue Department",

        "portal_url": (
            "https://ts.meeseva.telangana.gov.in/"
        ),

        "state_service_url": (
            "https://www.telangana.gov.in/services/state-services/"
        ),

        "form_url": (
            "https://ts.meeseva.telangana.gov.in/"
            "meeseva/downloadzip.htm?"
            "filename=IncomeGeneralApplicationForm.pdf"
        ),

        "steps": [
            "Open the official Telangana MeeSeva portal.",
            "Select the Income Certificate service.",
            "Enter the applicant details requested by MeeSeva.",
            "Upload the documents requested by the official portal.",
            "Review the entered information.",
            "Complete any authentication, payment or verification required by MeeSeva.",
            "Submit the application on the official government portal.",
            "Save the application/reference number."
        ],

        "requirements": [
            {
                "name": "Applicant details",
                "description": (
                    "The official application form contains "
                    "applicant and relationship details."
                ),
                "mandatory": True,
            },
            {
                "name": "Address details",
                "description": (
                    "Village/town, locality, mandal and district "
                    "information may be required."
                ),
                "mandatory": True,
            },
            {
                "name": "Income information",
                "description": (
                    "The application concerns annual income from "
                    "all sources."
                ),
                "mandatory": True,
            },
            {
                "name": "Supporting documents",
                "description": (
                    "Upload the documents requested by the official "
                    "MeeSeva application."
                ),
                "mandatory": True,
            },
        ],

        "note": (
            "The Telangana State Portal lists Income Certificate "
            "as an online state service. The official Telangana "
            "portal also publishes the Income Certificate form."
        ),
    },

    "caste_certificate": {
        "keywords": [
            "caste certificate",
            "caste cert",
            "community certificate",
            "sc certificate",
            "st certificate",
            "bc certificate",
            "obc certificate",
        ],
        "service_name": "Caste Certificate",
        "service_category": "Certificate",
        "jurisdiction": "Telangana",
        "department": "Revenue Department",

        "portal_url": (
            "https://ts.meeseva.telangana.gov.in/"
        ),

        "state_service_url": (
            "https://www.telangana.gov.in/services/state-services/"
        ),

        "form_url": "",

        "steps": [
            "Open the official Telangana MeeSeva portal.",
            "Select the appropriate Caste/Community Certificate service.",
            "Enter the applicant information requested by MeeSeva.",
            "Upload the documents requested by the official portal.",
            "Review the application.",
            "Complete any required authentication or verification.",
            "Submit the application through the official portal.",
            "Save the application/reference number."
        ],

        "requirements": [
            {
                "name": "Applicant information",
                "description": (
                    "Provide the information requested by the "
                    "official application."
                ),
                "mandatory": True,
            },
            {
                "name": "Address information",
                "description": (
                    "Provide the jurisdiction/address information "
                    "requested by the portal."
                ),
                "mandatory": True,
            },
            {
                "name": "Supporting documents",
                "description": (
                    "Use the current document requirements shown "
                    "by the official MeeSeva service."
                ),
                "mandatory": True,
            },
        ],

        "note": (
            "The Telangana State Portal lists online Caste "
            "Certificate application under the Revenue Department."
        ),
    },

    "residence_certificate": {
        "keywords": [
            "residence certificate",
            "residential certificate",
            "domicile certificate",
            "nativity certificate",
            "residence proof",
        ],
        "service_name": "Residence / Domicile Certificate",
        "service_category": "Certificate",
        "jurisdiction": "Telangana",
        "department": "Revenue Department",

        "portal_url": (
            "https://ts.meeseva.telangana.gov.in/"
        ),

        "state_service_url": (
            "https://www.telangana.gov.in/services/state-services/"
        ),

        "form_url": "",

        "steps": [
            "Open the official Telangana MeeSeva portal.",
            "Select the Residence/Domicile service.",
            "Enter the requested applicant details.",
            "Upload the documents requested by the official portal.",
            "Review the information.",
            "Complete any required authentication or verification.",
            "Submit through the official government portal.",
            "Save the application/reference number."
        ],

        "requirements": [
            {
                "name": "Applicant information",
                "description": (
                    "Provide the details requested by the official portal."
                ),
                "mandatory": True,
            },
            {
                "name": "Residence information",
                "description": (
                    "Provide current/residential information requested "
                    "by the application."
                ),
                "mandatory": True,
            },
            {
                "name": "Supporting documents",
                "description": (
                    "Follow the current document checklist shown by "
                    "MeeSeva."
                ),
                "mandatory": True,
            },
        ],

        "note": (
            "The Telangana State Portal lists Domicile/Residence "
            "Certificate under Revenue Department services."
        ),
    },

    "birth_certificate": {
        "keywords": [
            "birth certificate",
            "birth registration",
            "birth cert",
        ],
        "service_name": "Birth Certificate",
        "service_category": "Certificate",
        "jurisdiction": "Telangana",
        "department": "Municipal Administration & Urban Development",

        "portal_url": (
            "https://ts.meeseva.telangana.gov.in/"
        ),

        "state_service_url": (
            "https://www.telangana.gov.in/services/state-services/"
        ),

        "form_url": (
            "https://ts.meeseva.telangana.gov.in/"
            "meeseva/downloadzip.htm?"
            "filename=CDMAAPPLICATIONFORBIRTHCERTIFICATE.pdf"
        ),

        "steps": [
            "Open the official Telangana government service portal.",
            "Select the Birth Certificate service.",
            "Enter the requested birth-registration information.",
            "Upload the documents requested by the official service.",
            "Review the application.",
            "Complete any required verification or payment.",
            "Submit through the official government portal.",
            "Save the application/reference number."
        ],

        "requirements": [
            {
                "name": "Birth details",
                "description": (
                    "Provide the information requested about the birth."
                ),
                "mandatory": True,
            },
            {
                "name": "Applicant/parent information",
                "description": (
                    "Provide the details requested by the official form."
                ),
                "mandatory": True,
            },
            {
                "name": "Supporting documents",
                "description": (
                    "Follow the current official document requirements."
                ),
                "mandatory": True,
            },
        ],

        "note": (
            "The Telangana State Portal lists Birth Certificate "
            "as a state service."
        ),
    },

    "death_certificate": {
        "keywords": [
            "death certificate",
            "death registration",
            "death cert",
        ],
        "service_name": "Death Certificate",
        "service_category": "Certificate",
        "jurisdiction": "Telangana",
        "department": "Municipal Administration & Urban Development",

        "portal_url": (
            "https://ts.meeseva.telangana.gov.in/"
        ),

        "state_service_url": (
            "https://www.telangana.gov.in/services/state-services/"
        ),

        "form_url": (
            "https://ts.meeseva.telangana.gov.in/"
            "meeseva/downloadzip.htm?"
            "filename=CDMAAPPLICATIONFORDEATHCERTIFICATE.pdf"
        ),

        "steps": [
            "Open the official Telangana government service portal.",
            "Select the Death Certificate service.",
            "Enter the requested registration information.",
            "Upload the documents requested by the official service.",
            "Review the application.",
            "Complete any required verification or payment.",
            "Submit through the official government portal.",
            "Save the application/reference number."
        ],

        "requirements": [
            {
                "name": "Death details",
                "description": (
                    "Provide the information requested about the death."
                ),
                "mandatory": True,
            },
            {
                "name": "Applicant information",
                "description": (
                    "Provide the details requested by the official form."
                ),
                "mandatory": True,
            },
            {
                "name": "Supporting documents",
                "description": (
                    "Follow the current official document requirements."
                ),
                "mandatory": True,
            },
        ],

        "note": (
            "The Telangana State Portal lists Death Certificate "
            "as a state service."
        ),
    },
}


# ============================================================
# DEFAULT SESSION STATE
# ============================================================

DEFAULT_STATE = {

    "conversation_id": None,

    "typed_service_request": "",
    "voice_text": "",

    "service_identified": False,
    "identified_service": None,

    "workflow_active": False,
    "workflow_step": 0,

    "requirements": None,

    "official_url": "",
    "official_form_url": "",
    "official_state_url": "",

    "applicant_name": "",
    "phone": "",
    "email": "",
    "address": "",
    "additional_information": "",

    "application_id": None,
    "submission_result": None,

    "last_ai_response": "",

    "language": "English",

    "_request_logged": "",
}


for key, value in DEFAULT_STATE.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SECRETS
# ============================================================

def get_secret(name, default=""):

    try:
        value = st.secrets.get(name, default)

        if value is None:
            return default

        return str(value).strip()

    except Exception:
        return default


OPENROUTER_API_KEY = get_secret(
    "OPENROUTER_API_KEY"
)

OPENROUTER_MODEL = get_secret(
    "OPENROUTER_MODEL",
    DEFAULT_MODEL,
)

SARVAM_API_KEY = get_secret(
    "SARVAM_API_KEY"
)

HOLIDAYS_RAW = get_secret(
    "HOLIDAYS",
    "[]",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 44px;
        font-weight: 850;
        letter-spacing: -1.5px;
        margin-bottom: 0;
    }

    .subtitle {
        font-size: 17px;
        opacity: 0.70;
        margin-top: 4px;
        margin-bottom: 22px;
    }

    .hero-card {
        padding: 28px;
        border-radius: 22px;
        border: 1px solid rgba(128,128,128,0.22);
        background: linear-gradient(
            135deg,
            rgba(80,120,255,0.10),
            rgba(120,80,220,0.05)
        );
        margin-bottom: 20px;
    }

    .workflow-card {
        padding: 22px;
        border-radius: 18px;
        border: 1px solid rgba(128,128,128,0.22);
        margin: 12px 0;
    }

    .step-active {
        padding: 18px;
        border-radius: 16px;
        border: 2px solid rgba(80,120,255,0.55);
        background: rgba(80,120,255,0.08);
        margin-bottom: 16px;
    }

    .step-complete {
        padding: 15px;
        border-radius: 14px;
        border: 1px solid rgba(50,180,100,0.35);
        background: rgba(50,180,100,0.08);
        margin-bottom: 10px;
    }

    .info-box {
        padding: 18px;
        border-radius: 15px;
        border: 1px solid rgba(80,130,220,0.35);
        background: rgba(80,130,220,0.08);
    }

    .warning-box {
        padding: 18px;
        border-radius: 15px;
        border: 1px solid rgba(220,170,50,0.35);
        background: rgba(220,170,50,0.08);
    }

    .small-muted {
        font-size: 13px;
        opacity: 0.68;
    }

    .conversation-title {
        font-weight: 600;
        font-size: 14px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATABASE
# ============================================================

def get_db():

    connection = sqlite3.connect(
        DATABASE_FILE,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (

            conversation_id TEXT PRIMARY KEY,

            title TEXT NOT NULL,

            state_json TEXT,

            created_at TEXT,

            updated_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_messages (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            conversation_id TEXT NOT NULL,

            role TEXT NOT NULL,

            content TEXT NOT NULL,

            created_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (

            application_id TEXT PRIMARY KEY,

            service_name TEXT,

            category TEXT,

            jurisdiction TEXT,

            department TEXT,

            applicant_name TEXT,

            phone TEXT,

            email TEXT,

            address TEXT,

            additional_information TEXT,

            official_url TEXT,

            submission_date TEXT,

            status TEXT,

            created_at TEXT,

            updated_at TEXT
        )
        """
    )

    connection.commit()
    connection.close()


init_database()


# ============================================================
# CONVERSATION STATE
# ============================================================

CONVERSATION_STATE_KEYS = [

    "typed_service_request",
    "voice_text",

    "service_identified",
    "identified_service",

    "workflow_active",
    "workflow_step",

    "requirements",

    "official_url",
    "official_form_url",
    "official_state_url",

    "applicant_name",
    "phone",
    "email",
    "address",
    "additional_information",

    "application_id",
    "submission_result",

    "last_ai_response",

    "language",

    "_request_logged",
]


def get_conversation_state():

    state = {}

    for key in CONVERSATION_STATE_KEYS:

        value = st.session_state.get(key)

        try:

            json.dumps(
                value,
                ensure_ascii=False,
            )

            state[key] = value

        except Exception:

            state[key] = None

    return state


def restore_conversation_state(state):

    if not isinstance(state, dict):
        return

    for key in CONVERSATION_STATE_KEYS:

        if key in state:
            st.session_state[key] = state[key]


def reset_conversation_state():

    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value


def create_conversation(title="New Conversation"):

    conversation_id = str(uuid.uuid4())

    now = datetime.now().isoformat()

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO conversations (

            conversation_id,
            title,
            state_json,
            created_at,
            updated_at

        )

        VALUES (?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            title,
            json.dumps({}),
            now,
            now,
        ),
    )

    connection.commit()
    connection.close()

    return conversation_id


def save_conversation_state():

    conversation_id = st.session_state.get(
        "conversation_id"
    )

    if not conversation_id:
        return

    state = get_conversation_state()

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE conversations

        SET
            state_json = ?,
            updated_at = ?

        WHERE conversation_id = ?
        """,
        (
            json.dumps(
                state,
                ensure_ascii=False,
            ),
            datetime.now().isoformat(),
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


def update_conversation_title(title):

    conversation_id = st.session_state.get(
        "conversation_id"
    )

    if not conversation_id:
        return

    title = re.sub(
        r"\s+",
        " ",
        str(title).strip(),
    )

    if not title:
        title = "New Conversation"

    if len(title) > 60:
        title = title[:57] + "..."

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE conversations

        SET
            title = ?,
            updated_at = ?

        WHERE conversation_id = ?
        """,
        (
            title,
            datetime.now().isoformat(),
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


def add_conversation_message(role, content):

    conversation_id = st.session_state.get(
        "conversation_id"
    )

    if not conversation_id:
        return

    if not content:
        return

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO conversation_messages (

            conversation_id,
            role,
            content,
            created_at

        )

        VALUES (?, ?, ?, ?)
        """,
        (
            conversation_id,
            role,
            str(content),
            datetime.now().isoformat(),
        ),
    )

    cursor.execute(
        """
        UPDATE conversations

        SET updated_at = ?

        WHERE conversation_id = ?
        """,
        (
            datetime.now().isoformat(),
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


def get_conversations():

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            conversation_id,
            title,
            created_at,
            updated_at

        FROM conversations

        ORDER BY updated_at DESC
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return rows


def load_conversation(conversation_id):

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *

        FROM conversations

        WHERE conversation_id = ?
        """,
        (conversation_id,),
    )

    row = cursor.fetchone()

    connection.close()

    if not row:
        return False

    try:

        state = json.loads(
            row["state_json"] or "{}"
        )

    except Exception:

        state = {}

    reset_conversation_state()

    st.session_state[
        "conversation_id"
    ] = conversation_id

    restore_conversation_state(state)

    return True


def delete_conversation(conversation_id):

    if not conversation_id:
        return

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM conversation_messages

        WHERE conversation_id = ?
        """,
        (conversation_id,),
    )

    cursor.execute(
        """
        DELETE FROM conversations

        WHERE conversation_id = ?
        """,
        (conversation_id,),
    )

    connection.commit()
    connection.close()


def ensure_current_conversation():

    if st.session_state.get(
        "conversation_id"
    ):
        return

    conversation_id = create_conversation()

    st.session_state[
        "conversation_id"
    ] = conversation_id

    save_conversation_state()


ensure_current_conversation()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🧭 NextStep AI")

    st.caption(
        "Action-first government service assistant"
    )

    if st.button(
        "➕ New Conversation",
        use_container_width=True,
        type="primary",
    ):

        save_conversation_state()

        new_id = create_conversation()

        reset_conversation_state()

        st.session_state[
            "conversation_id"
        ] = new_id

        save_conversation_state()

        st.rerun()

    st.divider()

    st.markdown("### 🕘 Conversations")

    conversations = get_conversations()

    current_id = st.session_state.get(
        "conversation_id"
    )

    for conversation in conversations:

        conversation_id = conversation[
            "conversation_id"
        ]

        title = (
            conversation["title"]
            or "New Conversation"
        )

        display_title = title

        if len(display_title) > 30:
            display_title = (
                display_title[:27]
                + "..."
            )

        col1, col2 = st.columns(
            [5, 1],
            gap="small",
        )

        with col1:

            prefix = (
                "🟢"
                if conversation_id == current_id
                else "💬"
            )

            if st.button(
                f"{prefix} {display_title}",
                key=f"open_{conversation_id}",
                use_container_width=True,
            ):

                if conversation_id != current_id:

                    save_conversation_state()

                    load_conversation(
                        conversation_id
                    )

                    st.rerun()

        with col2:

            if st.button(
                "🗑️",
                key=f"delete_{conversation_id}",
                use_container_width=True,
            ):

                deleting_current = (
                    conversation_id
                    == current_id
                )

                delete_conversation(
                    conversation_id
                )

                if deleting_current:

                    reset_conversation_state()

                    new_id = create_conversation()

                    st.session_state[
                        "conversation_id"
                    ] = new_id

                    save_conversation_state()

                st.rerun()

    st.divider()

    current_language = st.session_state.get(
        "language",
        "English",
    )

    language = st.selectbox(
        "🌐 Language",
        list(LANGUAGE_CODES.keys()),
        index=(
            list(LANGUAGE_CODES.keys()).index(
                current_language
            )
            if current_language in LANGUAGE_CODES
            else 0
        ),
    )

    st.session_state["language"] = language

    save_conversation_state()

    st.divider()

    st.markdown("### ⚡ Action Workflow")

    st.markdown(
        """
        **1. Tell NextStep AI**

        Describe the government service.

        **2. Start**

        The service workflow starts immediately.

        **3. Prepare**

        Review the requirements and prepare information.

        **4. Continue**

        Each button takes you directly to the next step.

        **5. Government Portal**

        The official government portal handles authentication,
        OTP, CAPTCHA, payment and final submission.

        **6. Track**

        Save the government application/reference number.
        """
    )

    st.divider()

    st.caption(
        "🔐 NextStep AI does not bypass CAPTCHA, OTP, "
        "biometric verification or other government security controls."
    )


# ============================================================
# OPENROUTER
# ============================================================

def openrouter_chat(
    system_prompt,
    user_prompt,
    temperature=0.1,
):

    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": (
            f"Bearer {OPENROUTER_API_KEY}"
        ),
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "temperature": temperature,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    }

    try:

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        choices = data.get(
            "choices",
            [],
        )

        if not choices:
            return None

        content = choices[0].get(
            "message",
            {},
        ).get(
            "content",
            "",
        )

        if isinstance(content, list):

            parts = []

            for item in content:

                if isinstance(item, dict):

                    parts.append(
                        str(
                            item.get(
                                "text",
                                "",
                            )
                        )
                    )

            content = "".join(parts)

        return str(content).strip()

    except Exception:
        return None


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):

    if not text:
        return None

    try:
        return json.loads(
            text.strip()
        )

    except Exception:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL,
    )

    if match:

        try:
            return json.loads(
                match.group(0)
            )

        except Exception:
            pass

    return None


# ============================================================
# URL VALIDATION
# ============================================================

def is_official_url(url):

    if not url:
        return False

    try:

        parsed = urlparse(
            str(url).strip()
        )

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return False

        hostname = (
            parsed.hostname or ""
        ).lower()

        return (
            hostname.endswith(".gov.in")
            or hostname.endswith(".nic.in")
            or hostname == "gov.in"
        )

    except Exception:
        return False


# ============================================================
# SERVICE MATCHING
# ============================================================

def normalize_text(text):

    text = str(text or "").lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def find_registry_service(user_request):

    normalized = normalize_text(
        user_request
    )

    best_key = None
    best_score = 0

    for key, service in SERVICE_REGISTRY.items():

        score = 0

        for keyword in service.get(
            "keywords",
            [],
        ):

            keyword_normalized = (
                normalize_text(keyword)
            )

            if keyword_normalized in normalized:

                score += len(
                    keyword_normalized.split()
                )

        if score > best_score:

            best_score = score
            best_key = key

    if best_key:

        service = dict(
            SERVICE_REGISTRY[best_key]
        )

        service["registry_key"] = best_key

        service["confidence"] = min(
            1.0,
            0.65 + (
                best_score * 0.08
            ),
        )

        return service

    return None


# ============================================================
# AI SERVICE IDENTIFICATION
# ============================================================

def identify_service(user_request):

    # First use the verified service registry.
    registry_match = (
        find_registry_service(
            user_request
        )
    )

    if registry_match:
        return registry_match

    if not OPENROUTER_API_KEY:
        return None

    system_prompt = """
You are NextStep AI's government-service identification engine.

Identify the most likely government/public service from the user's
natural-language request.

Return ONLY valid JSON.

Schema:

{
    "service_name": "",
    "service_category": "",
    "jurisdiction": "",
    "department": "",
    "intent": "",
    "confidence": 0
}

Rules:

1. Do not invent an official URL.
2. Do not invent a government procedure.
3. If jurisdiction is unknown, use "Unknown".
4. confidence must be between 0 and 1.
5. Keep the answer concise.
"""

    result = openrouter_chat(
        system_prompt,
        user_request,
        temperature=0.0,
    )

    data = extract_json(result)

    if not data:
        return None

    data["registry_key"] = "generic"

    try:

        data["confidence"] = float(
            data.get(
                "confidence",
                0,
            )
        )

    except Exception:

        data["confidence"] = 0

    data["portal_url"] = (
        "https://www.telangana.gov.in/services/state-services/"
        if str(
            data.get(
                "jurisdiction",
                "",
            )
        ).lower()
        == "telangana"
        else ""
    )

    data["form_url"] = ""

    data["state_service_url"] = (
        "https://www.telangana.gov.in/services/state-services/"
        if str(
            data.get(
                "jurisdiction",
                "",
            )
        ).lower()
        == "telangana"
        else ""
    )

    data["steps"] = [
        "Open the official government service portal.",
        "Locate the requested service.",
        "Enter the information requested by the official portal.",
        "Upload the documents requested by the official portal.",
        "Review the application.",
        "Complete any required verification.",
        "Submit through the official government portal.",
        "Save the application/reference number.",
    ]

    data["requirements"] = [
        {
            "name": "Applicant information",
            "description": (
                "Provide the information requested by "
                "the official service."
            ),
            "mandatory": True,
        },
        {
            "name": "Supporting documents",
            "description": (
                "Follow the current official portal's "
                "document checklist."
            ),
            "mandatory": True,
        },
    ]

    data["note"] = (
        "For services not yet configured with a direct "
        "workflow, NextStep AI sends the user to the "
        "official government service directory."
    )

    return data


# ============================================================
# REQUIREMENTS
# ============================================================

def get_requirements(service):

    requirements = service.get(
        "requirements",
        [],
    )

    if requirements:
        return requirements

    return [
        {
            "name": "Applicant information",
            "description": (
                "Information requested by the official portal."
            ),
            "mandatory": True,
        },
        {
            "name": "Supporting documents",
            "description": (
                "Documents requested by the official portal."
            ),
            "mandatory": True,
        },
    ]


# ============================================================
# SPEECH TO TEXT
# ============================================================

def speech_to_text(
    audio_bytes,
    language_name,
):

    if not SARVAM_API_KEY:
        return None

    language_code = LANGUAGE_CODES.get(
        language_name,
        "en-IN",
    )

    headers = {
        "api-subscription-key": SARVAM_API_KEY,
    }

    files = {
        "file": (
            "voice.wav",
            audio_bytes,
            "audio/wav",
        )
    }

    data = {
        "model": "saaras:v4",
        "language_code": language_code,
        "mode": "transcribe",
    }

    try:

        response = requests.post(
            SARVAM_STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        result = response.json()

        return (
            result.get("transcript")
            or result.get("text")
            or ""
        ).strip()

    except Exception:
        return None


# ============================================================
# TEXT TO SPEECH
# ============================================================

def text_to_speech(
    text,
    language_name,
):

    if not SARVAM_API_KEY:
        return None

    if language_name not in TTS_SUPPORTED:
        return None

    language_code = LANGUAGE_CODES.get(
        language_name,
        "en-IN",
    )

    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "text": text[:5000],
        "target_language_code": language_code,
        "language_code": language_code,
        "model": "bulbul:v3",
        "speaker": "shubh",
    }

    try:

        response = requests.post(
            SARVAM_TTS_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        audios = data.get(
            "audios"
        )

        if isinstance(
            audios,
            list
        ) and audios:

            audio_b64 = audios[0]

        else:

            audio_b64 = data.get(
                "audio"
            )

        if not audio_b64:
            return None

        return base64.b64decode(
            audio_b64
        )

    except Exception:
        return None


# ============================================================
# LOCAL APPLICATION STORAGE
# ============================================================

def save_local_application(
    service,
    applicant,
):

    application_id = (
        "NS-"
        + datetime.now().strftime(
            "%Y%m%d"
        )
        + "-"
        + uuid.uuid4().hex[:8].upper()
    )

    now = datetime.now().isoformat()

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO applications (

            application_id,
            service_name,
            category,
            jurisdiction,
            department,
            applicant_name,
            phone,
            email,
            address,
            additional_information,
            official_url,
            submission_date,
            status,
            created_at,
            updated_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,

            service.get(
                "service_name",
                "",
            ),

            service.get(
                "service_category",
                "",
            ),

            service.get(
                "jurisdiction",
                "",
            ),

            service.get(
                "department",
                "",
            ),

            applicant.get(
                "name",
                "",
            ),

            applicant.get(
                "phone",
                "",
            ),

            applicant.get(
                "email",
                "",
            ),

            applicant.get(
                "address",
                "",
            ),

            applicant.get(
                "additional_information",
                "",
            ),

            service.get(
                "portal_url",
                "",
            ),

            date.today().isoformat(),

            "Prepared - Not Submitted",

            now,
            now,
        ),
    )

    connection.commit()
    connection.close()

    return application_id


# ============================================================
# STATUS
# ============================================================

def fetch_local_status(
    application_id
):

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *

        FROM applications

        WHERE application_id = ?
        """,
        (application_id,),
    )

    row = cursor.fetchone()

    connection.close()

    if not row:

        return None

    return dict(row)


# ============================================================
# RESET WORKFLOW
# ============================================================

def reset_workflow():

    st.session_state[
        "service_identified"
    ] = False

    st.session_state[
        "identified_service"
    ] = None

    st.session_state[
        "workflow_active"
    ] = False

    st.session_state[
        "workflow_step"
    ] = 0

    st.session_state[
        "requirements"
    ] = None

    st.session_state[
        "official_url"
    ] = ""

    st.session_state[
        "official_form_url"
    ] = ""

    st.session_state[
        "official_state_url"
    ] = ""

    st.session_state[
        "applicant_name"
    ] = ""

    st.session_state[
        "phone"
    ] = ""

    st.session_state[
        "email"
    ] = ""

    st.session_state[
        "address"
    ] = ""

    st.session_state[
        "additional_information"
    ] = ""

    st.session_state[
        "application_id"
    ] = None

    st.session_state[
        "submission_result"
    ] = None


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🧭 NextStep AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    'Discover • Prepare • Act • Submit'
    '</div>',
    unsafe_allow_html=True,
)


# ============================================================
# HERO
# ============================================================

if not st.session_state.get(
    "workflow_active"
):

    st.markdown(
        """
        <div class="hero-card">

        <h2>Government services, one step at a time.</h2>

        <p>
        Tell NextStep AI what you need.
        It identifies the service and takes you directly
        into the action workflow.
        </p>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# MAIN TABS
# ============================================================

assistant_tab, workflow_tab, status_tab = st.tabs(
    [
        "🤖 Assistant",
        "🚀 Action Workflow",
        "📊 Status",
    ]
)


# ============================================================
# ASSISTANT
# ============================================================

with assistant_tab:

    st.markdown(
        "### What government service do you need?"
    )

    st.caption(
        "Type your request or use your microphone."
    )

    voice_audio = st.audio_input(
        "🎙️ Speak your request"
    )

    if voice_audio is not None:

        audio_bytes = (
            voice_audio.getvalue()
        )

        with st.spinner(
            "🎧 Understanding..."
        ):

            transcript = speech_to_text(
                audio_bytes,
                language,
            )

        if transcript:

            st.session_state[
                "voice_text"
            ] = transcript

            st.session_state[
                "typed_service_request"
            ] = transcript

            st.success(
                f"Voice understood: {transcript}"
            )

        else:

            st.warning(
                "Voice recognition was unavailable. "
                "Please type your request."
            )

    user_request = st.text_area(
        "Describe the service",
        value=st.session_state.get(
            "typed_service_request",
            "",
        ),
        height=120,
        placeholder=(
            "Example: I want to apply for an income certificate."
        ),
    )

    st.session_state[
        "typed_service_request"
    ] = user_request

    if st.button(
        "🚀 Start Service",
        type="primary",
        use_container_width=True,
    ):

        if not user_request.strip():

            st.warning(
                "Please describe the service first."
            )

        else:

            with st.spinner(
                "🧠 Identifying service..."
            ):

                service = identify_service(
                    user_request
                )

            if not service:

                st.error(
                    "I couldn't identify this service. "
                    "Try using the official service name."
                )

            else:

                reset_workflow()

                st.session_state[
                    "typed_service_request"
                ] = user_request

                st.session_state[
                    "service_identified"
                ] = True

                st.session_state[
                    "identified_service"
                ] = service

                st.session_state[
                    "workflow_active"
                ] = True

                st.session_state[
                    "workflow_step"
                ] = 0

                st.session_state[
                    "requirements"
                ] = get_requirements(
                    service
                )

                st.session_state[
                    "official_url"
                ] = service.get(
                    "portal_url",
                    "",
                )

                st.session_state[
                    "official_form_url"
                ] = service.get(
                    "form_url",
                    "",
                )

                st.session_state[
                    "official_state_url"
                ] = service.get(
                    "state_service_url",
                    "",
                )

                clean_request = (
                    user_request.strip()
                )

                if (
                    st.session_state.get(
                        "_request_logged"
                    )
                    != clean_request
                ):

                    add_conversation_message(
                        "user",
                        clean_request,
                    )

                    update_conversation_title(
                        clean_request
                    )

                    st.session_state[
                        "_request_logged"
                    ] = clean_request

                summary = (
                    "Started action workflow for "
                    + str(
                        service.get(
                            "service_name",
                            "government service",
                        )
                    )
                )

                st.session_state[
                    "last_ai_response"
                ] = summary

                add_conversation_message(
                    "assistant",
                    summary,
                )

                save_conversation_state()

                st.rerun()

    # ========================================================
    # QUICK TEST
    # ========================================================

    if not st.session_state.get(
        "workflow_active"
    ):

        st.divider()

        st.markdown(
            "### 🧪 Quick test"
        )

        st.caption(
            "Try the Telangana Income Certificate workflow."
        )

        if st.button(
            "📄 Test Income Certificate",
            use_container_width=True,
        ):

            test_request = (
                "I want to apply for an income certificate"
            )

            st.session_state[
                "typed_service_request"
            ] = test_request

            st.rerun()


# ============================================================
# ACTION WORKFLOW
# ============================================================

with workflow_tab:

    service = st.session_state.get(
        "identified_service"
    )

    if not service:

        st.info(
            "Start a government service from the Assistant tab."
        )

    else:

        service_name = service.get(
            "service_name",
            "Government Service",
        )

        current_step = int(
            st.session_state.get(
                "workflow_step",
                0,
            )
        )

        steps = [
            "Service",
            "Requirements",
            "Prepare",
            "Review",
            "Official Submission",
        ]

        st.markdown(
            f"## 🚀 {service_name}"
        )

        st.caption(
            "Action workflow"
        )

        # ----------------------------------------------------
        # PROGRESS
        # ----------------------------------------------------

        progress_value = min(
            (current_step + 1)
            / len(steps),
            1.0,
        )

        st.progress(
            progress_value
        )

        progress_cols = st.columns(
            len(steps)
        )

        for index, step_name in enumerate(
            steps
        ):

            with progress_cols[index]:

                if index < current_step:

                    st.success(
                        f"✓ {step_name}"
                    )

                elif index == current_step:

                    st.info(
                        f"● {step_name}"
                    )

                else:

                    st.caption(
                        f"○ {step_name}"
                    )

        st.divider()

        # ====================================================
        # STEP 0
        # ====================================================

        if current_step == 0:

            st.markdown(
                """
                <div class="step-active">
                <h3>1. Service identified</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns(2)

            with col1:

                st.markdown(
                    f"**Service:** {service_name}"
                )

                st.markdown(
                    f"**Category:** "
                    f"{service.get('service_category', 'Government Service')}"
                )

                st.markdown(
                    f"**Department:** "
                    f"{service.get('department', 'Government Department')}"
                )

            with col2:

                st.markdown(
                    f"**Jurisdiction:** "
                    f"{service.get('jurisdiction', 'Unknown')}"
                )

                confidence = float(
                    service.get(
                        "confidence",
                        0.8,
                    )
                )

                st.metric(
                    "Identification confidence",
                    f"{confidence * 100:.0f}%",
                )

            if service.get("note"):

                st.info(
                    service.get("note")
                )

            st.markdown(
                "### Ready for the next step?"
            )

            st.caption(
                "No compatibility check is required. "
                "NextStep AI moves directly into the service workflow."
            )

            if st.button(
                "➡️ Continue to Requirements",
                type="primary",
                use_container_width=True,
            ):

                st.session_state[
                    "workflow_step"
                ] = 1

                save_conversation_state()

                st.rerun()

        # ====================================================
        # STEP 1
        # ====================================================

        elif current_step == 1:

            st.markdown(
                """
                <div class="step-active">
                <h3>2. Requirements</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )

            requirements = (
                st.session_state.get(
                    "requirements",
                    [],
                )
            )

            if not requirements:

                requirements = (
                    get_requirements(
                        service
                    )
                )

                st.session_state[
                    "requirements"
                ] = requirements

            for requirement in requirements:

                if not isinstance(
                    requirement,
                    dict,
                ):
                    continue

                name = requirement.get(
                    "name",
                    "Requirement",
                )

                description = requirement.get(
                    "description",
                    "",
                )

                mandatory = requirement.get(
                    "mandatory",
                    False,
                )

                st.markdown(
                    f"""
                    <div class="workflow-card">

                    <strong>
                    {'🔴' if mandatory else '🟡'} {html.escape(str(name))}
                    </strong>

                    <br>

                    <span class="small-muted">
                    {html.escape(str(description))}
                    </span>

                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.info(
                "The official government portal remains the final source "
                "for the current document checklist."
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "⬅️ Back",
                    use_container_width=True,
                ):

                    st.session_state[
                        "workflow_step"
                    ] = 0

                    save_conversation_state()

                    st.rerun()

            with col2:

                if st.button(
                    "➡️ Continue to Preparation",
                    type="primary",
                    use_container_width=True,
                ):

                    st.session_state[
                        "workflow_step"
                    ] = 2

                    save_conversation_state()

                    st.rerun()

        # ====================================================
        # STEP 2
        # ====================================================

        elif current_step == 2:

            st.markdown(
                """
                <div class="step-active">
                <h3>3. Prepare Application</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.caption(
                "Prepare the basic information before opening "
                "the official government application."
            )

            with st.form(
                "preparation_form"
            ):

                applicant_name = st.text_input(
                    "Full name",
                    value=st.session_state.get(
                        "applicant_name",
                        "",
                    ),
                )

                phone = st.text_input(
                    "Phone number",
                    value=st.session_state.get(
                        "phone",
                        "",
                    ),
                )

                email = st.text_input(
                    "Email",
                    value=st.session_state.get(
                        "email",
                        "",
                    ),
                )

                address = st.text_area(
                    "Address",
                    value=st.session_state.get(
                        "address",
                        "",
                    ),
                )

                additional_information = (
                    st.text_area(
                        "Additional information",
                        value=st.session_state.get(
                            "additional_information",
                            "",
                        ),
                    )
                )

                st.caption(
                    "Do not enter passwords, OTPs, PINs, CVVs "
                    "or other authentication secrets here."
                )

                continue_button = (
                    st.form_submit_button(
                        "➡️ Continue to Review",
                        type="primary",
                        use_container_width=True,
                    )
                )

            if continue_button:

                if not applicant_name.strip():

                    st.error(
                        "Please enter the applicant's name."
                    )

                else:

                    st.session_state[
                        "applicant_name"
                    ] = applicant_name.strip()

                    st.session_state[
                        "phone"
                    ] = phone.strip()

                    st.session_state[
                        "email"
                    ] = email.strip()

                    st.session_state[
                        "address"
                    ] = address.strip()

                    st.session_state[
                        "additional_information"
                    ] = (
                        additional_information.strip()
                    )

                    st.session_state[
                        "workflow_step"
                    ] = 3

                    save_conversation_state()

                    st.rerun()

        # ====================================================
        # STEP 3
        # ====================================================

        elif current_step == 3:

            st.markdown(
                """
                <div class="step-active">
                <h3>4. Review</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(
                "### Application information"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.markdown(
                    f"**Service:** {service_name}"
                )

                st.markdown(
                    f"**Name:** "
                    f"{st.session_state.get('applicant_name', '')}"
                )

                st.markdown(
                    f"**Phone:** "
                    f"{st.session_state.get('phone', '') or 'Not provided'}"
                )

            with col2:

                st.markdown(
                    f"**Email:** "
                    f"{st.session_state.get('email', '') or 'Not provided'}"
                )

                st.markdown(
                    f"**Address:** "
                    f"{st.session_state.get('address', '') or 'Not provided'}"
                )

            if st.session_state.get(
                "additional_information"
            ):

                st.markdown(
                    "**Additional information:**"
                )

                st.info(
                    st.session_state[
                        "additional_information"
                    ]
                )

            st.divider()

            st.markdown(
                "### What happens next?"
            )

            st.markdown(
                """
                1. NextStep AI opens the official government service.
                2. You complete any government authentication.
                3. You enter/upload the required information.
                4. You complete any CAPTCHA, OTP, payment or verification.
                5. You submit the application on the official portal.
                6. You save the government application/reference number.
                """
            )

            st.warning(
                "The information above is only preparation inside "
                "NextStep AI. It does not mean that a government "
                "application has already been submitted."
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "✏️ Edit Information",
                    use_container_width=True,
                ):

                    st.session_state[
                        "workflow_step"
                    ] = 2

                    save_conversation_state()

                    st.rerun()

            with col2:

                if st.button(
                    "🌐 Continue to Official Submission",
                    type="primary",
                    use_container_width=True,
                ):

                    # Store a local preparation record.
                    application_id = (
                        save_local_application(
                            service,
                            {
                                "name": st.session_state.get(
                                    "applicant_name",
                                    "",
                                ),
                                "phone": st.session_state.get(
                                    "phone",
                                    "",
                                ),
                                "email": st.session_state.get(
                                    "email",
                                    "",
                                ),
                                "address": st.session_state.get(
                                    "address",
                                    "",
                                ),
                                "additional_information": (
                                    st.session_state.get(
                                        "additional_information",
                                        "",
                                    )
                                ),
                            },
                        )
                    )

                    st.session_state[
                        "application_id"
                    ] = application_id

                    st.session_state[
                        "workflow_step"
                    ] = 4

                    save_conversation_state()

                    st.rerun()

        # ====================================================
        # STEP 4
        # ====================================================

        elif current_step == 4:

            st.markdown(
                """
                <div class="step-active">
                <h3>5. Official Government Submission</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.success(
                "Your preparation is complete."
            )

            st.markdown(
                f"### {service_name}"
            )

            st.markdown(
                """
                The actual government application must now be
                completed on the official government website.

                NextStep AI does not create a fake government
                submission or pretend that an application was
                submitted.
                """
            )

            st.divider()

            # ------------------------------------------------
            # DIRECT ACTION BUTTON
            # ------------------------------------------------

            official_url = service.get(
                "portal_url",
                "",
            )

            form_url = service.get(
                "form_url",
                "",
            )

            state_url = service.get(
                "state_service_url",
                "",
            )

            if is_official_url(
                official_url
            ):

                st.link_button(
                    "🚀 OPEN OFFICIAL APPLICATION PORTAL",
                    official_url,
                    type="primary",
                    use_container_width=True,
                )

            if form_url and is_official_url(
                form_url
            ):

                st.link_button(
                    "📄 OPEN OFFICIAL APPLICATION FORM",
                    form_url,
                    use_container_width=True,
                )

            if state_url and is_official_url(
                state_url
            ):

                st.link_button(
                    "🏛️ OPEN TELANGANA SERVICE DIRECTORY",
                    state_url,
                    use_container_width=True,
                )

            st.divider()

            st.markdown(
                "### 🧭 Your next actions"
            )

            service_steps = service.get(
                "steps",
                [],
            )

            for index, step in enumerate(
                service_steps,
                start=1,
            ):

                st.markdown(
                    f"**{index}.** {step}"
                )

            st.divider()

            st.markdown(
                "### 📌 Your NextStep preparation ID"
            )

            preparation_id = (
                st.session_state.get(
                    "application_id"
                )
            )

            if preparation_id:

                st.code(
                    preparation_id
                )

                st.caption(
                    "This is a NextStep AI preparation ID, "
                    "not a government application number."
                )

            st.warning(
                "After submitting on the official portal, "
                "save the government-generated application/reference "
                "number. Use that number for official status tracking."
            )

            if st.button(
                "🔄 Start Another Service",
                use_container_width=True,
            ):

                reset_workflow()

                save_conversation_state()

                st.rerun()


# ============================================================
# STATUS
# ============================================================

with status_tab:

    st.markdown(
        "## 📊 Application Status"
    )

    st.caption(
        "Enter the application/reference number provided "
        "by the government service."
    )

    government_application_id = st.text_input(
        "Government application/reference number"
    )

    if st.button(
        "🔍 Check Status",
        type="primary",
        use_container_width=True,
    ):

        if not government_application_id.strip():

            st.warning(
                "Enter the government application/reference number."
            )

        else:

            st.info(
                "Live government status checking requires an official "
                "status API/integration for that service."
            )

            st.markdown(
                """
                **For the demo:**

                Use the official government portal to check the
                current status of the submitted application.
                """
            )

            service = (
                st.session_state.get(
                    "identified_service"
                )
            )

            if service:

                official_url = service.get(
                    "portal_url",
                    "",
                )

                if is_official_url(
                    official_url
                ):

                    st.link_button(
                        "🌐 Open Official Government Portal",
                        official_url,
                        use_container_width=True,
                    )


# ============================================================
# VOICE ASSISTANT
# ============================================================

if st.session_state.get(
    "last_ai_response"
):

    st.divider()

    st.markdown(
        "### 🔊 Voice Assistant"
    )

    if language in TTS_SUPPORTED:

        if st.button(
            "🔊 Speak Last Response"
        ):

            with st.spinner(
                "Preparing voice..."
            ):

                audio = text_to_speech(
                    st.session_state[
                        "last_ai_response"
                    ],
                    language,
                )

            if audio:

                st.audio(
                    audio,
                    format="audio/wav",
                )

            else:

                st.warning(
                    "Voice generation was unavailable."
                )

    else:

        st.caption(
            "Voice output is not currently available "
            "for the selected language."
        )
