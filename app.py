import streamlit as st
import requests
import json
import re
import sqlite3
import os
import uuid
import base64

from datetime import datetime, date, timedelta
from urllib.parse import urlparse


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="NextStep AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_FILE = "nextstep_ai.db"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

REQUEST_TIMEOUT = 45


# ============================================================
# LANGUAGES
# ============================================================

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
    "Urdu": "ur-IN"
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
    "Gujarati"
}


# ============================================================
# SESSION STATE
# ============================================================

DEFAULT_STATE = {
    "typed_service_request": "",
    "voice_text": "",

    "service_identified": False,
    "identified_service": None,

    "application_decision": None,
    "application_mode": False,

    "requirements": None,
    "timeline": None,

    "official_url": "",

    "application_id": None,
    "submission_result": None,

    "last_ai_response": ""
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SECRETS
# ============================================================

def get_secret(name, default=""):

    try:
        value = st.secrets.get(name, None)

        if value is not None:
            return str(value)

    except Exception:
        pass

    return os.getenv(name, default)


OPENROUTER_API_KEY = get_secret(
    "OPENROUTER_API_KEY"
)

OPENROUTER_MODEL = get_secret(
    "OPENROUTER_MODEL",
    DEFAULT_MODEL
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
    "[]"
)


# ============================================================
# HOLIDAYS
# ============================================================

def get_holidays():

    try:

        values = json.loads(
            HOLIDAYS_RAW
        )

        if isinstance(values, list):

            result = set()

            for value in values:

                try:

                    result.add(
                        datetime.strptime(
                            str(value),
                            "%Y-%m-%d"
                        ).date()
                    )

                except Exception:
                    continue

            return result

    except Exception:
        pass

    return set()


HOLIDAYS = get_holidays()


# ============================================================
# DATABASE
# ============================================================

def init_database():

    conn = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            application_id TEXT UNIQUE,

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

            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()


init_database()


# ============================================================
# DATABASE SAVE
# ============================================================

def save_application(application):

    conn = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = conn.cursor()

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

            created_at,
            updated_at
        )

        VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?,
            ?, ?,
            ?, ?,
            ?,
            ?, ?,
            ?, ?
        )
        """,
        (
            application["application_id"],

            application["service_name"],
            application["category"],
            application["jurisdiction"],
            application["department"],

            application["applicant_name"],
            application["phone"],
            application["email"],
            application["address"],
            application["additional_information"],

            application["official_url"],

            application["submission_date"],
            application["status"],

            application["processing_days"],
            application["processing_type"],

            application["expected_completion_date"],

            application["timeline_source"],
            application["timeline_verified"],

            application["created_at"],
            application["updated_at"]
        )
    )

    conn.commit()
    conn.close()


# ============================================================
# DATABASE GET
# ============================================================

def get_application(application_id):

    conn = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
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

            created_at,
            updated_at

        FROM applications

        WHERE application_id = ?
        """,
        (
            application_id,
        )
    )

    row = cursor.fetchone()

    conn.close()

    if not row:
        return None

    columns = [
        "application_id",

        "service_name",
        "category",
        "jurisdiction",
        "department",

        "applicant_name",
        "phone",
        "email",
        "address",
        "additional_information",

        "official_url",

        "submission_date",
        "status",

        "processing_days",
        "processing_type",

        "expected_completion_date",

        "timeline_source",
        "timeline_verified",

        "created_at",
        "updated_at"
    ]

    return dict(
        zip(columns, row)
    )


# ============================================================
# HELPERS
# ============================================================

def safe_json(text, fallback=None):

    if fallback is None:
        fallback = {}

    if not text:
        return fallback

    text = text.strip()

    text = re.sub(
        r"^```json",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```",
        "",
        text
    )

    text = re.sub(
        r"```$",
        "",
        text
    )

    try:
        return json.loads(
            text.strip()
        )

    except Exception:
        return fallback


def generate_application_id():

    return (
        "NS-"
        + datetime.now().strftime("%Y%m%d")
        + "-"
        + uuid.uuid4().hex[:8].upper()
    )


def format_date(value):

    if not value:
        return "Not available"

    try:

        parsed = datetime.strptime(
            str(value),
            "%Y-%m-%d"
        ).date()

        return parsed.strftime(
            "%d %B %Y"
        )

    except Exception:

        return str(value)


# ============================================================
# OPENROUTER AI
# ============================================================

