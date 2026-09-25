import streamlit as st
import requests
import json
import re
import sqlite3
import base64
import uuid

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


BLOCKING_BARRIERS = {
    "captcha",
    "recaptcha",
    "hcaptcha",
    "cloudflare_turnstile",
    "biometric",
    "physical_verification",
    "mandatory_physical_presence",
    "human_verification",
    "manual_verification",
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

    "application_decision": None,
    "application_mode": False,

    "requirements": None,
    "timeline": None,

    "official_url": "",
    "official_page_text": "",

    "barrier_check": None,
    "submission_capability": None,

    "application_id": None,
    "submission_result": None,

    "pending_application_payload": None,
    "ready_to_submit": False,

    "last_ai_response": "",

    "language": "English",

    "_request_logged": "",
}


for key, value in DEFAULT_STATE.items():

    if key not in st.session_state:

        st.session_state[key] = value


# ============================================================
# SECRETS HELPERS
# ============================================================

def get_secret(name, default=""):

    try:

        value = st.secrets.get(
            name,
            default,
        )

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

GOVERNMENT_SUBMISSION_URL = get_secret(
    "GOVERNMENT_SUBMISSION_URL"
)

GOVERNMENT_STATUS_URL = get_secret(
    "GOVERNMENT_STATUS_URL"
)

HOLIDAYS_RAW = get_secret(
    "HOLIDAYS",
    "[]",
)


# ============================================================
# OPTIONAL SERVICE INTEGRATION REGISTRY
# ============================================================

def load_integration_registry():

    raw = get_secret(
        "GOVERNMENT_INTEGRATIONS",
        "",
    )

    if not raw:
        return []

    try:

        parsed = json.loads(raw)

        if isinstance(parsed, list):
            return parsed

        return []

    except Exception:

        return []


GOVERNMENT_INTEGRATIONS = (
    load_integration_registry()
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 0;
    }

    .subtitle {
        font-size: 17px;
        opacity: 0.75;
        margin-top: 4px;
        margin-bottom: 24px;
    }

    .service-box {
        padding: 20px;
        border-radius: 16px;
        border: 1px solid rgba(128,128,128,0.25);
        margin-bottom: 16px;
    }

    .success-box {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(50,180,100,0.35);
        background: rgba(50,180,100,0.08);
    }

    .warning-box {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(220,170,50,0.35);
        background: rgba(220,170,50,0.08);
    }

    .danger-box {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(220,70,70,0.35);
        background: rgba(220,70,70,0.08);
    }

    .info-box {
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(80,130,220,0.35);
        background: rgba(80,130,220,0.08);
    }

    .small-muted {
        font-size: 13px;
        opacity: 0.7;
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

    # --------------------------------------------------------
    # APPLICATIONS
    # --------------------------------------------------------

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

            processing_days INTEGER,
            processing_type TEXT,
            expected_completion_date TEXT,

            timeline_source TEXT,
            timeline_verified INTEGER,

            ai_submission_supported INTEGER,
            barrier_detected INTEGER,
            barrier_details TEXT,

            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    # --------------------------------------------------------
    # CONVERSATIONS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CONVERSATION MESSAGES
    # --------------------------------------------------------

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

    "application_decision",
    "application_mode",

    "requirements",
    "timeline",

    "official_url",
    "official_page_text",

    "barrier_check",
    "submission_capability",

    "application_id",
    "submission_result",

    "pending_application_payload",
    "ready_to_submit",

    "last_ai_response",

    "language",

    "_request_logged",
]


def get_conversation_state():

    state = {}

    for key in CONVERSATION_STATE_KEYS:

        value = st.session_state.get(
            key
        )

        try:

            json.dumps(
                value,
                ensure_ascii=False,
            )

            state[key] = value

        except Exception:

            state[key] = None

    return state


def restore_conversation_state(
    state,
):

    if not isinstance(
        state,
        dict,
    ):
        return

    for key in CONVERSATION_STATE_KEYS:

        if key in state:

            st.session_state[key] = state[key]


def reset_conversation_state():

    for key, value in DEFAULT_STATE.items():

        st.session_state[key] = value


def create_conversation(
    title="New Conversation",
):

    conversation_id = str(
        uuid.uuid4()
    )

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
            json.dumps(
                {},
                ensure_ascii=False,
            ),
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

    now = datetime.now().isoformat()

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
            now,
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


def update_conversation_title(
    title,
):

    conversation_id = st.session_state.get(
        "conversation_id"
    )

    if not conversation_id:
        return

    title = str(title).strip()

    if not title:
        return

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


def add_conversation_message(
    role,
    content,
):

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


