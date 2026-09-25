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
# CONSTANTS
# ============================================================

DATABASE_FILE = "nextstep_ai.db"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

REQUEST_TIMEOUT = 45


# ============================================================
# LANGUAGE CONFIGURATION
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

DEFAULT_SESSION_STATE = {
    "typed_service_request": "",
    "voice_text": "",
    "service_identified": False,
    "identified_service": None,
    "application_decision": None,
    "requirements": None,
    "timeline": None,
    "application_id": None,
    "last_ai_response": "",
    "official_url": "",
    "submission_result": None
}

for key, value in DEFAULT_SESSION_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SECRETS / ENVIRONMENT VARIABLES
# ============================================================

def get_secret(name, default=""):
    """
    Reads a value from Streamlit secrets first,
    then environment variables.
    """

    try:
        value = st.secrets.get(name, None)

        if value is not None:
            return str(value)

    except Exception:
        pass

    return os.getenv(name, default)


OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY")
OPENROUTER_MODEL = get_secret(
    "OPENROUTER_MODEL",
    DEFAULT_MODEL
)

SARVAM_API_KEY = get_secret("SARVAM_API_KEY")

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
        holidays = json.loads(HOLIDAYS_RAW)

        if isinstance(holidays, list):
            result = set()

            for item in holidays:
                try:
                    result.add(
                        datetime.strptime(
                            str(item),
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

    conn = sqlite3.connect(DATABASE_FILE)

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
# DATABASE HELPERS
# ============================================================

def save_application(application):

    conn = sqlite3.connect(DATABASE_FILE)

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO applications (
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

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def get_application(application_id):

    conn = sqlite3.connect(DATABASE_FILE)

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
        (application_id,)
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

    return dict(zip(columns, row))


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_json_text(text):

    if not text:
        return ""

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?",
            "",
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r"```$",
            "",
            text
        )

    return text.strip()


def safe_json_loads(text, fallback=None):

    if fallback is None:
        fallback = {}

    try:
        return json.loads(
            clean_json_text(text)
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

        return parsed.strftime("%d %B %Y")

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
                "OPENROUTER_API_KEY is not configured. "
                "Please add it to Streamlit Secrets."
            )
        }

    headers = {
        "Authorization": (
            f"Bearer {OPENROUTER_API_KEY}"
        ),
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.io",
        "X-Title": "NextStep AI"
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
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        if not content:

            return {
                "success": False,
                "error": "AI returned an empty response."
            }

        return {
            "success": True,
            "content": content
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "error": "AI request timed out."
        }

    except requests.exceptions.RequestException as e:

        return {
            "success": False,
            "error": f"AI connection error: {str(e)}"
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"Unexpected AI error: {str(e)}"
        }


# ============================================================
# IDENTIFY GOVERNMENT SERVICE
# ============================================================

def identify_service(user_request, language):

    prompt = f"""
You are NextStep AI, an AI assistant for government and public services.

The user may describe any government service from any country, state,
city, municipality, or public authority.

User language:
{language}

User request:
{user_request}

Identify the most likely government/public service.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "service_name": "",
    "service_category": "",
    "jurisdiction": "",
    "department": "",
    "intent": "",
    "confidence": 0,
    "explanation": ""
}}

Important:
- Do not invent an exact government department if it cannot be determined.
- jurisdiction may be "Unknown".
- department may be "Unknown".
- confidence must be a number between 0 and 1.
- service_name should be understandable to an ordinary citizen.
"""

    result = call_ai(
        [
            {
                "role": "system",
                "content": (
                    "You identify government services accurately "
                    "and return strict JSON."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    if not result["success"]:
        return result

    data = safe_json_loads(
        result["content"],
        None
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error": "AI returned invalid service information."
        }

    data["success"] = True

    return data


# ============================================================
# REQUIREMENTS GENERATION
# ============================================================

def generate_requirements(service_info, language):

    prompt = f"""
You are helping a citizen prepare for a government service.

Service:
{service_info.get("service_name", "Unknown")}

Category:
{service_info.get("service_category", "Unknown")}

Jurisdiction:
{service_info.get("jurisdiction", "Unknown")}

Department:
{service_info.get("department", "Unknown")}

Language:
{language}

Return ONLY valid JSON.

Structure:

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

Important:
- Do not claim a document is officially required unless it is reasonably
  standard or verified.
- Clearly state that exact requirements should be checked against the
  relevant official government portal.
"""

    result = call_ai(
        [
            {
                "role": "system",
                "content": (
                    "You explain government-service requirements "
                    "carefully and avoid fabricating official rules."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    if not result["success"]:
        return result

    data = safe_json_loads(
        result["content"],
        None
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error": "Could not understand AI requirements."
        }

    data["success"] = True

    return data


# ============================================================
# OFFICIAL URL VALIDATION
# ============================================================

def is_official_url(url):

    if not url:
        return False

    try:

        parsed = urlparse(url)

        hostname = (
            parsed.hostname or ""
        ).lower()

        if parsed.scheme not in {
            "http",
            "https"
        }:
            return False

        allowed = (
            hostname.endswith(".gov.in")
            or hostname.endswith(".gov")
            or hostname.endswith(".nic.in")
            or hostname.endswith(".ac.in")
            or hostname.endswith(".org.in")
        )

        return allowed

    except Exception:

        return False


# ============================================================
# READ OFFICIAL PAGE
# ============================================================

def read_official_page(url):

    if not is_official_url(url):

        return {
            "success": False,
            "error": (
                "For timeline verification, please provide "
                "an official government website."
            )
        }

    try:

        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "NextStepAI/1.0"
                )
            }
        )

        if response.status_code != 200:

            return {
                "success": False,
                "error": (
                    f"Official page returned "
                    f"HTTP {response.status_code}."
                )
            }

        html = response.text

        html = re.sub(
            r"<script.*?</script>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        html = re.sub(
            r"<style.*?</style>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        html = re.sub(
            r"<[^>]+>",
            " ",
            html
        )

        html = re.sub(
            r"\s+",
            " ",
            html
        )

        text = html.strip()

        if not text:

            return {
                "success": False,
                "error": "Official page contains no readable text."
            }

        return {
            "success": True,
            "text": text[:18000]
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "error": "Official website request timed out."
        }

    except requests.exceptions.RequestException as e:

        return {
            "success": False,
            "error": (
                f"Could not access official website: {str(e)}"
            )
        }

    except Exception as e:

        return {
            "success": False,
            "error": f"Website reading error: {str(e)}"
        }


# ============================================================
# VERIFY PROCESSING TIMELINE
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
You are verifying an official government service processing timeline.

Service:
{service_name}

Official website:
{official_url}

Official page text:
{page["text"]}

Look ONLY for an explicitly stated processing timeline.

Examples:
- "7 working days"
- "15 days"
- "within 30 days"
- "processed in 5 business days"

Return ONLY valid JSON:

{{
    "verified": true,
    "processing_days": 0,
    "processing_type": "working_days",
    "evidence": "",
    "confidence": 0
}}

Rules:
- processing_type must be either:
  "calendar_days"
  or
  "working_days"
- If the official page does NOT explicitly provide a timeline:
  verified must be false and processing_days must be 0.
- Do NOT guess.
- Do NOT convert vague language into an exact number.
"""

    result = call_ai(
        [
            {
                "role": "system",
                "content": (
                    "You verify official processing timelines "
                    "without inventing numbers."
                )
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

    data = safe_json_loads(
        result["content"],
        None
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error": "Timeline verification returned invalid data."
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


def add_working_days(start_date, number_of_days):

    current = start_date
    added = 0

    while added < number_of_days:

        current += timedelta(days=1)

        if is_working_day(current):
            added += 1

    return current


def calculate_expected_completion(
    submission_date,
    processing_days,
    processing_type
):

    if not submission_date:
        return None

    if processing_days is None:
        return None

    try:

        processing_days = int(
            processing_days
        )

    except Exception:

        return None

    if processing_days <= 0:
        return None

    if processing_type == "working_days":

        return add_working_days(
            submission_date,
            processing_days
        )

    return (
        submission_date
        + timedelta(days=processing_days)
    )


# ============================================================
# REMAINING DAYS
# ============================================================

def calculate_remaining_days(
    submission_date,
    processing_days,
    processing_type
):

    if not submission_date:
        return None

    try:

        submission = datetime.strptime(
            str(submission_date),
            "%Y-%m-%d"
        ).date()

    except Exception:

        return None

    if processing_days is None:
        return None

    try:

        processing_days = int(
            processing_days
        )

    except Exception:

        return None

    if processing_days <= 0:
        return None

    today = date.today()

    if processing_type == "working_days":

        elapsed = 0
        current = submission

        while current < today:

            current += timedelta(days=1)

            if is_working_day(current):
                elapsed += 1

        remaining = (
            processing_days - elapsed
        )

    else:

        elapsed = (
            today - submission
        ).days

        remaining = (
            processing_days - elapsed
        )

    return max(0, remaining)


# ============================================================
# GENERIC GOVERNMENT SUBMISSION
# ============================================================

def submit_application(application_data):

    """
    If GOVERNMENT_SUBMISSION_URL is configured,
    submit to the authorized backend.

    Otherwise create a local/demo application record.

    The local mode must NOT be confused with a real
    government submission.
    """

    if GOVERNMENT_SUBMISSION_URL:

        try:

            response = requests.post(
                GOVERNMENT_SUBMISSION_URL,
                json=application_data,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code not in range(200, 300):

                return {
                    "success": False,
                    "error": (
                        "Government submission failed: "
                        f"HTTP {response.status_code}"
                    )
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
                "application_id": application_id,
                "status": (
                    data.get(
                        "status",
                        "Submitted"
                    )
                ),
                "message": (
                    data.get(
                        "message",
                        "Application submitted successfully."
                    )
                )
            }

        except requests.exceptions.Timeout:

            return {
                "success": False,
                "error": (
                    "Government submission service timed out."
                )
            }

        except requests.exceptions.RequestException as e:

            return {
                "success": False,
                "error": (
                    f"Government submission error: {str(e)}"
                )
            }

        except Exception as e:

            return {
                "success": False,
                "error": (
                    f"Submission error: {str(e)}"
                )
            }

    # --------------------------------------------------------
    # LOCAL DEMO MODE
    # --------------------------------------------------------

    application_id = generate_application_id()

    return {
        "success": True,
        "real_submission": False,
        "application_id": application_id,
        "status": "Application Submitted",
        "message": (
            "Demo application created locally. "
            "A real government submission requires "
            "an authorized government backend/API."
        )
    }


# ============================================================
# STATUS API
# ============================================================

def fetch_status(application_id):

    if GOVERNMENT_STATUS_URL:

        try:

            response = requests.post(
                GOVERNMENT_STATUS_URL,
                json={
                    "application_id": application_id
                },
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code not in range(200, 300):

                return {
                    "success": False,
                    "error": (
                        f"Status API returned "
                        f"HTTP {response.status_code}"
                    )
                }

            data = response.json()

            return {
                "success": True,
                "status": data.get(
                    "status",
                    "Status unavailable"
                ),
                "message": data.get(
                    "message",
                    ""
                ),
                "real_status": True
            }

        except Exception as e:

            return {
                "success": False,
                "error": (
                    f"Status API error: {str(e)}"
                )
            }

    # --------------------------------------------------------
    # LOCAL STATUS
    # --------------------------------------------------------

    application = get_application(
        application_id
    )

    if not application:

        return {
            "success": False,
            "error": "Application ID not found."
        }

    return {
        "success": True,
        "status": application["status"],
        "message": (
            "This is the locally stored demo status. "
            "Live government status requires an authorized API."
        ),
        "real_status": False
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
            "error": (
                "SARVAM_API_KEY is not configured."
            )
        }

    if not audio_bytes:

        return {
            "success": False,
            "error": "No audio was received."
        }

    language_code = LANGUAGE_CODES.get(
        language,
        "en-IN"
    )

    headers = {
        "api-subscription-key": SARVAM_API_KEY
    }

    files = {
        "file": (
            "voice.wav",
            audio_bytes,
            "audio/wav"
        )
    }

    data = {
        "model": "saaras:v4",
        "language_code": language_code,
        "mode": "transcribe"
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
                "error": (
                    f"Sarvam STT error "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
                )
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
                "error": "No speech was detected."
            }

        return {
            "success": True,
            "text": transcript
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "error": "Voice recognition timed out."
        }

    except Exception as e:

        return {
            "success": False,
            "error": (
                f"Voice recognition error: {str(e)}"
            )
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
            "error": (
                "SARVAM_API_KEY is not configured."
            )
        }

    if language not in TTS_SUPPORTED:

        return {
            "success": False,
            "error": (
                f"Voice output is currently unavailable "
                f"for {language}."
            )
        }

    language_code = LANGUAGE_CODES.get(
        language,
        "en-IN"
    )

    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "text": text[:5000],
        "target_language_code": language_code,
        "language_code": language_code,
        "model": "bulbul:v3",
        "speaker": "shubh"
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
                "error": (
                    f"Sarvam TTS error "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
                )
            }

        result = response.json()

        audios = result.get(
            "audios",
            []
        )

        if not audios:

            return {
                "success": False,
                "error": "No audio was returned."
            }

        audio_data = base64.b64decode(
            audios[0]
        )

        return {
            "success": True,
            "audio": audio_data
        }

    except Exception as e:

        return {
            "success": False,
            "error": (
                f"Voice output error: {str(e)}"
            )
        }


# ============================================================
# UI HELPERS
# ============================================================

def display_requirements(requirements):

    if not requirements:
        return

    st.subheader("📋 Service Requirements")

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
                    f"**🔴 {name}**"
                )

            else:

                st.markdown(
                    f"**🟢 {name}**"
                )

            if description:
                st.write(description)

    information_needed = requirements.get(
        "information_needed",
        []
    )

    if information_needed:

        st.subheader("📝 Information You May Need")

        for item in information_needed:

            st.write(
                f"• {item}"
            )

    warnings = requirements.get(
        "warnings",
        []
    )

    if warnings:

        st.subheader("⚠️ Important")

        for warning in warnings:

            st.warning(warning)

    note = requirements.get(
        "verification_note"
    )

    if note:

        st.info(note)


# ============================================================
# HEADER
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

    .service-card {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #ddd;
        margin-top: 15px;
        margin-bottom: 15px;
    }

    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    '<div class="main-title">🤖 NextStep AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="subtitle">
    Discover • Prepare • Submit • Track government services
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
        list(LANGUAGE_CODES.keys()),
        index=0
    )

    st.divider()

    st.markdown(
        """
        ### How NextStep AI works

        **1️⃣ Describe your service**

        Tell NextStep AI what government service
        you need.

        **2️⃣ Identify**

        AI identifies the likely service,
        jurisdiction and department.

        **3️⃣ Decide**

        Choose whether you want NextStep AI
        to prepare the application.

        **4️⃣ Submit**

        Review your information and authorize
        the application.

        **5️⃣ Track**

        Get the application ID and monitor
        the application status.
        """
    )

    st.divider()

    if GOVERNMENT_SUBMISSION_URL:

        st.success(
            "Government submission API configured."
        )

    else:

        st.info(
            "Demo submission mode is active."
        )

    if GOVERNMENT_STATUS_URL:

        st.success(
            "Government status API configured."
        )

    else:

        st.info(
            "Local status tracking is active."
        )


# ============================================================
# TABS
# ============================================================

tab_assistant, tab_application, tab_tracking = st.tabs(
    [
        "🤖 Assistant",
        "📝 Application",
        "🔎 Track Status"
    ]
)


# ============================================================
# ASSISTANT TAB
# ============================================================

with tab_assistant:

    st.header("What government service do you need?")

    st.write(
        "Describe the service in your own words. "
        "You can type or use your voice."
    )

    # --------------------------------------------------------
    # VOICE INPUT
    # --------------------------------------------------------

    st.subheader("🎙️ Voice Input")

    audio = st.audio_input(
        "Record your request"
    )

    if audio is not None:

        if st.button(
            "🎤 Convert Voice to Text",
            key="convert_voice_button"
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

                # IMPORTANT FIX:
                # Persist voice text into the actual
                # service request state.

                st.session_state[
                    "typed_service_request"
                ] = voice_result["text"]

                st.success(
                    "Voice converted successfully."
                )

            else:

                st.error(
                    voice_result["error"]
                )

    # --------------------------------------------------------
    # SERVICE REQUEST TEXT AREA
    # --------------------------------------------------------

    typed_request = st.text_area(
        "📝 Service request",
        value=st.session_state[
            "typed_service_request"
        ],
        key="service_request_box",
        placeholder=(
            "Example: I want to apply for a "
            "birth certificate..."
        ),
        height=120
    )

    # Keep the latest typed text in session state.
    st.session_state[
        "typed_service_request"
    ] = typed_request

    # --------------------------------------------------------
    # IDENTIFY SERVICE
    # --------------------------------------------------------

    if st.button(
        "🔍 Identify Service",
        type="primary",
        use_container_width=True,
        key="identify_service_button"
    ):

        if not typed_request.strip():

            st.warning(
                "Please describe the government service first."
            )

        else:

            with st.spinner(
                "AI is identifying the service..."
            ):

                result = identify_service(
                    typed_request.strip(),
                    language
                )

            if result["success"]:

                # ====================================================
                # IMPORTANT FIX
                #
                # These values are saved BEFORE rerun.
                # Therefore the identified service survives
                # Streamlit's rerun.
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
                    "requirements"
                ] = None

                st.session_state[
                    "timeline"
                ] = None

                st.session_state[
                    "submission_result"
                ] = None

                st.rerun()

            else:

                st.error(
                    result["error"]
                )

    # ========================================================
    # IMPORTANT FIX
    #
    # This entire section is OUTSIDE the Identify button.
    #
    # Therefore after Streamlit reruns, the identified service
    # remains visible and the application decision appears.
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

                st.markdown(
                    f"""
                    **Department**

                    {service.get(
                        "department",
                        "Unknown"
                    )}

                    **Confidence**

                    {float(
                        service.get(
                            "confidence",
                            0
                        )
                    ) * 100:.0f}%

                    **Intent**

                    {service.get(
                        "intent",
                        "Unknown"
                    )}
                    """
                )

            explanation = service.get(
                "explanation",
                ""
            )

            if explanation:

                st.info(
                    explanation
                )

            # ====================================================
            # APPLICATION DECISION
            # ====================================================

            st.divider()

            st.subheader(
                "Would you like NextStep AI to apply for this service?"
            )

            st.write(
                "Choose what you want NextStep AI to do next."
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "✅ Yes, apply for me",
                    use_container_width=True,
                    type="primary",
                    key="yes_apply_button"
                ):

                    st.session_state[
                        "application_decision"
                    ] = "yes"

                    st.rerun()

            with col2:

                if st.button(
                    "📋 No, show requirements only",
                    use_container_width=True,
                    key="requirements_only_button"
                ):

                    st.session_state[
                        "application_decision"
                    ] = "no"

                    st.rerun()

            # ====================================================
            # REQUIREMENTS ONLY
            # ====================================================

            if st.session_state.get(
                "application_decision"
            ) == "no":

                if st.session_state.get(
                    "requirements"
                ) is None:

                    with st.spinner(
                        "Preparing service requirements..."
                    ):

                        req_result = generate_requirements(
                            service,
                            language
                        )

                    if req_result["success"]:

                        st.session_state[
                            "requirements"
                        ] = req_result

                    else:

                        st.error(
                            req_result["error"]
                        )

                display_requirements(
                    st.session_state.get(
                        "requirements"
                    )
                )

                st.info(
                    "No application information was collected."
                )

            # ====================================================
            # APPLICATION PROCESS
            # ====================================================

            if st.session_state.get(
                "application_decision"
            ) == "yes":

                st.success(
                    "Application mode activated. "
                    "Please complete the information below."
                )

                st.info(
                    "Only provide information required for "
                    "the application. Your data should be "
                    "submitted only through an authorized "
                    "government integration."
                )

                # Generate requirements first.

                if st.session_state.get(
                    "requirements"
                ) is None:

                    with st.spinner(
                        "Preparing application requirements..."
                    ):

                        req_result = generate_requirements(
                            service,
                            language
                        )

                    if req_result["success"]:

                        st.session_state[
                            "requirements"
                        ] = req_result

                    else:

                        st.error(
                            req_result["error"]
                        )

                display_requirements(
                    st.session_state.get(
                        "requirements"
                    )
                )

                st.markdown(
                    """
                    ### Next step

                    Go to the **📝 Application** tab
                    to enter the applicant information.
                    """
                )


# ============================================================
# APPLICATION TAB
# ============================================================

with tab_application:

    st.header("📝 Application")

    # ========================================================
    # FIX:
    # Application tab is controlled by persistent session state.
    # ========================================================

    if st.session_state.get(
        "application_decision"
    ) != "yes":

        st.info(
            "First identify a service and choose "
            "**Yes, apply for me** in the Assistant tab."
        )

    else:

        service = st.session_state.get(
            "identified_service"
        )

        if not service:

            st.warning(
                "No service has been selected yet."
            )

        else:

            st.success(
                f"Preparing application for: "
                f"{service.get('service_name', 'Unknown')}"
            )

            st.divider()

            st.subheader(
                "👤 Applicant Information"
            )

            with st.form(
                "application_form"
            ):

                applicant_name = st.text_input(
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
                    "Additional Information",
                    placeholder=(
                        "Enter any other information "
                        "relevant to this service."
                    )
                )

                st.subheader(
                    "🌐 Official Service Website"
                )

                official_url = st.text_input(
                    "Official government service URL",
                    value=st.session_state.get(
                        "official_url",
                        ""
                    ),
                    placeholder=(
                        "https://example.gov.in/..."
                    )
                )

                st.caption(
                    "This is used to verify the official "
                    "processing timeline when possible."
                )

                authorization = st.checkbox(
                    "I authorize NextStep AI to submit this application "
                    "through an authorized government integration when configured."
                )

                submit_button = st.form_submit_button(
                    "🚀 Submit Application",
                    type="primary",
                    use_container_width=True
                )

            if submit_button:

                # ------------------------------------------------
                # VALIDATION
                # ------------------------------------------------

                errors = []

                if not applicant_name.strip():

                    errors.append(
                        "Full name is required."
                    )

                if not phone.strip():

                    errors.append(
                        "Phone number is required."
                    )

                if not address.strip():

                    errors.append(
                        "Address is required."
                    )

                if not authorization:

                    errors.append(
                        "You must provide authorization "
                        "before submitting."
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

                    # ------------------------------------------------
                    # VERIFY TIMELINE
                    # ------------------------------------------------

                    timeline = None

                    if official_url.strip():

                        with st.spinner(
                            "Verifying official processing timeline..."
                        ):

                            timeline = verify_timeline(
                                official_url.strip(),
                                service.get(
                                    "service_name",
                                    "Unknown"
                                )
                            )

                        if not timeline["success"]:

                            st.warning(
                                timeline["error"]
                            )

                        elif timeline.get(
                            "verified",
                            False
                        ):

                            st.success(
                                "Official processing timeline verified."
                            )

                            st.session_state[
                                "timeline"
                            ] = timeline

                        else:

                            st.warning(
                                "The official website did not provide "
                                "a clearly verifiable processing timeline."
                            )

                    # ------------------------------------------------
                    # TIMELINE VALUES
                    # ------------------------------------------------

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
                        processing_type = "calendar_days"
                        timeline_source = ""
                        timeline_verified = 0

                    # ------------------------------------------------
                    # SUBMISSION DATE
                    # ------------------------------------------------

                    submission_date = date.today()

                    expected_date = (
                        calculate_expected_completion(
                            submission_date,
                            processing_days,
                            processing_type
                        )
                    )

                    # ------------------------------------------------
                    # APPLICATION PAYLOAD
                    # ------------------------------------------------

                    application_payload = {

                        "service": {
                            "name": service.get(
                                "service_name",
                                ""
                            ),
                            "category": service.get(
                                "service_category",
                                ""
                            ),
                            "jurisdiction": service.get(
                                "jurisdiction",
                                ""
                            ),
                            "department": service.get(
                                "department",
                                ""
                            )
                        },

                        "applicant": {
                            "full_name": applicant_name.strip(),
                            "phone": phone.strip(),
                            "email": email.strip(),
                            "address": address.strip(),
                            "additional_information": (
                                additional_information.strip()
                            )
                        },

                        "official_service_url": (
                            official_url.strip()
                        ),

                        "submitted_at": (
                            submission_date.isoformat()
                        )
                    }

                    # ------------------------------------------------
                    # SUBMIT
                    # ------------------------------------------------

                    with st.spinner(
                        "Submitting application..."
                    ):

                        submission = submit_application(
                            application_payload
                        )

                    if not submission["success"]:

                        st.error(
                            submission["error"]
                        )

                    else:

                        application_id = (
                            submission[
                                "application_id"
                            ]
                        )

                        status = submission.get(
                            "status",
                            "Submitted"
                        )

                        now = datetime.now().isoformat()

                        application_record = {

                            "application_id": application_id,

                            "service_name": service.get(
                                "service_name",
                                ""
                            ),

                            "category": service.get(
                                "service_category",
                                ""
                            ),

                            "jurisdiction": service.get(
                                "jurisdiction",
                                ""
                            ),

                            "department": service.get(
                                "department",
                                ""
                            ),

                            "applicant_name": applicant_name.strip(),

                            "phone": phone.strip(),

                            "email": email.strip(),

                            "address": address.strip(),

                            "additional_information": (
                                additional_information.strip()
                            ),

                            "official_url": (
                                official_url.strip()
                            ),

                            "submission_date": (
                                submission_date.isoformat()
                            ),

                            "status": status,

                            "processing_days": processing_days,

                            "processing_type": processing_type,

                            "expected_completion_date": (
                                expected_date.isoformat()
                                if expected_date
                                else None
                            ),

                            "timeline_source": timeline_source,

                            "timeline_verified": (
                                timeline_verified
                            ),

                            "created_at": now,

                            "updated_at": now
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
                            ] = submission

                            st.success(
                                "🎉 Application process completed."
                            )

                            st.markdown(
                                f"""
                                ### 🆔 Application ID

                                ## `{application_id}`
                                """
                            )

                            if submission.get(
                                "real_submission",
                                False
                            ):

                                st.success(
                                    "This application was sent "
                                    "through the configured "
                                    "government integration."
                                )

                            else:

                                st.warning(
                                    "⚠️ Demo/local mode: this is "
                                    "not a real government submission. "
                                    "Configure an authorized government "
                                    "backend/API for real submission."
                                )

                            st.write(
                                f"**Status:** {status}"
                            )

                            if expected_date:

                                st.write(
                                    "**Expected completion:** "
                                    f"{format_date(expected_date)}"
                                )

                            else:

                                st.info(
                                    "No verified official processing "
                                    "timeline was available."
                                )

                            st.info(
                                "Go to **🔎 Track Status** to monitor "
                                "this application."
                            )

                        except Exception as e:

                            st.error(
                                f"Could not save application: {str(e)}"
                            )


# ============================================================
# TRACK STATUS TAB
# ============================================================

with tab_tracking:

    st.header("🔎 Track Application")

    default_id = st.session_state.get(
        "application_id",
        ""
    )

    application_id_input = st.text_input(
        "Application ID",
        value=default_id,
        placeholder="Example: NS-20260925-AB12CD34"
    )

    if st.button(
        "🔎 Check Status",
        type="primary",
        use_container_width=True
    ):

        if not application_id_input.strip():

            st.warning(
                "Please enter an application ID."
            )

        else:

            with st.spinner(
                "Checking application status..."
            ):

                status_result = fetch_status(
                    application_id_input.strip()
                )

            if not status_result["success"]:

                st.error(
                    status_result["error"]
                )

            else:

                application = get_application(
                    application_id_input.strip()
                )

                st.subheader(
                    "📌 Application Status"
                )

                st.success(
                    status_result.get(
                        "status",
                        "Status unavailable"
                    )
                )

                if status_result.get(
                    "message"
                ):

                    st.info(
                        status_result["message"]
                    )

                if application:

                    st.divider()

                    col1, col2 = st.columns(2)

                    with col1:

                        st.markdown(
                            f"""
                            **Application ID**

                            `{application["application_id"]}`

                            **Service**

                            {application["service_name"]}

                            **Jurisdiction**

                            {application["jurisdiction"]}

                            **Department**

                            {application["department"]}
                            """
                        )

                    with col2:

                        st.markdown(
                            f"""
                            **Submitted**

                            {format_date(
                                application["submission_date"]
                            )}

                            **Processing timeline**

                            {
                                (
                                    str(application["processing_days"])
                                    + " "
                                    + application["processing_type"]
                                )
                                if application["processing_days"]
                                else
                                "Not verified"
                            }
                            """
                        )

                    # ------------------------------------------------
                    # DYNAMIC COUNTDOWN
                    # ------------------------------------------------

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

                        expected = (
                            application[
                                "expected_completion_date"
                            ]
                        )

                        st.divider()

                        if remaining is not None:

                            if remaining > 0:

                                st.metric(
                                    "⏳ Estimated Time Remaining",
                                    f"{remaining} day(s)"
                                )

                            else:

                                st.warning(
                                    "The estimated processing "
                                    "timeline has been reached."
                                )

                        if expected:

                            st.write(
                                "**Expected completion date:** "
                                f"{format_date(expected)}"
                            )

                        if application[
                            "timeline_verified"
                        ]:

                            st.success(
                                "Processing timeline was verified "
                                "from the provided official website."
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
                                "No official processing timeline "
                                "was verified for this application."
                            )

                    else:

                        st.info(
                            "A countdown cannot be calculated because "
                            "an official processing timeline was not verified."
                        )


# ============================================================
# VOICE RESPONSE SECTION
# ============================================================

st.divider()

st.subheader("🔊 Voice Assistant")

st.write(
    "You can have the latest NextStep AI response "
    "read aloud."
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

            tts_result = text_to_speech(
                st.session_state[
                    "last_ai_response"
                ],
                language
            )

        if tts_result["success"]:

            st.audio(
                tts_result["audio"],
                format="audio/wav"
            )

        else:

            st.warning(
                tts_result["error"]
            )

else:

    st.caption(
        "Voice output will appear when an AI response "
        "is available."
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div style="text-align:center; padding:25px; color:#777;">
        🤖 <b>NextStep AI</b><br>
        Discover • Prepare • Submit • Track
    </div>
    """,
    unsafe_allow_html=True
)