def call_ai(
    messages,
    temperature=0.2,
    max_tokens=1500
):

    if not OPENROUTER_API_KEY:

        return {
            "success": False,
            "error": (
                "OPENROUTER_API_KEY is not configured."
            )
        }

    headers = {
        "Authorization":
            f"Bearer {OPENROUTER_API_KEY}",

        "Content-Type":
            "application/json",

        "HTTP-Referer":
            "https://streamlit.io",

        "X-Title":
            "NextStep AI"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:

            return {
                "success": False,
                "error": (
                    f"OpenRouter error "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
                )
            }

        data = response.json()

        content = (
            data
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        if not content:

            return {
                "success": False,
                "error":
                    "AI returned an empty response."
            }

        return {
            "success": True,
            "content": content
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "error":
                "AI request timed out."
        }

    except requests.exceptions.RequestException as e:

        return {
            "success": False,
            "error":
                f"AI connection error: {str(e)}"
        }

    except Exception as e:

        return {
            "success": False,
            "error":
                f"Unexpected AI error: {str(e)}"
        }


# ============================================================
# IDENTIFY SERVICE
# ============================================================

def identify_service(
    user_request,
    language
):

    prompt = f"""
You are NextStep AI.

You identify government and public services
from any country, state, city, municipality,
or public authority.

User language:
{language}

User request:
{user_request}

Return ONLY valid JSON.

Use exactly:

{{
    "service_name": "",
    "service_category": "",
    "jurisdiction": "",
    "department": "",
    "intent": "",
    "confidence": 0,
    "explanation": ""
}}

Rules:

- Do not invent an exact department.
- Use "Unknown" when necessary.
- confidence must be between 0 and 1.
- service_name should be citizen-friendly.
"""

    result = call_ai(
        [
            {
                "role": "system",
                "content":
                    "Identify government services accurately."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    if not result["success"]:
        return result

    data = safe_json(
        result["content"],
        None
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error":
                "AI returned invalid service information."
        }

    data["success"] = True

    return data


# ============================================================
# REQUIREMENTS
# ============================================================

def generate_requirements(
    service,
    language
):

    prompt = f"""
Prepare requirements for this government service.

Service:
{service.get("service_name", "Unknown")}

Category:
{service.get("service_category", "Unknown")}

Jurisdiction:
{service.get("jurisdiction", "Unknown")}

Department:
{service.get("department", "Unknown")}

Language:
{language}

Return ONLY JSON:

{{
    "requirements": [
        {{
            "name": "",
            "description": "",
            "mandatory": true
        }}
    ],

    "information_needed": [
        ""
    ],

    "warnings": [
        ""
    ],

    "verification_note": ""
}}

Do not falsely claim that something is officially required.
Tell the citizen to verify requirements on the official portal.
"""

    result = call_ai(
        [
            {
                "role": "system",
                "content":
                    "Explain government requirements carefully."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    if not result["success"]:
        return result

    data = safe_json(
        result["content"],
        None
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error":
                "Invalid requirements returned by AI."
        }

    data["success"] = True

    return data


# ============================================================
# DISPLAY REQUIREMENTS
# ============================================================

def display_requirements(requirements):

    if not requirements:
        return

    st.subheader(
        "📋 Required Information & Documents"
    )

    items = requirements.get(
        "requirements",
        []
    )

    if items:

        for item in items:

            name = item.get(
                "name",
                "Requirement"
            )

            description = item.get(
                "description",
                ""
            )

            mandatory = item.get(
                "mandatory",
                False
            )

            if mandatory:

                st.markdown(
                    f"🔴 **{name}**"
                )

            else:

                st.markdown(
                    f"🟢 **{name}**"
                )

            if description:

                st.write(
                    description
                )

    information = requirements.get(
        "information_needed",
        []
    )

    if information:

        st.subheader(
            "📝 Information Needed"
        )

        for item in information:

            st.write(
                f"• {item}"
            )

    warnings = requirements.get(
        "warnings",
        []
    )

    if warnings:

        st.subheader(
            "⚠️ Important"
        )

        for warning in warnings:

            st.warning(
                warning
            )

    note = requirements.get(
        "verification_note",
        ""
    )

    if note:

        st.info(
            note
        )


# ============================================================
# OFFICIAL URL CHECK
# ============================================================

def is_official_url(url):

    if not url:
        return False

    try:

        parsed = urlparse(
            url
        )

        hostname = (
            parsed.hostname or ""
        ).lower()

        if parsed.scheme not in {
            "http",
            "https"
        }:

            return False

        return (
            hostname.endswith(".gov.in")
            or hostname.endswith(".gov")
            or hostname.endswith(".nic.in")
            or hostname.endswith(".ac.in")
            or hostname.endswith(".org.in")
        )

    except Exception:

        return False


# ============================================================
# READ OFFICIAL PAGE
# ============================================================

def read_official_page(url):

    if not is_official_url(url):

        return {
            "success": False,
            "error":
                "Please provide an official government website."
        }

    try:

        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent":
                    "Mozilla/5.0 NextStepAI/1.0"
            }
        )

        if response.status_code != 200:

            return {
                "success": False,
                "error":
                    f"Official page returned HTTP "
                    f"{response.status_code}."
            }

        text = response.text

        text = re.sub(
            r"<script.*?</script>",
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

        text = re.sub(
            r"<style.*?</style>",
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

        text = re.sub(
            r"<[^>]+>",
            " ",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return {
            "success": True,
            "text": text[:18000]
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "error":
                "Official website request timed out."
        }

    except Exception as e:

        return {
            "success": False,
            "error":
                f"Could not read official page: {str(e)}"
        }


# ============================================================
# VERIFY TIMELINE
# ============================================================

def verify_timeline(
    official_url,
    service_name
):

    page = read_official_page(
        official_url
    )

    if not page["success"]:
        return page

    prompt = f"""
Verify the official processing timeline.

Service:
{service_name}

Official website:
{official_url}

Page:
{page["text"]}

Look only for an explicitly stated timeline.

Examples:
7 working days
15 days
within 30 days
5 business days

Return ONLY:

{{
    "verified": true,
    "processing_days": 0,
    "processing_type": "working_days",
    "evidence": "",
    "confidence": 0
}}

processing_type must be:

calendar_days

OR

working_days

If no exact timeline is explicitly stated:
verified = false
processing_days = 0

Never guess.
"""

    result = call_ai(
        [
            {
                "role": "system",
                "content":
                    "Verify official processing timelines."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=1000
    )

    if not result["success"]:
        return result

    data = safe_json(
        result["content"],
        None
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error":
                "Invalid timeline verification."
        }

    data["success"] = True
    data["source"] = official_url

    return data


# ============================================================
# WORKING DAYS
# ============================================================

def is_working_day(day):

    if day.weekday() >= 5:
        return False

    if day in HOLIDAYS:
        return False

    return True


def add_working_days(
    start_date,
    number_of_days
):

    current = start_date
    count = 0

    while count < number_of_days:

        current += timedelta(
            days=1
        )

        if is_working_day(
            current
        ):

            count += 1

    return current


# ============================================================
# EXPECTED DATE
# ============================================================

def calculate_expected_date(
    submission_date,
    processing_days,
    processing_type
):

    if not submission_date:
        return None

    if not processing_days:
        return None

    try:

        days = int(
            processing_days
        )

    except Exception:

        return None

    if days <= 0:
        return None

    if processing_type == "working_days":

        return add_working_days(
            submission_date,
            days
        )

    return (
        submission_date
        + timedelta(days=days)
    )


# ============================================================
# DYNAMIC REMAINING DAYS
# ============================================================

def calculate_remaining_days(
    submission_date,
    processing_days,
    processing_type
):

    if not submission_date:
        return None

    try:

        submitted = datetime.strptime(
            str(submission_date),
            "%Y-%m-%d"
        ).date()

    except Exception:

        return None

    try:

        total_days = int(
            processing_days
        )

    except Exception:

        return None

    today = date.today()

    if processing_type == "working_days":

        elapsed = 0
        current = submitted

        while current < today:

            current += timedelta(
                days=1
            )

            if is_working_day(
                current
            ):

                elapsed += 1

        return max(
            0,
            total_days - elapsed
        )

    elapsed = (
        today - submitted
    ).days

    return max(
        0,
        total_days - elapsed
    )


# ============================================================
# GOVERNMENT SUBMISSION
# ============================================================

def submit_application(
    payload
):

    # ========================================================
    # REAL GOVERNMENT API
    # ========================================================

    if GOVERNMENT_SUBMISSION_URL:

        try:

            response = requests.post(
                GOVERNMENT_SUBMISSION_URL,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code not in range(
                200,
                300
            ):

                return {
                    "success": False,
                    "error":
                        f"Government API returned "
                        f"HTTP {response.status_code}"
                }

            try:

                data = response.json()

            except Exception:

                data = {}

            application_id = (
                data.get("application_id")
                or data.get("applicationId")
                or data.get("id")
            )

            if not application_id:

                application_id = (
                    generate_application_id()
                )

            return {
                "success": True,
                "real_submission": True,
                "application_id":
                    application_id,
                "status":
                    data.get(
                        "status",
                        "Submitted"
                    ),
                "message":
                    data.get(
                        "message",
                        "Application submitted successfully."
                    )
            }

        except Exception as e:

            return {
                "success": False,
                "error":
                    f"Government submission error: {str(e)}"
            }

    # ========================================================
    # DEMO / LOCAL MODE
    # ========================================================

    application_id = (
        generate_application_id()
    )

    return {
        "success": True,
        "real_submission": False,
        "application_id":
            application_id,
        "status":
            "Application Submitted",
        "message":
            "Application created in local demo mode."
    }


# ============================================================
# STATUS API
# ============================================================

def fetch_status(
    application_id
):

    # ========================================================
    # REAL GOVERNMENT STATUS API
    # ========================================================

    if GOVERNMENT_STATUS_URL:

        try:

            response = requests.post(
                GOVERNMENT_STATUS_URL,
                json={
                    "application_id":
                        application_id
                },
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code not in range(
                200,
                300
            ):

                return {
                    "success": False,
                    "error":
                        f"Status API returned "
                        f"HTTP {response.status_code}"
                }

            data = response.json()

            return {
                "success": True,
                "real_status": True,
                "status":
                    data.get(
                        "status",
                        "Status unavailable"
                    ),
                "message":
                    data.get(
                        "message",
                        ""
                    )
            }

        except Exception as e:

            return {
                "success": False,
                "error":
                    f"Status API error: {str(e)}"
            }

    # ========================================================
    # LOCAL DATABASE STATUS
    # ========================================================

    application = get_application(
        application_id
    )

    if not application:

        return {
            "success": False,
            "error":
                "Application ID not found."
        }

    return {
        "success": True,
        "real_status": False,
        "status":
            application["status"],
        "message":
            "Status is currently stored locally. "
            "Connect an authorized government status API "
            "for live status."
    }


# ============================================================
# SPEECH TO TEXT
# ============================================================

def speech_to_text(
    audio_bytes,
    language
):

    if not SARVAM_API_KEY:

        return {
            "success": False,
            "error":
                "SARVAM_API_KEY is not configured."
        }

    if not audio_bytes:

        return {
            "success": False,
            "error":
                "No audio received."
        }

    language_code = LANGUAGE_CODES.get(
        language,
        "en-IN"
    )

    headers = {
        "api-subscription-key":
            SARVAM_API_KEY
    }

    files = {
        "file": (
            "voice.wav",
            audio_bytes,
            "audio/wav"
        )
    }

    data = {
        "model":
            "saaras:v4",

        "language_code":
            language_code,

        "mode":
            "transcribe"
    }

    try:

        response = requests.post(
            SARVAM_STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:

            return {
                "success": False,
                "error":
                    f"Sarvam STT error "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
            }

        result = response.json()

        transcript = (
            result.get("transcript")
            or result.get("text")
            or ""
        )

        if not transcript:

            return {
                "success": False,
                "error":
                    "No speech detected."
            }

        return {
            "success": True,
            "text":
                transcript
        }

    except Exception as e:

        return {
            "success": False,
            "error":
                f"Voice recognition error: {str(e)}"
        }


# ============================================================
# TEXT TO SPEECH
# ============================================================

def text_to_speech(
    text,
    language
):

    if not SARVAM_API_KEY:

        return {
            "success": False,
            "error":
                "SARVAM_API_KEY is not configured."
        }

    if language not in TTS_SUPPORTED:

        return {
            "success": False,
            "error":
                f"Voice output is unavailable for {language}."
        }

    language_code = LANGUAGE_CODES.get(
        language,
        "en-IN"
    )

    headers = {
        "api-subscription-key":
            SARVAM_API_KEY,

        "Content-Type":
            "application/json"
    }

    payload = {
        "text":
            text[:5000],

        "target_language_code":
            language_code,

        "language_code":
            language_code,

        "model":
            "bulbul:v3",

        "speaker":
            "shubh"
    }

    try:

        response = requests.post(
            SARVAM_TTS_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:

            return {
                "success": False,
                "error":
                    f"Sarvam TTS error "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
            }

        data = response.json()

        audios = data.get(
            "audios",
            []
        )

        if not audios:

            return {
                "success": False,
                "error":
                    "No audio returned."
            }

        audio = base64.b64decode(
            audios[0]
        )

        return {
            "success": True,
            "audio":
                audio
        }

    except Exception as e:

        return {
            "success": False,
            "error":
                f"Voice output error: {str(e)}"
        }


# ============================================================
# CUSTOM CSS
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
        font-size: 18px;
        color: #777;
        margin-bottom: 20px;
    }

    .application-mode {
        padding: 18px;
        border-radius: 15px;
        border: 1px solid #ddd;
        margin-top: 15px;
        margin-bottom: 15px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🤖 NextStep AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="subtitle">
    Discover • Prepare • Submit • Track
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Settings")

    language = st.selectbox(
        "🌐 Language",
        list(LANGUAGE_CODES.keys())
    )

    st.divider()

    st.markdown(
        """
        ### How it works

        **1. Discover**

        Describe the government service.

        **2. Identify**

        AI identifies the service,
        jurisdiction and department.

        **3. Application Mode**

        Choose whether NextStep AI
        should help prepare the application.

        **4. Submit**

        Review and authorize the application.

        **5. Track**

        Track application status and
        processing time.
        """
    )

    st.divider()

    if GOVERNMENT_SUBMISSION_URL:

        st.success(
            "🟢 Government submission API connected"
        )

    else:

        st.info(
            "🟡 Demo submission mode"
        )

    if GOVERNMENT_STATUS_URL:

        st.success(
            "🟢 Live status API connected"
        )

    else:

        st.info(
            "🟡 Local status tracking"
        )


# ============================================================
# TABS
# ============================================================

tab_assistant, tab_application, tab_status = st.tabs(
    [
        "🤖 Assistant",
        "📝 Application Mode",
        "🔎 Application Status"
    ]
)


# ============================================================
# ASSISTANT
# ============================================================

with tab_assistant:

    st.header(
        "What government service do you need?"
    )

    st.write(
        "Describe the service by typing or using your voice."
    )

    # --------------------------------------------------------
    # VOICE
    # --------------------------------------------------------

    st.subheader(
        "🎙️ Voice Input"
    )

    audio = st.audio_input(
        "Record your government-service request"
    )

    if audio is not None:

        if st.button(
            "🎤 Convert Voice to Text",
            key="convert_voice"
        ):

            with st.spinner(
                "Understanding your voice..."
            ):

                voice_result = speech_to_text(
                    audio.getvalue(),
                    language
                )

            if voice_result["success"]:

                st.session_state[
                    "voice_text"
                ] = voice_result["text"]

                st.session_state[
                    "typed_service_request"
                ] = voice_result["text"]

                st.success(
                    "Voice converted successfully."
                )

                st.rerun()

            else:

                st.error(
                    voice_result["error"]
                )

    # --------------------------------------------------------
    # TEXT REQUEST
    # --------------------------------------------------------

    request_text = st.text_area(
        "📝 Service request",

        value=st.session_state[
            "typed_service_request"
        ],

        key="service_request_box",

        height=120,

        placeholder=(
            "Example: I want to apply for a birth certificate"
        )
    )

    st.session_state[
        "typed_service_request"
    ] = request_text

    # --------------------------------------------------------
    # IDENTIFY
    # --------------------------------------------------------

    if st.button(
        "🔍 Identify Service",
        type="primary",
        use_container_width=True,
        key="identify_service"
    ):

        if not request_text.strip():

            st.warning(
                "Please describe a government service first."
            )

        else:

            with st.spinner(
                "AI is identifying the service..."
            ):

                result = identify_service(
                    request_text.strip(),
                    language
                )

            if result["success"]:

                # ====================================================
                # IMPORTANT
                # Persist identification BEFORE rerun.
                # ====================================================

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

                st.rerun()

            else:

                st.error(
                    result["error"]
                )

    # ========================================================
    # IDENTIFIED SERVICE
    # ========================================================

    if st.session_state.get(
        "service_identified",
        False
    ):

        service = st.session_state.get(
            "identified_service"
        )

        if service:

            st.divider()

            st.subheader(
                "🎯 Service Identified"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.markdown(
                    f"""
                    **Service**

                    {service.get(
                        "service_name",
                        "Unknown"
                    )}

                    **Category**

                    {service.get(
                        "service_category",
                        "Unknown"
                    )}

                    **Jurisdiction**

                    {service.get(
                        "jurisdiction",
                        "Unknown"
                    )}
                    """
                )

            with col2:

                confidence = service.get(
                    "confidence",
                    0
                )

                try:

                    confidence_percent = (
                        float(confidence) * 100
                    )

                except Exception:

                    confidence_percent = 0

                st.markdown(
                    f"""
                    **Department**

                    {service.get(
                        "department",
                        "Unknown"
                    )}

                    **AI Confidence**

                    {confidence_percent:.0f}%

                    **Intent**

                    {service.get(
                        "intent",
                        "Unknown"
                    )}
                    """
                )

            if service.get(
                "explanation"
            ):

                st.info(
                    service[
                        "explanation"
                    ]
                )

            # ====================================================
            # APPLICATION MODE
            # ====================================================

            st.divider()

            st.subheader(
                "🚀 Application Mode"
            )

            st.write(
                "What would you like NextStep AI to do?"
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "✅ Yes, apply for me",
                    type="primary",
                    use_container_width=True,
                    key="apply_yes"
                ):

                    st.session_state[
                        "application_decision"
                    ] = "yes"

                    st.session_state[
                        "application_mode"
                    ] = True

                    st.rerun()

            with col2:

                if st.button(
                    "📋 No, only show requirements",
                    use_container_width=True,
                    key="apply_no"
                ):

                    st.session_state[
                        "application_decision"
                    ] = "no"

                    st.session_state[
                        "application_mode"
                    ] = False

                    st.rerun()

            # ====================================================
            # REQUIREMENTS ONLY MODE
            # ====================================================

            if st.session_state.get(
                "application_decision"
            ) == "no":

                st.info(
                    "📋 Requirements-only mode is active."
                )

                if st.session_state.get(
                    "requirements"
                ) is None:

                    with st.spinner(
                        "Preparing requirements..."
                    ):

                        requirements = generate_requirements(
                            service,
                            language
                        )

                    if requirements["success"]:

                        st.session_state[
                            "requirements"
                        ] = requirements

                    else:

                        st.error(
                            requirements["error"]
                        )

                display_requirements(
                    st.session_state.get(
                        "requirements"
                    )
                )

                st.success(
                    "No applicant information was collected."
                )

            # ====================================================
            # APPLICATION MODE ACTIVE
            # ====================================================

            if st.session_state.get(
                "application_mode",
                False
            ):

                st.success(
                    "🟢 Application Mode is active."
                )

                st.markdown(
                    """
                    Your service has been identified.

                    NextStep AI will now:

                    **1️⃣ Check requirements**

                    **2️⃣ Collect applicant information**

                    **3️⃣ Verify the processing timeline**

                    **4️⃣ Ask for authorization**

                    **5️⃣ Submit through the configured backend**

                    **6️⃣ Generate an application ID**

                    **7️⃣ Track the application status**
                    """
                )

                if st.session_state.get(
                    "requirements"
                ) is None:

                    with st.spinner(
                        "Preparing application requirements..."
                    ):

                        requirements = generate_requirements(
                            service,
                            language
                        )

                    if requirements["success"]:

                        st.session_state[
                            "requirements"
                        ] = requirements

                    else:

                        st.error(
                            requirements["error"]
                        )

                display_requirements(
                    st.session_state.get(
                        "requirements"
                    )
                )

                st.info(
                    "➡️ Open the **📝 Application Mode** tab "
                    "to continue."
                )


# ============================================================
# APPLICATION MODE TAB
# ============================================================

with tab_application:

    st.header(
        "📝 Application Mode"
    )

    # ========================================================
    # APPLICATION MODE NOT ACTIVE
    # ========================================================

    if not st.session_state.get(
        "application_mode",
        False
    ):

        st.info(
            "Application Mode is not active."
        )

        st.write(
            "Go to the **🤖 Assistant** tab, "
            "identify a service, and select "
            "**✅ Yes, apply for me**."
        )

    else:

        service = st.session_state.get(
            "identified_service"
        )

        if not service:

            st.warning(
                "No service has been identified."
            )

        else:

            st.success(
                "🟢 Application Mode Active"
            )

            st.markdown(
                f"""
                ### Selected Service

                **{service.get(
                    "service_name",
                    "Unknown"
                )}**

                **Category:** {
                    service.get(
                        "service_category",
                        "Unknown"
                    )
                }

                **Jurisdiction:** {
                    service.get(
                        "jurisdiction",
                        "Unknown"
                    )
                }
                """
            )

            st.divider()

            st.subheader(
                "👤 Applicant Information"
            )

            with st.form(
                "application_form"
            ):

                full_name = st.text_input(
                    "Full Name *"
                )

                phone = st.text_input(
                    "Phone Number *"
                )

                email = st.text_input(
                    "Email Address"
                )

                address = st.text_area(
                    "Address *"
                )

                additional_information = st.text_area(
                    "Additional Information"
                )

                st.divider()

                st.subheader(
                    "🌐 Official Service Portal"
                )

                official_url = st.text_input(
                    "Official government service URL",
                    value=st.session_state.get(
                        "official_url",
                        ""
                    ),
                    placeholder=(
                        "https://example.gov.in/service"
                    )
                )

                st.caption(
                    "If available, provide the official "
                    "government service page so NextStep AI "
                    "can verify the processing timeline."
                )

                st.divider()

                st.subheader(
                    "🔐 Authorization"
                )

                authorization = st.checkbox(
                    "I authorize NextStep AI to submit this "
                    "application through an authorized "
                    "government integration when configured."
                )

                submit = st.form_submit_button(
                    "🚀 Submit Application",
                    type="primary",
                    use_container_width=True
                )

            # ====================================================
            # SUBMISSION
            # ====================================================

            if submit:

                errors = []

                if not full_name.strip():

                    errors.append(
                        "Full Name is required."
                    )

                if not phone.strip():

                    errors.append(
                        "Phone Number is required."
                    )

                if not address.strip():

                    errors.append(
                        "Address is required."
                    )

                if not authorization:

                    errors.append(
                        "Authorization is required."
                    )

                if errors:

                    for error in errors:

                        st.error(
                            error
                        )

                else:

                    st.session_state[
                        "official_url"
                    ] = official_url.strip()

                    # ==================================================
                    # VERIFY TIMELINE
                    # ==================================================

                    timeline = None

                    if official_url.strip():

                        with st.spinner(
                            "Checking official processing timeline..."
                        ):

                            timeline = verify_timeline(
                                official_url.strip(),
                                service.get(
                                    "service_name",
                                    "Unknown"
                                )
                            )

                        if timeline["success"]:

                            if timeline.get(
                                "verified",
                                False
                            ):

                                st.success(
                                    "✅ Official processing timeline verified."
                                )

                                st.session_state[
                                    "timeline"
                                ] = timeline

                            else:

                                st.warning(
                                    "The official website did not "
                                    "provide a clearly verifiable "
                                    "processing timeline."
                                )

                        else:

                            st.warning(
                                timeline["error"]
                            )

                    # ==================================================
                    # TIMELINE
                    # ==================================================

                    verified_timeline = (
                        st.session_state.get(
                            "timeline"
                        )
                    )

                    if (
                        verified_timeline
                        and verified_timeline.get(
                            "verified",
                            False
                        )
                    ):

                        processing_days = int(
                            verified_timeline.get(
                                "processing_days",
                                0
                            )
                        )

                        processing_type = (
                            verified_timeline.get(
                                "processing_type",
                                "calendar_days"
                            )
                        )

                        timeline_source = (
                            verified_timeline.get(
                                "source",
                                official_url
                            )
                        )

                        timeline_verified = 1

                    else:

                        processing_days = 0

                        processing_type = (
                            "calendar_days"
                        )

                        timeline_source = ""

                        timeline_verified = 0

                    submission_date = date.today()

                    expected_date = (
                        calculate_expected_date(
                            submission_date,
                            processing_days,
                            processing_type
                        )
                    )

                    # ==================================================
                    # PAYLOAD
                    # ==================================================

                    payload = {

                        "service": {

                            "name":
                                service.get(
                                    "service_name",
                                    ""
                                ),

                            "category":
                                service.get(
                                    "service_category",
                                    ""
                                ),

                            "jurisdiction":
                                service.get(
                                    "jurisdiction",
                                    ""
                                ),

                            "department":
                                service.get(
                                    "department",
                                    ""
                                )
                        },

                        "applicant": {

                            "full_name":
                                full_name.strip(),

                            "phone":
                                phone.strip(),

                            "email":
                                email.strip(),

                            "address":
                                address.strip(),

                            "additional_information":
                                additional_information.strip()
                        },

                        "official_service_url":
                            official_url.strip(),

                        "submission_date":
                            submission_date.isoformat()
                    }

                    # ==================================================
                    # SUBMIT
                    # ==================================================

                    with st.spinner(
                        "Submitting application..."
                    ):

                        result = submit_application(
                            payload
                        )

                    if not result["success"]:

                        st.error(
                            result["error"]
                        )

                    else:

                        application_id = (
                            result[
                                "application_id"
                            ]
                        )

                        status = result.get(
                            "status",
                            "Application Submitted"
                        )

                        now = datetime.now().isoformat()

                        application_record = {

                            "application_id":
                                application_id,

                            "service_name":
                                service.get(
                                    "service_name",
                                    ""
                                ),

                            "category":
                                service.get(
                                    "service_category",
                                    ""
                                ),

                            "jurisdiction":
                                service.get(
                                    "jurisdiction",
                                    ""
                                ),

                            "department":
                                service.get(
                                    "department",
                                    ""
                                ),

                            "applicant_name":
                                full_name.strip(),

                            "phone":
                                phone.strip(),

                            "email":
                                email.strip(),

                            "address":
                                address.strip(),

                            "additional_information":
                                additional_information.strip(),

                            "official_url":
                                official_url.strip(),

                            "submission_date":
                                submission_date.isoformat(),

                            "status":
                                status,

                            "processing_days":
                                processing_days,

                            "processing_type":
                                processing_type,

                            "expected_completion_date":
                                (
                                    expected_date.isoformat()
                                    if expected_date
                                    else None
                                ),

                            "timeline_source":
                                timeline_source,

                            "timeline_verified":
                                timeline_verified,

                            "created_at":
                                now,

                            "updated_at":
                                now
                        }

                        try:

                            save_application(
                                application_record
                            )

                            st.session_state[
                                "application_id"
                            ] = application_id

                            st.session_state[
                                "submission_result"
                            ] = result

                            st.success(
                                "🎉 Application submitted successfully."
                            )

                            st.markdown(
                                f"""
                                ## 🆔 Application ID

                                # `{application_id}`
                                """
                            )

                            st.write(
                                f"**Current Status:** {status}"
                            )

                            if result.get(
                                "real_submission",
                                False
                            ):

                                st.success(
                                    "🟢 Sent through the configured "
                                    "government integration."
                                )

                            else:

                                st.warning(
                                    "🟡 Demo mode: this application "
                                    "is stored locally. A real "
                                    "government submission requires "
                                    "an authorized government API."
                                )

                            if expected_date:

                                st.info(
                                    "**Expected completion:** "
                                    + format_date(
                                        expected_date
                                    )
                                )

                            else:

                                st.info(
                                    "No verified processing timeline "
                                    "was available."
                                )

                            st.success(
                                "➡️ Open the **🔎 Application Status** "
                                "tab to track it."
                            )

                        except Exception as e:

                            st.error(
                                "Could not save the application: "
                                + str(e)
                            )


# ============================================================
# APPLICATION STATUS TAB
# ============================================================

with tab_status:

    st.header(
        "🔎 Application Status"
    )

    st.write(
        "Enter your application ID to check the "
        "current status and remaining processing time."
    )

    default_application_id = (
        st.session_state.get(
            "application_id",
            ""
        )
    )

    application_id = st.text_input(
        "Application ID",
        value=default_application_id,
        placeholder="NS-20260925-XXXXXXXX"
    )

    if st.button(
        "🔎 Check Application Status",
        type="primary",
        use_container_width=True,
        key="check_status"
    ):

        if not application_id.strip():

            st.warning(
                "Please enter an application ID."
            )

        else:

            with st.spinner(
                "Checking application status..."
            ):

                status_result = fetch_status(
                    application_id.strip()
                )

            if not status_result["success"]:

                st.error(
                    status_result["error"]
                )

            else:

                application = get_application(
                    application_id.strip()
                )

                # ==================================================
                # STATUS
                # ==================================================

                st.subheader(
                    "📌 Current Application Status"
                )

                current_status = status_result.get(
                    "status",
                    "Status unavailable"
                )

                if current_status.lower() in {
                    "approved",
                    "completed",
                    "delivered"
                }:

                    st.success(
                        f"✅ {current_status}"
                    )

                elif current_status.lower() in {
                    "rejected",
                    "cancelled",
                    "failed"
                }:

                    st.error(
                        f"❌ {current_status}"
                    )

                else:

                    st.info(
                        f"🔄 {current_status}"
                    )

                if status_result.get(
                    "message"
                ):

                    st.caption(
                        status_result["message"]
                    )

                # ==================================================
                # APPLICATION DETAILS
                # ==================================================

                if application:

                    st.divider()

                    st.subheader(
                        "📄 Application Details"
                    )

                    col1, col2 = st.columns(2)

                    with col1:

                        st.markdown(
                            f"""
                            **Application ID**

                            `{application["application_id"]}`

                            **Service**

                            {application["service_name"]}

                            **Category**

                            {application["category"]}

                            **Jurisdiction**

                            {application["jurisdiction"]}

                            **Department**

                            {application["department"]}
                            """
                        )

                    with col2:

                        st.markdown(
                            f"""
                            **Submitted On**

                            {format_date(
                                application["submission_date"]
                            )}

                            **Processing Type**

                            {application["processing_type"]}

                            **Official Timeline**

                            {
                                str(
                                    application["processing_days"]
                                )
                                + " day(s)"
                                if application["processing_days"]
                                else "Not verified"
                            }
                            """
                        )

                    # ==================================================
                    # DYNAMIC COUNTDOWN
                    # ==================================================

                    st.divider()

                    st.subheader(
                        "⏳ Processing Timeline"
                    )

                    if application[
                        "processing_days"
                    ]:

                        remaining = (
                            calculate_remaining_days(
                                application[
                                    "submission_date"
                                ],

                                application[
                                    "processing_days"
                                ],

                                application[
                                    "processing_type"
                                ]
                            )
                        )

                        expected = application[
                            "expected_completion_date"
                        ]

                        col1, col2, col3 = st.columns(3)

                        with col1:

                            if remaining is not None:

                                st.metric(
                                    "Days Remaining",
                                    f"{remaining}"
                                )

                        with col2:

                            st.metric(
                                "Official Timeline",
                                (
                                    f"{application['processing_days']} "
                                    f"day(s)"
                                )
                            )

                        with col3:

                            if expected:

                                st.metric(
                                    "Expected Completion",
                                    format_date(
                                        expected
                                    )
                                )

                        if remaining is not None:

                            if remaining > 0:

                                st.success(
                                    f"⏳ Approximately "
                                    f"{remaining} day(s) remaining "
                                    f"according to the verified "
                                    f"processing timeline."
                                )

                            else:

                                st.warning(
                                    "⚠️ The official processing "
                                    "timeline has been reached."
                                )

                    else:

                        st.info(
                            "⏳ A dynamic countdown is unavailable "
                            "because no official processing timeline "
                            "was verified."
                        )

                    # ==================================================
                    # TIMELINE SOURCE
                    # ==================================================

                    if application[
                        "timeline_verified"
                    ]:

                        st.success(
                            "✅ Processing timeline verified "
                            "from an official source."
                        )

                        if application[
                            "timeline_source"
                        ]:

                            st.caption(
                                "Timeline source: "
                                + application[
                                    "timeline_source"
                                ]
                            )

                    else:

                        st.info(
                            "The processing timeline was not "
                            "officially verified."
                        )

                else:

                    st.warning(
                        "The application exists in the external "
                        "status system, but local application details "
                        "are not available."
                    )


# ============================================================
# VOICE ASSISTANT
# ============================================================

st.divider()

st.subheader(
    "🔊 Voice Assistant"
)

if st.session_state.get(
    "last_ai_response"
):

    if st.button(
        "🔊 Speak Response"
    ):

        with st.spinner(
            "Generating voice..."
        ):

            audio_result = text_to_speech(
                st.session_state[
                    "last_ai_response"
                ],
                language
            )

        if audio_result["success"]:

            st.audio(
                audio_result["audio"],
                format="audio/wav"
            )

        else:

            st.warning(
                audio_result["error"]
            )

else:

    st.caption(
        "Voice output is available when an AI response is generated."
    )