def load_conversation(
    conversation_id,
):

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *

        FROM conversations

        WHERE conversation_id = ?
        """,
        (
            conversation_id,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    if not row:
        return False

    try:

        state = json.loads(
            row["state_json"]
            or "{}"
        )

    except Exception:

        state = {}

    reset_conversation_state()

    st.session_state[
        "conversation_id"
    ] = conversation_id

    restore_conversation_state(
        state
    )

    return True


def delete_conversation(
    conversation_id,
):

    if not conversation_id:
        return

    connection = get_db()

    cursor = connection.cursor()

    # Delete all messages belonging to this conversation
    cursor.execute(
        """
        DELETE FROM conversation_messages

        WHERE conversation_id = ?
        """,
        (
            conversation_id,
        ),
    )

    # Delete the conversation itself
    cursor.execute(
        """
        DELETE FROM conversations

        WHERE conversation_id = ?
        """,
        (
            conversation_id,
        ),
    )

    connection.commit()
    connection.close()


def ensure_current_conversation():

    if st.session_state.get(
        "conversation_id"
    ):
        return

    conversation_id = create_conversation(
        "New Conversation"
    )

    st.session_state[
        "conversation_id"
    ] = conversation_id

    save_conversation_state()


ensure_current_conversation()


# ============================================================
# CONVERSATION SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🧭 NextStep AI"
    )

    st.caption(
        "AI-powered public-service assistant"
    )

    # ========================================================
    # NEW CONVERSATION
    # ========================================================

    if st.button(
        "➕ New Conversation",
        use_container_width=True,
        type="primary",
    ):

        # Save current conversation before creating another
        save_conversation_state()

        new_id = create_conversation(
            "New Conversation"
        )

        reset_conversation_state()

        st.session_state[
            "conversation_id"
        ] = new_id

        save_conversation_state()

        st.rerun()

    st.divider()

    # ========================================================
    # CONVERSATION HISTORY
    # ========================================================

    st.markdown(
        "### 🕘 Previous Conversations"
    )

    conversations = get_conversations()

    current_id = st.session_state.get(
        "conversation_id"
    )

    if not conversations:

        st.caption(
            "No conversations yet."
        )

    else:

        for conversation in conversations:

            conversation_id = conversation[
                "conversation_id"
            ]

            title = (
                conversation["title"]
                or "New Conversation"
            )

            # Clean empty/untitled conversations
            if not title.strip():

                title = "New Conversation"

            # Short display title
            display_title = title

            if len(display_title) > 32:

                display_title = (
                    display_title[:29]
                    + "..."
                )

            is_current = (
                conversation_id
                == current_id
            )

            # ------------------------------------------------
            # EACH CONVERSATION GETS TWO BUTTONS:
            # OPEN + DELETE
            # ------------------------------------------------

            open_col, delete_col = st.columns(
                [5, 1],
                gap="small",
            )

            with open_col:

                if is_current:

                    button_label = (
                        f"🟢 {display_title}"
                    )

                else:

                    button_label = (
                        f"💬 {display_title}"
                    )

                if st.button(
                    button_label,
                    key=(
                        "open_conversation_"
                        + conversation_id
                    ),
                    use_container_width=True,
                ):

                    if conversation_id != current_id:

                        save_conversation_state()

                        loaded = load_conversation(
                            conversation_id
                        )

                        if loaded:

                            st.rerun()

            with delete_col:

                if st.button(
                    "🗑️",
                    key=(
                        "delete_conversation_"
                        + conversation_id
                    ),
                    help=(
                        "Delete this conversation"
                    ),
                    use_container_width=True,
                ):

                    deleting_current = (
                        conversation_id
                        == current_id
                    )

                    delete_conversation(
                        conversation_id
                    )

                    # If current conversation was deleted,
                    # immediately create a fresh conversation.
                    if deleting_current:

                        reset_conversation_state()

                        new_id = create_conversation(
                            "New Conversation"
                        )

                        st.session_state[
                            "conversation_id"
                        ] = new_id

                        save_conversation_state()

                    st.rerun()

    st.divider()

    # ========================================================
    # CURRENT CONVERSATION
    # ========================================================

    current_conversation_id = (
        st.session_state.get(
            "conversation_id"
        )
    )

    current_title = "New Conversation"

    if current_conversation_id:

        connection = get_db()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT title

            FROM conversations

            WHERE conversation_id = ?
            """,
            (
                current_conversation_id,
            ),
        )

        row = cursor.fetchone()

        connection.close()

        if row and row["title"]:

            current_title = row["title"]

    st.markdown(
        "### 💬 Current Conversation"
    )

    st.caption(
        current_title
    )

    if st.button(
        "🗑️ Delete Current Conversation",
        use_container_width=True,
    ):

        current_conversation = (
            st.session_state.get(
                "conversation_id"
            )
        )

        if current_conversation:

            delete_conversation(
                current_conversation
            )

        reset_conversation_state()

        new_id = create_conversation(
            "New Conversation"
        )

        st.session_state[
            "conversation_id"
        ] = new_id

        save_conversation_state()

        st.rerun()

    st.divider()

    # ========================================================
    # LANGUAGE
    # ========================================================

    current_language = (
        st.session_state.get(
            "language",
            "English",
        )
    )

    language_index = 0

    if current_language in LANGUAGE_CODES:

        language_index = list(
            LANGUAGE_CODES.keys()
        ).index(
            current_language
        )

    language = st.selectbox(
        "🌐 Language",
        list(LANGUAGE_CODES.keys()),
        index=language_index,
    )

    st.session_state[
        "language"
    ] = language

    # Save language change
    save_conversation_state()

    st.divider()

    # ========================================================
    # HOW IT WORKS
    # ========================================================

    st.markdown(
        "### How it works"
    )

    st.markdown(
        """
        **1. Discover**  
        Describe the government service.

        **2. Verify**  
        NextStep AI checks the official process.

        **3. Safety check**  
        CAPTCHA and other human-only barriers are detected.

        **4. Prepare**  
        Required information is collected only when needed.

        **5. Submit**  
        Submission happens only through an authorized integration.

        **6. Track**  
        Application status and processing timeline are shown.
        """
    )

    st.divider()

    st.caption(
        "NextStep AI never bypasses CAPTCHA, OTP, biometric "
        "verification, or other human-verification controls."
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🧭 NextStep AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">Discover • Prepare • Submit • Track</div>',
    unsafe_allow_html=True,
)


# ============================================================
# DATE / WORKING DAY HELPERS
# ============================================================

def load_holidays():

    try:

        holidays = json.loads(
            HOLIDAYS_RAW
        )

        if not isinstance(
            holidays,
            list,
        ):
            return set()

        return {
            str(item).strip()
            for item in holidays
            if str(item).strip()
        }

    except Exception:

        return set()


HOLIDAYS = load_holidays()


def is_working_day(day):

    if day.weekday() >= 5:
        return False

    if day.isoformat() in HOLIDAYS:
        return False

    return True


def add_working_days(
    start_date,
    number_of_days,
):

    current = start_date
    added = 0

    while added < number_of_days:

        current += timedelta(days=1)

        if is_working_day(current):

            added += 1

    return current


def add_processing_days(
    submission_date,
    processing_days,
    processing_type,
):

    if not processing_days:
        return None

    if processing_type == "working_days":

        return add_working_days(
            submission_date,
            processing_days,
        )

    return submission_date + timedelta(
        days=processing_days
    )


def calculate_remaining_days(
    expected_date,
    processing_type,
):

    if not expected_date:
        return None

    today = date.today()

    if expected_date <= today:
        return 0

    if processing_type == "working_days":

        count = 0
        current = today

        while current < expected_date:

            current += timedelta(days=1)

            if is_working_day(current):

                count += 1

        return count

    return (
        expected_date - today
    ).days


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

        message = choices[0].get(
            "message",
            {},
        )

        content = message.get(
            "content",
            "",
        )

        if isinstance(
            content,
            list,
        ):

            text_parts = []

            for item in content:

                if isinstance(
                    item,
                    dict,
                ):

                    text_parts.append(
                        str(
                            item.get(
                                "text",
                                "",
                            )
                        )
                    )

            content = "".join(
                text_parts
            )

        return str(
            content
        ).strip()

    except Exception:

        return None


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):

    if not text:
        return None

    text = text.strip()

    try:

        return json.loads(text)

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

        parsed = urlparse(url)

        if parsed.scheme not in {
            "http",
            "https",
        }:

            return False

        hostname = (
            parsed.hostname or ""
        ).lower()

        if not hostname:
            return False

        allowed = (
            hostname.endswith(".gov.in")
            or hostname.endswith(".nic.in")
            or hostname == "gov.in"
        )

        return allowed

    except Exception:

        return False


def normalize_url(url):

    if not url:
        return ""

    url = str(
        url
    ).strip()

    if not url.startswith(
        (
            "http://",
            "https://",
        )
    ):

        url = (
            "https://"
            + url
        )

    return url


# ============================================================
# OFFICIAL PAGE READER
# ============================================================

def read_official_page(url):

    url = normalize_url(
        url
    )

    if not is_official_url(
        url
    ):

        return {
            "success": False,
            "text": "",
            "error": (
                "URL is not a verified "
                "government-domain URL."
            ),
        }

    try:

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; NextStepAI/1.0)"
            )
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        response.raise_for_status()

        final_url = response.url

        if not is_official_url(
            final_url
        ):

            return {
                "success": False,
                "text": "",
                "error": (
                    "The page redirected outside "
                    "a verified government domain."
                ),
            }

        html = response.text

        html = re.sub(
            r"<script.*?</script>",
            " ",
            html,
            flags=re.I | re.S,
        )

        html = re.sub(
            r"<style.*?</style>",
            " ",
            html,
            flags=re.I | re.S,
        )

        html = re.sub(
            r"<noscript.*?</noscript>",
            " ",
            html,
            flags=re.I | re.S,
        )

        text = re.sub(
            r"<[^>]+>",
            " ",
            html,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        return {
            "success": True,
            "text": text[:30000],
            "url": final_url,
            "error": "",
        }

    except Exception as error:

        return {
            "success": False,
            "text": "",
            "error": str(error),
        }


# ============================================================
# AI SERVICE IDENTIFICATION
# ============================================================

def identify_service(
    user_request
):

    system_prompt = """
You are the service-identification engine for NextStep AI.

The user may describe a government/public service in natural language.

Identify the most likely service.

Return ONLY valid JSON.

Required schema:

{
  "service_name": "",
  "service_category": "",
  "jurisdiction": "",
  "department": "",
  "intent": "",
  "confidence": 0,
  "online_application_available": false,
  "official_portal_url": "",
  "explanation": ""
}

Rules:

1. Do not invent a government procedure.
2. Do not invent an exact official URL.
3. If you do not know an official URL with reasonable confidence,
   return an empty official_portal_url.
4. confidence must be between 0 and 1.
5. online_application_available should only be true when an
   online application process is reasonably known.
6. Identify the jurisdiction if the user explicitly provides it.
7. If jurisdiction is unknown, say "Unknown".
8. Be conservative.
"""

    result = openrouter_chat(
        system_prompt,
        user_request,
        temperature=0.0,
    )

    data = extract_json(
        result
    )

    if not data:
        return None

    try:

        data["confidence"] = float(
            data.get(
                "confidence",
                0,
            )
        )

    except Exception:

        data["confidence"] = 0

    data[
        "official_portal_url"
    ] = normalize_url(
        data.get(
            "official_portal_url",
            "",
        )
    )

    return data


# ============================================================
# REQUIREMENTS
# ============================================================

def generate_requirements(
    service
):

    system_prompt = """
You are the requirements engine for NextStep AI.

Generate a conservative list of information/documents that
a citizen may need for the identified government service.

Return ONLY valid JSON.

Schema:

{
  "requirements": [
    {
      "name": "",
      "description": "",
      "mandatory": true
    }
  ],
  "information_needed": [],
  "warnings": [],
  "verification_note": ""
}

Rules:

- Never invent a government requirement as certain.
- Clearly distinguish likely requirements from verified requirements.
- Do not request unnecessary sensitive information.
- Do not ask for passwords, OTPs, PINs, CVVs or authentication secrets.
- Mention that the official portal should be checked.
"""

    prompt = json.dumps(
        service,
        ensure_ascii=False,
    )

    result = openrouter_chat(
        system_prompt,
        prompt,
        temperature=0.1,
    )

    data = extract_json(
        result
    )

    if not data:

        return {
            "requirements": [],
            "information_needed": [],
            "warnings": [
                "Requirements could not be generated."
            ],
            "verification_note": (
                "Please verify requirements on the "
                "official government portal."
            ),
        }

    return data


# ============================================================
# BARRIER DETECTION
# ============================================================

def detect_ai_barriers(
    service,
    official_page_text,
):

    if not official_page_text:

        return {
            "page_checked": False,
            "ai_submission_supported": False,
            "barriers": [],
            "reason": (
                "The official application page could "
                "not be inspected. Automatic submission "
                "is disabled until the process can be verified."
            ),
        }

    system_prompt = """
You are the automation-safety checker for NextStep AI.

Analyze the official government application-page text.

Your task is to determine whether an AI agent can safely and
legitimately automate the application.

Return ONLY valid JSON:

{
  "page_checked": true,
  "online_application_available": false,
  "ai_submission_supported": false,
  "barriers": [
    {
      "type": "",
      "present": false,
      "blocking": false,
      "evidence": ""
    }
  ],
  "human_steps_required": [],
  "reason": ""
}

Recognize barriers including:

- CAPTCHA
- reCAPTCHA
- hCaptcha
- Cloudflare Turnstile
- human verification
- OTP that must be entered by the applicant
- biometric authentication
- Aadhaar biometric authentication
- mandatory physical verification
- mandatory physical presence
- mandatory in-person appointment
- payment that requires human interaction
- any other explicit human-only verification

Important:

1. Never recommend bypassing CAPTCHA.
2. Never recommend bypassing OTP or identity verification.
3. Never claim an application can be automated if a blocking
   human verification step is explicitly present.
4. If the page does not contain enough evidence, be conservative.
5. Do not treat ordinary login as a CAPTCHA.
6. Do not treat a normal document upload as a barrier.
7. Do not invent barriers that are not present.
8. If CAPTCHA is detected, ai_submission_supported MUST be false.
9. If mandatory biometric verification is detected,
   ai_submission_supported MUST be false.
10. If mandatory physical presence is detected,
    ai_submission_supported MUST be false.
"""

    prompt = f"""
SERVICE:

{json.dumps(
    service,
    indent=2,
    ensure_ascii=False,
)}

OFFICIAL PAGE TEXT:

{official_page_text[:25000]}
"""

    result = openrouter_chat(
        system_prompt,
        prompt,
        temperature=0.0,
    )

    data = extract_json(
        result
    )

    if not data:

        return {
            "page_checked": True,
            "online_application_available": False,
            "ai_submission_supported": False,
            "barriers": [],
            "human_steps_required": [],
            "reason": (
                "The application process could not be "
                "reliably analyzed. Automatic submission "
                "has therefore been disabled."
            ),
        }

    barriers = data.get(
        "barriers",
        [],
    )

    for barrier in barriers:

        if not isinstance(
            barrier,
            dict,
        ):
            continue

        barrier_type = str(
            barrier.get(
                "type",
                "",
            )
        ).lower().replace(
            "-",
            "_",
        ).replace(
            " ",
            "_",
        )

        if (
            barrier_type
            in BLOCKING_BARRIERS
            and barrier.get(
                "present"
            )
            is True
        ):

            data[
                "ai_submission_supported"
            ] = False

    return data


# ============================================================
# AUTHORIZED INTEGRATION CHECK
# ============================================================

def find_authorized_integration(
    service_name
):

    service_name_lower = (
        str(
            service_name or ""
        )
        .strip()
        .lower()
    )

    if not service_name_lower:
        return None

    for integration in (
        GOVERNMENT_INTEGRATIONS
    ):

        if not isinstance(
            integration,
            dict,
        ):
            continue

        registered_name = str(
            integration.get(
                "service_name",
                "",
            )
        ).strip().lower()

        if (
            registered_name
            == service_name_lower
        ):

            return integration

    return None


def check_submission_capability(
    service,
    barrier_check,
):

    service_name = service.get(
        "service_name",
        "",
    )

    integration = (
        find_authorized_integration(
            service_name
        )
    )

    if not barrier_check:

        return {
            "supported": False,
            "reason": (
                "The application process has not "
                "been verified."
            ),
            "integration": None,
        }

    if not barrier_check.get(
        "page_checked",
        False,
    ):

        return {
            "supported": False,
            "reason": (
                "The official application process "
                "could not be verified."
            ),
            "integration": None,
        }

    if not barrier_check.get(
        "ai_submission_supported",
        False,
    ):

        return {
            "supported": False,
            "reason": barrier_check.get(
                "reason",
                "A human verification step is required.",
            ),
            "integration": integration,
        }

    if not integration:

        return {
            "supported": False,
            "reason": (
                "The service may have an online application, "
                "but NextStep AI does not have a configured "
                "authorized government integration for "
                "automatic submission."
            ),
            "integration": None,
        }

    endpoint = str(
        integration.get(
            "endpoint",
            "",
        )
    ).strip()

    if not endpoint:

        return {
            "supported": False,
            "reason": (
                "No authorized submission endpoint "
                "is configured for this service."
            ),
            "integration": None,
        }

    return {
        "supported": True,
        "reason": (
            "The application process passed the barrier "
            "check and an authorized integration is configured."
        ),
        "integration": integration,
    }


# ============================================================
# OFFICIAL TIMELINE VERIFICATION
# ============================================================

def verify_timeline(
    service,
    official_page_text,
):

    if not official_page_text:

        return {
            "verified": False,
            "processing_days": None,
            "processing_type": None,
            "evidence": "",
            "confidence": 0,
        }

    system_prompt = """
You are the official timeline extraction engine for NextStep AI.

Extract a processing timeline ONLY when the official page text
explicitly states it.

Return ONLY JSON:

{
  "verified": false,
  "processing_days": null,
  "processing_type": null,
  "evidence": "",
  "confidence": 0
}

processing_type must be exactly:

"calendar_days"

or

"working_days"

or null.

Rules:

- Never guess.
- Never infer a processing time from general statements.
- If the page says "within 7 working days", return 7 and working_days.
- If it says "within 30 days", return 30 and calendar_days only if
  the context clearly means calendar days.
- If unclear, return verified false.
- evidence must briefly quote the relevant wording.
"""

    prompt = f"""
SERVICE:

{json.dumps(
    service,
    ensure_ascii=False,
)}

OFFICIAL PAGE:

{official_page_text[:25000]}
"""

    result = openrouter_chat(
        system_prompt,
        prompt,
        temperature=0.0,
    )

    data = extract_json(
        result
    )

    if not data:

        return {
            "verified": False,
            "processing_days": None,
            "processing_type": None,
            "evidence": "",
            "confidence": 0,
        }

    return data


# ============================================================
# SARVAM SPEECH TO TEXT
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
        "api-subscription-key": (
            SARVAM_API_KEY
        ),
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
# SARVAM TEXT TO SPEECH
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
        "api-subscription-key": (
            SARVAM_API_KEY
        ),
        "Content-Type": (
            "application/json"
        ),
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

        audio_b64 = (
            data.get(
                "audios",
                [None],
            )[0]
            if isinstance(
                data.get("audios"),
                list,
            )
            else data.get(
                "audio"
            )
        )

        if not audio_b64:
            return None

        return base64.b64decode(
            audio_b64
        )

    except Exception:

        return None


# ============================================================
# SUBMISSION
# ============================================================

def submit_application(
    payload,
    integration,
):

    if not integration:

        return {
            "success": False,
            "real_submission": False,
            "application_id": None,
            "message": (
                "No authorized government integration "
                "is configured for this service."
            ),
        }

    endpoint = str(
        integration.get(
            "endpoint",
            "",
        )
    ).strip()

    if not endpoint:

        return {
            "success": False,
            "real_submission": False,
            "application_id": None,
            "message": (
                "The authorized integration does not "
                "have a submission endpoint."
            ),
        }

    method = str(
        integration.get(
            "method",
            "POST",
        )
    ).upper()

    headers = {
        "Content-Type": (
            "application/json"
        )
    }

    extra_headers = (
        integration.get(
            "headers",
            {},
        )
    )

    if isinstance(
        extra_headers,
        dict,
    ):

        headers.update(
            extra_headers
        )

    try:

        if method == "POST":

            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

        elif method == "PUT":

            response = requests.put(
                endpoint,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

        else:

            return {
                "success": False,
                "real_submission": False,
                "application_id": None,
                "message": (
                    "Unsupported integration method."
                ),
            }

        response.raise_for_status()

        data = response.json()

        application_id = (
            data.get("application_id")
            or data.get("applicationId")
            or data.get("reference_number")
            or data.get("referenceNumber")
            or data.get("application_number")
            or data.get("applicationNumber")
            or data.get("id")
        )

        if not application_id:

            return {
                "success": False,
                "real_submission": False,
                "application_id": None,
                "message": (
                    "The government integration responded, "
                    "but did not provide a recognizable "
                    "application/reference number."
                ),
                "raw_response": data,
            }

        return {
            "success": True,
            "real_submission": True,
            "application_id": str(
                application_id
            ),
            "message": (
                "Application submitted through the "
                "configured authorized integration."
            ),
            "raw_response": data,
        }

    except Exception as error:

        return {
            "success": False,
            "real_submission": False,
            "application_id": None,
            "message": (
                "Government submission failed: "
                + str(error)
            ),
        }


# ============================================================
# LOCAL APPLICATION RECORD
# ============================================================

def save_application(
    record
):

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

            processing_days,
            processing_type,
            expected_completion_date,

            timeline_source,
            timeline_verified,

            ai_submission_supported,
            barrier_detected,
            barrier_details,

            created_at,
            updated_at
        )

        VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?,
            ?,
            ?,
            ?, ?, ?,
            ?, ?,
            ?, ?,
            ?,
            ?, ?
        )
        """,
        (
            record.get(
                "application_id"
            ),

            record.get(
                "service_name"
            ),

            record.get(
                "category"
            ),

            record.get(
                "jurisdiction"
            ),

            record.get(
                "department"
            ),

            record.get(
                "applicant_name"
            ),

            record.get(
                "phone"
            ),

            record.get(
                "email"
            ),

            record.get(
                "address"
            ),

            record.get(
                "additional_information"
            ),

            record.get(
                "official_url"
            ),

            record.get(
                "submission_date"
            ),

            record.get(
                "status"
            ),

            record.get(
                "processing_days"
            ),

            record.get(
                "processing_type"
            ),

            record.get(
                "expected_completion_date"
            ),

            record.get(
                "timeline_source"
            ),

            1 if record.get(
                "timeline_verified"
            ) else 0,

            1 if record.get(
                "ai_submission_supported"
            ) else 0,

            1 if record.get(
                "barrier_detected"
            ) else 0,

            json.dumps(
                record.get(
                    "barrier_details",
                    {},
                ),
                ensure_ascii=False,
            ),

            record.get(
                "created_at"
            ),

            record.get(
                "updated_at"
            ),
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# STATUS
# ============================================================

def fetch_status(
    application_id
):

    if GOVERNMENT_STATUS_URL:

        try:

            response = requests.post(
                GOVERNMENT_STATUS_URL,
                json={
                    "application_id": (
                        application_id
                    )
                },
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            data = response.json()

            return {
                "success": True,
                "status": data.get(
                    "status",
                    "Unknown",
                ),
                "message": data.get(
                    "message",
                    "",
                ),
                "raw": data,
            }

        except Exception as error:

            return {
                "success": False,
                "status": "Unknown",
                "message": str(error),
                "raw": {},
            }

    connection = get_db()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *

        FROM applications

        WHERE application_id = ?
        """,
        (
            application_id,
        ),
    )

    row = cursor.fetchone()

    connection.close()

    if not row:

        return {
            "success": False,
            "status": "Not found",
            "message": (
                "No application was found."
            ),
            "raw": {},
        }

    return {
        "success": True,
        "status": row["status"],
        "message": (
            "This is the status stored by NextStep AI. "
            "A live government status requires a configured "
            "government status API."
        ),
        "raw": dict(row),
    }


# ============================================================
# MAIN TABS
# ============================================================

assistant_tab, application_tab, status_tab = st.tabs(
    [
        "🤖 Assistant",
        "📝 Application Mode",
        "📊 Application Status",
    ]
)


# ============================================================
# ASSISTANT TAB
# ============================================================

with assistant_tab:

    st.markdown(
        "### Tell me what government service you need"
    )

    st.caption(
        "You can type your request or use your microphone."
    )

    # ========================================================
    # VOICE INPUT
    # ========================================================

    voice_audio = st.audio_input(
        "🎙️ Speak your request"
    )

    if voice_audio is not None:

        audio_bytes = (
            voice_audio.getvalue()
        )

        with st.spinner(
            "🎧 Understanding your voice..."
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
                "I couldn't understand the voice recording. "
                "Please try again or type your request."
            )

    # ========================================================
    # TEXT INPUT
    # ========================================================

    user_request = st.text_area(
        "Describe the service",
        value=st.session_state.get(
            "typed_service_request",
            "",
        ),
        height=120,
        placeholder=(
            "Example: I want to apply for a birth certificate."
        ),
    )

    st.session_state[
        "typed_service_request"
    ] = user_request

    identify_clicked = st.button(
        "🔎 Identify Service",
        type="primary",
        use_container_width=True,
    )

    if identify_clicked:

        if not user_request.strip():

            st.warning(
                "Please describe the government service first."
            )

        elif not OPENROUTER_API_KEY:

            st.error(
                "OPENROUTER_API_KEY is missing from Streamlit secrets."
            )

        else:

            with st.spinner(
                "🧠 Identifying the service..."
            ):

                result = identify_service(
                    user_request
                )

            if not result:

                st.error(
                    "I couldn't identify the service reliably. "
                    "Please describe it in a little more detail."
                )

            else:

                st.session_state[
                    "service_identified"
                ] = True

                st.session_state[
                    "identified_service"
                ] = result

                st.session_state[
                    "application_decision"
                ] = None

                st.session_state[
                    "application_mode"
                ] = False

                st.session_state[
                    "requirements"
                ] = None

                st.session_state[
                    "timeline"
                ] = None

                st.session_state[
                    "official_url"
                ] = result.get(
                    "official_portal_url",
                    "",
                )

                st.session_state[
                    "official_page_text"
                ] = ""

                st.session_state[
                    "barrier_check"
                ] = None

                st.session_state[
                    "submission_capability"
                ] = None

                st.session_state[
                    "application_id"
                ] = None

                st.session_state[
                    "submission_result"
                ] = None

                st.session_state[
                    "pending_application_payload"
                ] = None

                st.session_state[
                    "ready_to_submit"
                ] = False

                # ------------------------------------------------
                # SAVE USER REQUEST
                # ------------------------------------------------

                clean_request = (
                    user_request.strip()
                )

                if clean_request:

                    previous_request = (
                        st.session_state.get(
                            "_request_logged",
                            "",
                        )
                    )

                    if (
                        previous_request
                        != clean_request
                    ):

                        add_conversation_message(
                            "user",
                            clean_request,
                        )

                        # ------------------------------------------------
                        # AUTOMATIC CONVERSATION NAME
                        # ------------------------------------------------
                        #
                        # The first request becomes the conversation
                        # title. This means every conversation gets
                        # its own meaningful name.
                        #

                        title = clean_request

                        # Remove excessive whitespace
                        title = re.sub(
                            r"\s+",
                            " ",
                            title,
                        ).strip()

                        # Make it title-like when possible
                        if len(title) > 60:

                            title = (
                                title[:57]
                                + "..."
                            )

                        update_conversation_title(
                            title
                        )

                        st.session_state[
                            "_request_logged"
                        ] = clean_request

                assistant_summary = (
                    "Service identified: "
                    + str(
                        result.get(
                            "service_name",
                            "Unknown",
                        )
                    )
                )

                add_conversation_message(
                    "assistant",
                    assistant_summary,
                )

                st.session_state[
                    "last_ai_response"
                ] = assistant_summary

                save_conversation_state()

                st.rerun()

    # ========================================================
    # IDENTIFIED SERVICE
    # ========================================================

    if st.session_state.get(
        "service_identified",
        False,
    ):

        service = st.session_state.get(
            "identified_service"
        )

        if service:

            st.divider()

            st.markdown(
                "## 🔍 Service identified"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.markdown(
                    f"**Service:** "
                    f"{service.get('service_name', 'Unknown')}"
                )

                st.markdown(
                    f"**Category:** "
                    f"{service.get('service_category', 'Unknown')}"
                )

                st.markdown(
                    f"**Jurisdiction:** "
                    f"{service.get('jurisdiction', 'Unknown')}"
                )

                st.markdown(
                    f"**Department:** "
                    f"{service.get('department', 'Unknown')}"
                )

            with col2:

                confidence = float(
                    service.get(
                        "confidence",
                        0,
                    )
                )

                st.metric(
                    "AI confidence",
                    f"{confidence * 100:.0f}%",
                )

                st.markdown(
                    f"**Intent:** "
                    f"{service.get('intent', 'Unknown')}"
                )

            st.info(
                service.get(
                    "explanation",
                    "Service identified.",
                )
            )

            # ====================================================
            # OFFICIAL URL
            # ====================================================

            official_url = st.session_state.get(
                "official_url",
                "",
            )

            if (
                official_url
                and is_official_url(
                    official_url
                )
            ):

                st.markdown(
                    f"**Official portal:** "
                    f"{official_url}"
                )

                st.link_button(
                    "🌐 Open Official Portal",
                    official_url,
                )

            else:

                st.warning(
                    "A verified official government portal URL "
                    "could not be established automatically."
                )

            # ====================================================
            # VERIFY OFFICIAL PAGE
            # ====================================================

            if (
                official_url
                and is_official_url(
                    official_url
                )
            ):

                if st.button(
                    "🛡️ Check AI Submission Compatibility",
                    use_container_width=True,
                ):

                    with st.spinner(
                        "🔍 Checking the official application process..."
                    ):

                        page_result = (
                            read_official_page(
                                official_url
                            )
                        )

                        if page_result.get(
                            "success"
                        ):

                            page_text = (
                                page_result.get(
                                    "text",
                                    "",
                                )
                            )

                            barrier_result = (
                                detect_ai_barriers(
                                    service,
                                    page_text,
                                )
                            )

                            st.session_state[
                                "official_page_text"
                            ] = page_text

                            st.session_state[
                                "barrier_check"
                            ] = barrier_result

                            capability = (
                                check_submission_capability(
                                    service,
                                    barrier_result,
                                )
                            )

                            st.session_state[
                                "submission_capability"
                            ] = capability

                            timeline = (
                                verify_timeline(
                                    service,
                                    page_text,
                                )
                            )

                            st.session_state[
                                "timeline"
                            ] = timeline

                            save_conversation_state()

                            st.success(
                                "Official application process checked."
                            )

                            st.rerun()

                        else:

                            st.error(
                                "The official page could not be inspected."
                            )

                            st.caption(
                                page_result.get(
                                    "error",
                                    "Unknown error",
                                )
                            )

            # ====================================================
            # BARRIER RESULT
            # ====================================================

            barrier_check = (
                st.session_state.get(
                    "barrier_check"
                )
            )

            capability = (
                st.session_state.get(
                    "submission_capability"
                )
            )

            if barrier_check:

                st.divider()

                st.markdown(
                    "### 🛡️ AI Submission Safety Check"
                )

                barriers = (
                    barrier_check.get(
                        "barriers",
                        [],
                    )
                )

                blocking_barriers = []

                for barrier in barriers:

                    if not isinstance(
                        barrier,
                        dict,
                    ):
                        continue

                    if (
                        barrier.get(
                            "present"
                        )
                        and barrier.get(
                            "blocking"
                        )
                    ):

                        blocking_barriers.append(
                            barrier
                        )

                if blocking_barriers:

                    st.error(
                        "🚫 Automatic AI submission is not supported for this service."
                    )

                    for barrier in blocking_barriers:

                        barrier_type = (
                            barrier.get(
                                "type",
                                "human verification",
                            )
                        )

                        evidence = (
                            barrier.get(
                                "evidence",
                                "",
                            )
                        )

                        st.markdown(
                            f"**Detected barrier:** "
                            f"{barrier_type}"
                        )

                        if evidence:

                            st.caption(
                                evidence
                            )

                    st.info(
                        "NextStep AI will not bypass this "
                        "verification. Please use the official "
                        "government portal manually."
                    )

                elif (
                    capability
                    and capability.get(
                        "supported"
                    )
                ):

                    st.success(
                        "🟢 This service is eligible for AI-assisted submission through a configured authorized integration."
                    )

                else:

                    st.warning(
                        "🟡 Automatic submission is not currently available."
                    )

                    st.caption(
                        capability.get(
                            "reason",
                            "An authorized integration is not configured.",
                        )
                        if capability
                        else
                        "The submission process could not be verified."
                    )

                human_steps = (
                    barrier_check.get(
                        "human_steps_required",
                        [],
                    )
                )

                if human_steps:

                    st.markdown(
                        "**Human action required:**"
                    )

                    for step in human_steps:

                        st.markdown(
                            f"- {step}"
                        )

            # ====================================================
            # APPLICATION DECISION
            # ====================================================

            st.divider()

            st.markdown(
                "### What would you like NextStep AI to do?"
            )

            st.caption(
                "Choose whether you want help only, or whether "
                "you want NextStep AI to prepare and submit the "
                "application when an authorized integration allows it."
            )

            decision_col1, decision_col2 = (
                st.columns(2)
            )

            with decision_col1:

                yes_clicked = st.button(
                    "✅ Yes, apply for me",
                    use_container_width=True,
                )

            with decision_col2:

                no_clicked = st.button(
                    "📋 No, only show requirements",
                    use_container_width=True,
                )

            if yes_clicked:

                if not barrier_check:

                    st.warning(
                        "First run the AI Submission Compatibility Check."
                    )

                elif (
                    capability
                    and capability.get(
                        "supported"
                    )
                ):

                    st.session_state[
                        "application_decision"
                    ] = "yes"

                    st.session_state[
                        "application_mode"
                    ] = True

                    add_conversation_message(
                        "user",
                        "Yes, apply for me",
                    )

                    save_conversation_state()

                    st.rerun()

                else:

                    st.error(
                        "NextStep AI cannot automatically submit "
                        "this service. No personal application "
                        "information will be collected."
                    )

                    if official_url:

                        st.link_button(
                            "🌐 Continue on Official Portal",
                            official_url,
                        )

            if no_clicked:

                st.session_state[
                    "application_decision"
                ] = "no"

                st.session_state[
                    "application_mode"
                ] = False

                add_conversation_message(
                    "user",
                    "No, only show requirements",
                )

                save_conversation_state()

                st.rerun()

            # ====================================================
            # REQUIREMENTS FOR NO MODE
            # ====================================================

            if (
                st.session_state.get(
                    "application_decision"
                )
                == "no"
            ):

                st.divider()

                st.markdown(
                    "### 📋 Service Requirements"
                )

                if not st.session_state.get(
                    "requirements"
                ):

                    with st.spinner(
                        "Preparing requirements..."
                    ):

                        requirements = (
                            generate_requirements(
                                service
                            )
                        )

                        st.session_state[
                            "requirements"
                        ] = requirements

                        save_conversation_state()

                requirements = (
                    st.session_state.get(
                        "requirements",
                        {},
                    )
                )

                for item in requirements.get(
                    "requirements",
                    [],
                ):

                    if isinstance(
                        item,
                        dict,
                    ):

                        mandatory = (
                            "Required"
                            if item.get(
                                "mandatory",
                                False,
                            )
                            else
                            "May be required"
                        )

                        st.markdown(
                            f"**{item.get('name', 'Requirement')}** "
                            f"({mandatory})"
                        )

                        if item.get(
                            "description"
                        ):

                            st.caption(
                                item.get(
                                    "description"
                                )
                            )

                information_needed = (
                    requirements.get(
                        "information_needed",
                        [],
                    )
                )

                if information_needed:

                    st.markdown(
                        "#### Information you may need"
                    )

                    for item in information_needed:

                        st.markdown(
                            f"- {item}"
                        )

                warnings = (
                    requirements.get(
                        "warnings",
                        [],
                    )
                )

                if warnings:

                    st.markdown(
                        "#### ⚠️ Notes"
                    )

                    for warning in warnings:

                        st.warning(
                            warning
                        )

                st.info(
                    requirements.get(
                        "verification_note",
                        "Verify requirements on the official government portal.",
                    )
                )

                if official_url:

                    st.link_button(
                        "🌐 Open Official Application Portal",
                        official_url,
                    )


# ============================================================
# APPLICATION MODE
# ============================================================

with application_tab:

    st.markdown(
        "## 📝 Application Mode"
    )

    if not st.session_state.get(
        "application_mode",
        False,
    ):

        st.info(
            "Choose 'Yes, apply for me' after the service "
            "compatibility check to enter Application Mode."
        )

    else:

        service = (
            st.session_state.get(
                "identified_service"
            )
        )

        capability = (
            st.session_state.get(
                "submission_capability"
            )
        )

        barrier_check = (
            st.session_state.get(
                "barrier_check"
            )
        )

        if not service or not capability:

            st.error(
                "Application session is incomplete. "
                "Please identify the service again."
            )

        elif not capability.get(
            "supported",
            False,
        ):

            st.error(
                "This service is not currently eligible "
                "for automatic AI submission."
            )

            st.session_state[
                "application_mode"
            ] = False

            save_conversation_state()

        else:

            st.success(
                "🟢 This service passed the AI submission checks."
            )

            st.markdown(
                f"**Service:** "
                f"{service.get('service_name', 'Unknown')}"
            )

            st.markdown(
                "### Step 1: Required information"
            )

            if not st.session_state.get(
                "requirements"
            ):

                with st.spinner(
                    "Checking required information..."
                ):

                    st.session_state[
                        "requirements"
                    ] = generate_requirements(
                        service
                    )

                    save_conversation_state()

            requirements = (
                st.session_state.get(
                    "requirements",
                    {},
                )
            )

            for item in requirements.get(
                "requirements",
                [],
            ):

                if isinstance(
                    item,
                    dict,
                ):

                    st.markdown(
                        f"- **{item.get('name', 'Requirement')}**"
                    )

            st.divider()

            # ====================================================
            # APPLICANT FORM
            # ====================================================

            st.markdown(
                "### Step 2: Applicant information"
            )

            st.caption(
                "Only provide information required for the application. "
                "Never enter passwords, OTPs, PINs or payment credentials here."
            )

            with st.form(
                "application_form"
            ):

                applicant_name = st.text_input(
                    "Full name *"
                )

                phone = st.text_input(
                    "Phone number *"
                )

                email = st.text_input(
                    "Email address"
                )

                address = st.text_area(
                    "Address"
                )

                additional_information = (
                    st.text_area(
                        "Additional information"
                    )
                )

                st.markdown(
                    "### Step 3: Review and authorization"
                )

                authorization = st.checkbox(
                    "I authorize NextStep AI to submit the above application through the configured authorized government integration."
                )

                submitted = st.form_submit_button(
                    "🚀 Review & Submit Application",
                    type="primary",
                    use_container_width=True,
                )

            if submitted:

                errors = []

                if not applicant_name.strip():

                    errors.append(
                        "Full name is required."
                    )

                if not phone.strip():

                    errors.append(
                        "Phone number is required."
                    )

                if not authorization:

                    errors.append(
                        "You must explicitly authorize submission."
                    )

                if errors:

                    for error in errors:

                        st.error(
                            error
                        )

                else:

                    st.session_state[
                        "pending_application_payload"
                    ] = {

                        "service_name": service.get(
                            "service_name",
                            "",
                        ),

                        "category": service.get(
                            "service_category",
                            "",
                        ),

                        "jurisdiction": service.get(
                            "jurisdiction",
                            "",
                        ),

                        "department": service.get(
                            "department",
                            "",
                        ),

                        "applicant": {

                            "name": applicant_name.strip(),

                            "phone": phone.strip(),

                            "email": email.strip(),

                            "address": address.strip(),

                            "additional_information": (
                                additional_information.strip()
                            ),
                        },

                        "official_portal_url": (
                            st.session_state.get(
                                "official_url",
                                "",
                            )
                        ),

                        "submission_timestamp": (
                            datetime.now().isoformat()
                        ),
                    }

                    st.session_state[
                        "ready_to_submit"
                    ] = True

                    save_conversation_state()

                    st.rerun()

            # ====================================================
            # FINAL REVIEW
            # ====================================================

            if st.session_state.get(
                "ready_to_submit",
                False,
            ):

                st.divider()

                st.markdown(
                    "## 🔎 Final Review"
                )

                payload = (
                    st.session_state.get(
                        "pending_application_payload",
                        {},
                    )
                )

                applicant = (
                    payload.get(
                        "applicant",
                        {},
                    )
                )

                review_col1, review_col2 = (
                    st.columns(2)
                )

                with review_col1:

                    st.markdown(
                        f"**Service:** "
                        f"{payload.get('service_name', '')}"
                    )

                    st.markdown(
                        f"**Name:** "
                        f"{applicant.get('name', '')}"
                    )

                    st.markdown(
                        f"**Phone:** "
                        f"{applicant.get('phone', '')}"
                    )

                with review_col2:

                    st.markdown(
                        f"**Email:** "
                        f"{applicant.get('email', '') or 'Not provided'}"
                    )

                    st.markdown(
                        f"**Address:** "
                        f"{applicant.get('address', '') or 'Not provided'}"
                    )

                st.warning(
                    "Review the information carefully. "
                    "Once submitted through the authorized integration, "
                    "the government system controls the application."
                )

                confirm_col1, confirm_col2 = (
                    st.columns(2)
                )

                with confirm_col1:

                    final_submit = st.button(
                        "🚀 Submit to Government System",
                        type="primary",
                        use_container_width=True,
                    )

                with confirm_col2:

                    cancel_submit = st.button(
                        "✏️ Edit Information",
                        use_container_width=True,
                    )

                if cancel_submit:

                    st.session_state[
                        "ready_to_submit"
                    ] = False

                    save_conversation_state()

                    st.rerun()

                if final_submit:

                    with st.spinner(
                        "📨 Submitting through the authorized government integration..."
                    ):

                        submission = (
                            submit_application(
                                payload,
                                capability.get(
                                    "integration"
                                ),
                            )
                        )

                    st.session_state[
                        "submission_result"
                    ] = submission

                    if submission.get(
                        "success"
                    ):

                        application_id = (
                            submission.get(
                                "application_id"
                            )
                        )

                        st.session_state[
                            "application_id"
                        ] = application_id

                        submission_date = date.today()

                        timeline = (
                            st.session_state.get(
                                "timeline",
                                {},
                            )
                        )

                        processing_days = (
                            timeline.get(
                                "processing_days"
                            )
                        )

                        processing_type = (
                            timeline.get(
                                "processing_type"
                            )
                        )

                        expected_completion = (
                            add_processing_days(
                                submission_date,
                                processing_days,
                                processing_type,
                            )
                        )

                        barrier_details = (
                            barrier_check
                            if barrier_check
                            else {}
                        )

                        now = (
                            datetime.now().isoformat()
                        )

                        record = {

                            "application_id":
                                application_id,

                            "service_name":
                                service.get(
                                    "service_name",
                                    "",
                                ),

                            "category":
                                service.get(
                                    "service_category",
                                    "",
                                ),

                            "jurisdiction":
                                service.get(
                                    "jurisdiction",
                                    "",
                                ),

                            "department":
                                service.get(
                                    "department",
                                    "",
                                ),

                            "applicant_name":
                                applicant.get(
                                    "name",
                                    "",
                                ),

                            "phone":
                                applicant.get(
                                    "phone",
                                    "",
                                ),

                            "email":
                                applicant.get(
                                    "email",
                                    "",
                                ),

                            "address":
                                applicant.get(
                                    "address",
                                    "",
                                ),

                            "additional_information":
                                applicant.get(
                                    "additional_information",
                                    "",
                                ),

                            "official_url":
                                payload.get(
                                    "official_portal_url",
                                    "",
                                ),

                            "submission_date":
                                submission_date.isoformat(),

                            "status":
                                "Submitted",

                            "processing_days":
                                processing_days,

                            "processing_type":
                                processing_type,

                            "expected_completion_date":
                                (
                                    expected_completion.isoformat()
                                    if expected_completion
                                    else None
                                ),

                            "timeline_source":
                                payload.get(
                                    "official_portal_url",
                                    "",
                                ),

                            "timeline_verified":
                                timeline.get(
                                    "verified",
                                    False,
                                ),

                            "ai_submission_supported":
                                True,

                            "barrier_detected":
                                bool(
                                    barrier_details.get(
                                        "barriers"
                                    )
                                ),

                            "barrier_details":
                                barrier_details,

                            "created_at":
                                now,

                            "updated_at":
                                now,
                        }

                        save_application(
                            record
                        )

                        st.session_state[
                            "ready_to_submit"
                        ] = False

                        st.session_state[
                            "last_ai_response"
                        ] = (
                            "Application submitted successfully. "
                            "Application ID: "
                            + str(
                                application_id
                            )
                        )

                        add_conversation_message(
                            "assistant",
                            (
                                "Application submitted successfully. "
                                "Application ID: "
                                + str(
                                    application_id
                                )
                            ),
                        )

                        save_conversation_state()

                        st.success(
                            "✅ Application submitted successfully through the configured authorized government integration."
                        )

                        st.markdown(
                            "### Application ID"
                        )

                        st.code(
                            application_id
                        )

                        st.info(
                            "Keep this application/reference number for tracking."
                        )

                        if expected_completion:

                            st.markdown(
                                f"**Expected completion:** "
                                f"{expected_completion.strftime('%d %B %Y')}"
                            )

                            st.caption(
                                f"Official processing timeline: "
                                f"{processing_days} "
                                f"{processing_type.replace('_', ' ')}."
                            )

                        else:

                            st.info(
                                "No verified processing timeline "
                                "was found on the official page."
                            )

                    else:

                        st.error(
                            submission.get(
                                "message",
                                "Submission failed.",
                            )
                        )

                        st.info(
                            "No fake application ID was created. "
                            "Please use the official portal if necessary."
                        )


# ============================================================
# APPLICATION STATUS TAB
# ============================================================

with status_tab:

    st.markdown(
        "## 📊 Application Status"
    )

    application_id_input = st.text_input(
        "Enter your application/reference number",
        value=(
            st.session_state.get(
                "application_id"
            )
            or ""
        ),
    )

    if st.button(
        "🔄 Check Status",
        type="primary",
        use_container_width=True,
    ):

        if not application_id_input.strip():

            st.warning(
                "Please enter an application/reference number."
            )

        else:

            with st.spinner(
                "Checking application status..."
            ):

                status_result = fetch_status(
                    application_id_input.strip()
                )

            if not status_result.get(
                "success"
            ):

                st.error(
                    status_result.get(
                        "message",
                        "Application not found.",
                    )
                )

            else:

                status = (
                    status_result.get(
                        "status",
                        "Unknown",
                    )
                )

                st.success(
                    f"Current status: **{status}**"
                )

                if status_result.get(
                    "message"
                ):

                    st.caption(
                        status_result.get(
                            "message"
                        )
                    )

                raw = (
                    status_result.get(
                        "raw",
                        {},
                    )
                )

                processing_days = (
                    raw.get(
                        "processing_days"
                    )
                )

                processing_type = (
                    raw.get(
                        "processing_type"
                    )
                )

                expected_date_raw = (
                    raw.get(
                        "expected_completion_date"
                    )
                )

                if expected_date_raw:

                    try:

                        expected_date = (
                            date.fromisoformat(
                                expected_date_raw
                            )
                        )

                        remaining = (
                            calculate_remaining_days(
                                expected_date,
                                processing_type,
                            )
                        )

                        st.metric(
                            "Remaining processing time",
                            (
                                f"{remaining} "
                                f"{'working days' if processing_type == 'working_days' else 'days'}"
                                if remaining is not None
                                else "Unavailable"
                            ),
                        )

                        st.markdown(
                            f"**Expected completion:** "
                            f"{expected_date.strftime('%d %B %Y')}"
                        )

                    except Exception:

                        pass

                if (
                    processing_days
                    and processing_type
                ):

                    st.caption(
                        f"Official processing timeline: "
                        f"{processing_days} "
                        f"{processing_type.replace('_', ' ')}."
                    )


# ============================================================
# VOICE RESPONSE
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
            "🔊 Speak Response",
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
