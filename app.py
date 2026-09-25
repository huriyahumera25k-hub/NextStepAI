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

OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)

DEFAULT_MODEL = "openai/gpt-4o-mini"

SARVAM_STT_URL = (
    "https://api.sarvam.ai/speech-to-text"
)

SARVAM_TTS_URL = (
    "https://api.sarvam.ai/text-to-speech"
)

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


# TTS currently available through Sarvam Bulbul v3
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
# SECRET HELPER
# ============================================================

def get_secret(name, default=None):

    try:

        if name in st.secrets:

            value = st.secrets[name]

            if value is not None:
                return str(value)

    except Exception:
        pass

    return os.getenv(
        name,
        default
    )


# ============================================================
# API KEYS
# ============================================================

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

HOLIDAYS_CONFIG = get_secret(
    "HOLIDAYS",
    "[]"
)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {

    "language": "English",

    "messages": [],

    "selected_service": None,

    "requirements": [],

    "timeline_result": None,

    "application_decision": None,

    "applicant_data": {},

    "last_application_id": "",

    "last_voice_text": "",

    "last_ai_response": "",

    "service_url": ""
}


for key, value in defaults.items():

    if key not in st.session_state:

        st.session_state[key] = value


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    return sqlite3.connect(
        DATABASE_FILE,
        check_same_thread=False
    )


def init_database():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            application_id TEXT UNIQUE,

            service_name TEXT,

            service_category TEXT,

            jurisdiction TEXT,

            department TEXT,

            applicant_name TEXT,

            applicant_data TEXT,

            status TEXT,

            submission_date TEXT,

            official_processing_days INTEGER,

            timeline_type TEXT,

            expected_completion_date TEXT,

            official_source TEXT,

            government_reference TEXT,

            created_at TEXT,

            updated_at TEXT
        )
        """
    )

    connection.commit()

    connection.close()


init_database()


# ============================================================
# DATABASE SAVE
# ============================================================

def save_application(application):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO applications (

            application_id,
            service_name,
            service_category,
            jurisdiction,
            department,
            applicant_name,
            applicant_data,
            status,
            submission_date,
            official_processing_days,
            timeline_type,
            expected_completion_date,
            official_source,
            government_reference,
            created_at,
            updated_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,

        (
            application["application_id"],

            application.get(
                "service_name",
                ""
            ),

            application.get(
                "service_category",
                ""
            ),

            application.get(
                "jurisdiction",
                ""
            ),

            application.get(
                "department",
                ""
            ),

            application.get(
                "applicant_name",
                ""
            ),

            json.dumps(
                application.get(
                    "applicant_data",
                    {}
                )
            ),

            application.get(
                "status",
                "Application Submitted"
            ),

            application.get(
                "submission_date",
                ""
            ),

            application.get(
                "official_processing_days",
                0
            ),

            application.get(
                "timeline_type",
                "unknown"
            ),

            application.get(
                "expected_completion_date",
                ""
            ),

            application.get(
                "official_source",
                ""
            ),

            application.get(
                "government_reference",
                ""
            ),

            application.get(
                "created_at",
                datetime.now().isoformat()
            ),

            application.get(
                "updated_at",
                datetime.now().isoformat()
            )
        )
    )

    connection.commit()

    connection.close()


# ============================================================
# DATABASE LOAD
# ============================================================

def load_application(application_id):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT

            application_id,
            service_name,
            service_category,
            jurisdiction,
            department,
            applicant_name,
            applicant_data,
            status,
            submission_date,
            official_processing_days,
            timeline_type,
            expected_completion_date,
            official_source,
            government_reference,
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

    connection.close()

    if not row:
        return None

    try:

        applicant_data = json.loads(
            row[6] or "{}"
        )

    except Exception:

        applicant_data = {}

    return {

        "application_id": row[0],

        "service_name": row[1],

        "service_category": row[2],

        "jurisdiction": row[3],

        "department": row[4],

        "applicant_name": row[5],

        "applicant_data": applicant_data,

        "status": row[7],

        "submission_date": row[8],

        "official_processing_days": row[9],

        "timeline_type": row[10],

        "expected_completion_date": row[11],

        "official_source": row[12],

        "government_reference": row[13],

        "created_at": row[14],

        "updated_at": row[15]
    }


# ============================================================
# DATABASE UPDATE
# ============================================================

def update_application(
    application_id,
    **updates
):

    allowed = {

        "status",

        "government_reference",

        "expected_completion_date",

        "official_processing_days",

        "timeline_type",

        "official_source"
    }

    fields = []

    values = []

    for field, value in updates.items():

        if field not in allowed:
            continue

        fields.append(
            f"{field} = ?"
        )

        values.append(
            value
        )

    if not fields:
        return

    fields.append(
        "updated_at = ?"
    )

    values.append(
        datetime.now().isoformat()
    )

    values.append(
        application_id
    )

    connection = get_connection()

    cursor = connection.cursor()

    query = f"""
        UPDATE applications
        SET {", ".join(fields)}
        WHERE application_id = ?
    """

    cursor.execute(
        query,
        values
    )

    connection.commit()

    connection.close()


# ============================================================
# DATE HELPERS
# ============================================================

def parse_date(value):

    if isinstance(value, date):
        return value

    if not value:
        return None

    try:

        return datetime.strptime(
            str(value)[:10],
            "%Y-%m-%d"
        ).date()

    except Exception:

        return None


def get_holidays():

    try:

        values = json.loads(
            str(HOLIDAYS_CONFIG)
        )

        result = set()

        for value in values:

            parsed = parse_date(
                value
            )

            if parsed:
                result.add(parsed)

        return result

    except Exception:

        return set()


def is_working_day(day):

    if day.weekday() >= 5:
        return False

    if day in get_holidays():
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

        if is_working_day(current):

            count += 1

    return current


def count_working_days(
    start_date,
    end_date
):

    if end_date <= start_date:
        return 0

    current = start_date

    count = 0

    while current < end_date:

        current += timedelta(
            days=1
        )

        if is_working_day(current):

            count += 1

    return count


def calculate_remaining_days(
    submission_date,
    processing_days,
    timeline_type
):

    submitted = parse_date(
        submission_date
    )

    if not submitted:
        return None

    if not processing_days:
        return None

    today = date.today()

    processing_days = int(
        processing_days
    )

    if timeline_type == "calendar_days":

        deadline = (
            submitted
            + timedelta(
                days=processing_days
            )
        )

        if today >= deadline:
            return 0

        return (
            deadline - today
        ).days

    deadline = add_working_days(
        submitted,
        processing_days
    )

    if today >= deadline:
        return 0

    return count_working_days(
        today,
        deadline
    )


# ============================================================
# URL HELPERS
# ============================================================

def valid_url(url):

    if not url:
        return False

    try:

        parsed = urlparse(
            url
        )

        return (
            parsed.scheme in [
                "http",
                "https"
            ]
            and bool(
                parsed.netloc
            )
        )

    except Exception:

        return False


def official_domain(url):

    if not valid_url(url):
        return False

    try:

        hostname = urlparse(
            url
        ).hostname

        if not hostname:
            return False

        hostname = hostname.lower()

    except Exception:

        return False

    return (
        hostname.endswith(".gov.in")
        or hostname.endswith(".gov")
        or hostname.endswith(".nic.in")
        or hostname.endswith(".ac.in")
        or hostname.endswith(".org.in")
    )


# ============================================================
# OPENROUTER AI
# ============================================================

def call_ai(
    messages,
    temperature=0.2,
    max_tokens=1800
):

    if not OPENROUTER_API_KEY:

        return {

            "success": False,

            "error":
                "OpenRouter API key is not configured."
        }

    headers = {

        "Authorization":
            f"Bearer {OPENROUTER_API_KEY}",

        "Content-Type":
            "application/json",

        "HTTP-Referer":
            "https://nextstep-ai.streamlit.app",

        "X-Title":
            "NextStep AI"
    }

    payload = {

        "model":
            OPENROUTER_MODEL,

        "messages":
            messages,

        "temperature":
            temperature,

        "max_tokens":
            max_tokens
    }

    try:

        response = requests.post(

            OPENROUTER_URL,

            headers=headers,

            json=payload,

            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        choices = data.get(
            "choices",
            []
        )

        if not choices:

            return {

                "success": False,

                "error":
                    "The AI returned no response."
            }

        content = (
            choices[0]
            .get("message", {})
            .get("content", "")
        )

        if not content:

            return {

                "success": False,

                "error":
                    "The AI returned an empty response."
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

    except requests.exceptions.HTTPError:

        try:

            detail = response.text[:600]

        except Exception:

            detail = ""

        return {

            "success": False,

            "error":
                f"AI service error. {detail}"
        }

    except requests.exceptions.RequestException as error:

        return {

            "success": False,

            "error":
                f"Network error: {error}"
        }

    except Exception as error:

        return {

            "success": False,

            "error":
                f"Unexpected AI error: {error}"
        }


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):

    if not text:
        return None

    cleaned = text.strip()

    cleaned = re.sub(
        r"```json",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = cleaned.replace(
        "```",
        ""
    ).strip()

    try:

        return json.loads(
            cleaned
        )

    except Exception:
        pass

    match = re.search(
        r"\{.*\}",
        cleaned,
        flags=re.DOTALL
    )

    if match:

        try:

            return json.loads(
                match.group(0)
            )

        except Exception:

            return None

    return None


# ============================================================
# SARVAM SPEECH TO TEXT
# ============================================================

def speech_to_text(
    audio_file,
    language
):

    if not SARVAM_API_KEY:

        return {

            "success": False,

            "error":
                "Sarvam API key is not configured."
        }

    language_code = LANGUAGE_CODES.get(
        language,
        "en-IN"
    )

    try:

        audio_bytes = audio_file.getvalue()

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

        headers = {

            "api-subscription-key":
                SARVAM_API_KEY
        }

        response = requests.post(

            SARVAM_STT_URL,

            headers=headers,

            files=files,

            data=data,

            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        result = response.json()

        transcript = result.get(
            "transcript",
            ""
        )

        if not transcript:

            return {

                "success": False,

                "error":
                    "No speech was detected."
            }

        return {

            "success": True,

            "text": transcript,

            "language_code":
                result.get(
                    "language_code",
                    language_code
                )
        }

    except requests.exceptions.RequestException as error:

        return {

            "success": False,

            "error":
                f"Voice API error: {error}"
        }

    except Exception as error:

        return {

            "success": False,

            "error":
                f"Voice processing error: {error}"
        }


# ============================================================
# SARVAM TEXT TO SPEECH
# ============================================================

def text_to_speech(
    text,
    language
):

    if not SARVAM_API_KEY:
        return None

    if language not in TTS_SUPPORTED:
        return None

    if not text:
        return None

    language_code = LANGUAGE_CODES.get(
        language,
        "en-IN"
    )

    # Sarvam Bulbul v3 supports up to 2500 characters
    text = text[:2400]

    headers = {

        "api-subscription-key":
            SARVAM_API_KEY,

        "Content-Type":
            "application/json"
    }

    payload = {

        "text":
            text,

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

        response.raise_for_status()

        result = response.json()

        audios = result.get(
            "audios",
            []
        )

        if not audios:
            return None

        return base64.b64decode(
            audios[0]
        )

    except Exception:

        return None


# ============================================================
# AI SERVICE IDENTIFICATION
# ============================================================

def identify_service(
    user_text,
    language
):

    system_prompt = f"""
You are the service-identification engine of NextStep AI.

The user wants help with a government or public service.

User language:
{language}

Identify the requested service.

Do not invent a government service.

Return ONLY valid JSON.

Schema:

{{
    "service_name": "",
    "service_category": "",
    "jurisdiction": "",
    "department": "",
    "intent": "",
    "confidence": 0,
    "explanation": ""
}}
"""

    result = call_ai(
        [
            {
                "role":
                    "system",

                "content":
                    system_prompt
            },

            {
                "role":
                    "user",

                "content":
                    user_text
            }
        ]
    )

    if not result["success"]:
        return result

    data = extract_json(
        result["content"]
    )

    if not isinstance(
        data,
        dict
    ):

        return {

            "success": False,

            "error":
                "The AI returned invalid service data."
        }

    return {

        "success": True,

        "data":
            data
    }


# ============================================================
# REQUIREMENT DISCOVERY
# ============================================================

def generate_requirements(
    service_name,
    jurisdiction,
    language
):

    system_prompt = f"""
You are the government-service requirements assistant.

Service:
{service_name}

Jurisdiction:
{jurisdiction}

Language:
{language}

Give the user the likely information and documents
needed for this service.

IMPORTANT:

Do not claim that AI-generated requirements are
official unless verified from an official source.

Return ONLY JSON.

Schema:

{{
    "requirements": [
        {{
            "name": "",
            "type": "document|information|optional",
            "description": "",
            "required": true
        }}
    ],
    "verification_note": ""
}}
"""

    result = call_ai(
        [
            {
                "role":
                    "system",

                "content":
                    system_prompt
            },

            {
                "role":
                    "user",

                "content":
                    "Find the likely requirements."
            }
        ]
    )

    if not result["success"]:
        return result

    data = extract_json(
        result["content"]
    )

    if not isinstance(
        data,
        dict
    ):

        return {

            "success": False,

            "error":
                "Invalid requirements response."
        }

    return {

        "success": True,

        "data":
            data
    }


# ============================================================
# OFFICIAL PAGE READER
# ============================================================

def read_official_page(url):

    if not valid_url(url):

        return {

            "success": False,

            "error":
                "Invalid URL."
        }

    try:

        response = requests.get(

            url,

            timeout=REQUEST_TIMEOUT,

            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "(compatible; NextStepAI/1.0)"
            }
        )

        response.raise_for_status()

        html = response.text

        html = re.sub(
            r"<script.*?</script>",
            " ",
            html,
            flags=re.DOTALL |
            re.IGNORECASE
        )

        html = re.sub(
            r"<style.*?</style>",
            " ",
            html,
            flags=re.DOTALL |
            re.IGNORECASE
        )

        text = re.sub(
            r"<[^>]+>",
            " ",
            html
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        ).strip()

        return {

            "success": True,

            "text":
                text[:18000]
        }

    except Exception as error:

        return {

            "success": False,

            "error":
                f"Unable to read official page: {error}"
        }


# ============================================================
# TIMELINE VERIFICATION
# ============================================================

def verify_timeline(
    service_name,
    jurisdiction,
    url,
    language
):

    if not official_domain(url):

        return {

            "success": False,

            "verified": False,

            "error":
                "Please use an official government URL."
        }

    page = read_official_page(
        url
    )

    if not page["success"]:
        return page

    system_prompt = """
You verify official government processing timelines.

Use ONLY the supplied official webpage.

Do not guess.

Return ONLY JSON.

Schema:

{
    "processing_days": null,
    "timeline_type": "working_days|calendar_days|unknown",
    "department": "",
    "notes": ""
}
"""

    user_prompt = f"""
Service:
{service_name}

Jurisdiction:
{jurisdiction}

Official webpage:
{page["text"]}

Language:
{language}
"""

    result = call_ai(
        [
            {
                "role":
                    "system",

                "content":
                    system_prompt
            },

            {
                "role":
                    "user",

                "content":
                    user_prompt
            }
        ],
        max_tokens=1200
    )

    if not result["success"]:
        return result

    data = extract_json(
        result["content"]
    )

    if not isinstance(
        data,
        dict
    ):

        return {

            "success": False,

            "verified": False,

            "error":
                "Could not interpret official information."
        }

    try:

        processing_days = int(
            data.get(
                "processing_days"
            )
        )

    except Exception:

        processing_days = None

    if not processing_days:

        return {

            "success": True,

            "verified": False,

            "data":
                data
        }

    return {

        "success": True,

        "verified": True,

        "processing_days":
            processing_days,

        "timeline_type":
            data.get(
                "timeline_type",
                "unknown"
            ),

        "data":
            data
    }


# ============================================================
# APPLICATION ID
# ============================================================

def create_application_id():

    return (

        "NS-"

        + datetime.now().strftime(
            "%Y%m%d"
        )

        + "-"

        + uuid.uuid4()
        .hex[:8]
        .upper()
    )


# ============================================================
# GOVERNMENT SUBMISSION
# ============================================================

def submit_application(
    application
):

    # --------------------------------------------------------
    # REAL GOVERNMENT API
    # --------------------------------------------------------

    if GOVERNMENT_SUBMISSION_URL:

        payload = {

            "service_name":
                application[
                    "service_name"
                ],

            "service_category":
                application.get(
                    "service_category",
                    ""
                ),

            "jurisdiction":
                application[
                    "jurisdiction"
                ],

            "department":
                application.get(
                    "department",
                    ""
                ),

            "applicant":
                application[
                    "applicant_data"
                ],

            "submission_date":
                application[
                    "submission_date"
                ]
        }

        try:

            response = requests.post(

                GOVERNMENT_SUBMISSION_URL,

                json=payload,

                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            government_id = (

                data.get(
                    "application_id"
                )

                or data.get(
                    "applicationId"
                )

                or data.get(
                    "id"
                )
            )

            if not government_id:

                return {

                    "success": False,

                    "error":
                        "Government API did not return an application ID."
                }

            return {

                "success": True,

                "application_id":
                    str(
                        government_id
                    ),

                "status":
                    data.get(
                        "status",
                        "Submitted"
                    ),

                "government_reference":
                    str(
                        data.get(
                            "reference",
                            ""
                        )
                    )
            }

        except Exception as error:

            return {

                "success": False,

                "error":
                    f"Government submission failed: {error}"
            }

    # --------------------------------------------------------
    # LOCAL FUNCTIONAL MODE
    # --------------------------------------------------------

    return {

        "success": True,

        "application_id":
            create_application_id(),

        "status":
            "Application Submitted",

        "government_reference":
            ""
    }


# ============================================================
# GOVERNMENT STATUS
# ============================================================

def fetch_status(application):

    if not GOVERNMENT_STATUS_URL:

        return {

            "success": True,

            "status":
                application.get(
                    "status",
                    "Application Submitted"
                )
        }

    try:

        response = requests.post(

            GOVERNMENT_STATUS_URL,

            json={

                "application_id":
                    application[
                        "application_id"
                    ],

                "government_reference":
                    application.get(
                        "government_reference",
                        ""
                    )
            },

            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        return {

            "success": True,

            "status":
                data.get(
                    "status",
                    "Processing"
                )
        }

    except Exception:

        return {

            "success": True,

            "status":
                application.get(
                    "status",
                    "Application Submitted"
                )
        }


# ============================================================
# SPEAK RESPONSE
# ============================================================

def speak_response(text):

    if not text:
        return

    if not SARVAM_API_KEY:
        return

    if st.session_state.language not in TTS_SUPPORTED:

        st.info(
            "Voice output is not currently available "
            "for this selected language."
        )

        return

    with st.spinner(
        "Generating voice response..."
    ):

        audio = text_to_speech(
            text,
            st.session_state.language
        )

    if audio:

        st.audio(
            audio,
            format="audio/wav",
            autoplay=False
        )


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #f7f9fc;
    }

    section[data-testid="stSidebar"] {
        background-color: #111827;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title(
        "🤖 NextStep AI"
    )

    st.caption(
        "Government services assistant"
    )

    st.divider()

    selected_language = st.selectbox(

        "🌐 Select language",

        list(
            LANGUAGE_CODES.keys()
        ),

        index=list(
            LANGUAGE_CODES.keys()
        ).index(
            st.session_state.language
        ),

        key="language_selector"
    )

    st.session_state.language = (
        selected_language
    )

    st.divider()

    st.subheader(
        "Connected services"
    )

    if OPENROUTER_API_KEY:

        st.success(
            "AI: Connected"
        )

    else:

        st.error(
            "AI: API key missing"
        )

    if SARVAM_API_KEY:

        st.success(
            "Voice: Connected"
        )

    else:

        st.warning(
            "Voice: API key missing"
        )

    st.divider()

    st.caption(
        f"Selected language: "
        f"{st.session_state.language}"
    )


# ============================================================
# MAIN HEADER
# ============================================================

st.title(
    "🤖 NextStep AI"
)

st.subheader(
    "One assistant for government services"
)

st.write(
    "Describe the service you need by typing or speaking. "
    "NextStep AI identifies the service first, then asks "
    "whether you want to apply."
)

st.divider()


# ============================================================
# MAIN TABS
# ============================================================

assistant_tab, application_tab, tracking_tab = st.tabs(
    [
        "🤖 Assistant",
        "📝 Application",
        "📊 Track Status"
    ]
)


# ============================================================
# ASSISTANT
# ============================================================

with assistant_tab:

    st.header(
        "What government service do you need?"
    )

    st.write(
        "You can type your request or use the microphone."
    )

    # --------------------------------------------------------
    # VOICE INPUT
    # --------------------------------------------------------

    voice_col, text_col = st.columns(
        [1, 1]
    )

    with voice_col:

        st.subheader(
            "🎙️ Voice input"
        )

        audio_input = st.audio_input(
            "Speak your request",
            sample_rate=16000,
            key="service_voice_input"
        )

        if audio_input:

            if not SARVAM_API_KEY:

                st.warning(
                    "Add SARVAM_API_KEY to enable voice input."
                )

            else:

                if st.button(
                    "Convert voice to text",
                    key="convert_service_voice"
                ):

                    with st.spinner(
                        "Understanding your voice..."
                    ):

                        voice_result = speech_to_text(

                            audio_input,

                            st.session_state.language
                        )

                    if voice_result["success"]:

                        st.session_state[
                            "last_voice_text"
                        ] = voice_result[
                            "text"
                        ]

                        st.success(
                            "Voice converted successfully."
                        )

                        st.text_area(
                            "Recognized speech",
                            value=voice_result[
                                "text"
                            ],
                            height=100,
                            key="recognized_voice_text"
                        )

                    else:

                        st.error(
                            voice_result[
                                "error"
                            ]
                        )

    # --------------------------------------------------------
    # TEXT INPUT
    # --------------------------------------------------------

    with text_col:

        st.subheader(
            "⌨️ Text input"
        )

        typed_request = st.text_area(

            "Describe the service",

            placeholder=(
                "Example: I need to apply for "
                "a birth certificate"
            ),

            height=150,

            key="typed_service_request"
        )

        use_voice_text = st.button(
            "Use recognized voice",
            key="use_voice_text"
        )

        if use_voice_text:

            if st.session_state.last_voice_text:

                typed_request = (
                    st.session_state.last_voice_text
                )

                st.info(
                    "Voice text loaded. Click "
                    "Identify Service below."
                )

            else:

                st.warning(
                    "Record and convert a voice request first."
                )

    # --------------------------------------------------------
    # SERVICE IDENTIFICATION
    # --------------------------------------------------------

    identify = st.button(
        "🔎 Identify Service",
        type="primary",
        use_container_width=True
    )

    if identify:

        request_text = (
            typed_request.strip()
        )

        if not request_text:

            request_text = (
                st.session_state.last_voice_text.strip()
            )

        if not request_text:

            st.warning(
                "Please type or speak your request."
            )

        else:

            with st.spinner(
                "Identifying the government service..."
            ):

                result = identify_service(

                    request_text,

                    st.session_state.language
                )

            if result["success"]:

                service = result["data"]

                st.session_state.selected_service = (
                    service
                )

                st.session_state.application_decision = (
                    None
                )

                st.session_state.requirements = []

                st.success(
                    "Service identified."
                )

                c1, c2 = st.columns(2)

                with c1:

                    st.write(
                        "**Service**"
                    )

                    st.info(
                        service.get(
                            "service_name",
                            "Unknown"
                        )
                    )

                    st.write(
                        "**Category**"
                    )

                    st.write(
                        service.get(
                            "service_category",
                            "Unknown"
                        )
                    )

                with c2:

                    st.write(
                        "**Jurisdiction**"
                    )

                    st.info(
                        service.get(
                            "jurisdiction",
                            "Unknown"
                        )
                    )

                    st.write(
                        "**Department**"
                    )

                    st.write(
                        service.get(
                            "department",
                            "Unknown"
                        )
                    )

                if service.get(
                    "explanation"
                ):

                    st.write(
                        service[
                            "explanation"
                        ]
                    )

                st.divider()

                # ------------------------------------------------
                # THE IMPORTANT QUESTION
                # ------------------------------------------------

                st.subheader(
                    "Would you like NextStep AI to apply for this service?"
                )

                st.write(
                    "Choose **Yes** if you want help preparing "
                    "the application. Choose **No** if you "
                    "only want to know the required documents."
                )

                yes_col, no_col = st.columns(2)

                with yes_col:

                    if st.button(
                        "✅ Yes, apply for me",
                        use_container_width=True,
                        type="primary",
                        key="apply_yes"
                    ):

                        st.session_state.application_decision = (
                            "yes"
                        )

                        st.rerun()

                with no_col:

                    if st.button(
                        "📄 No, show requirements only",
                        use_container_width=True,
                        key="apply_no"
                    ):

                        st.session_state.application_decision = (
                            "no"
                        )

                        st.rerun()

            else:

                st.error(
                    result.get(
                        "error",
                        "Unable to identify the service."
                    )
                )

    # ========================================================
    # NO APPLICATION
    # ========================================================

    if (
        st.session_state.selected_service
        and
        st.session_state.application_decision == "no"
    ):

        service = (
            st.session_state.selected_service
        )

        st.divider()

        st.subheader(
            "📄 Required documents and information"
        )

        with st.spinner(
            "Finding the likely requirements..."
        ):

            requirements_result = (
                generate_requirements(

                    service.get(
                        "service_name",
                        ""
                    ),

                    service.get(
                        "jurisdiction",
                        ""
                    ),

                    st.session_state.language
                )
            )

        if requirements_result["success"]:

            requirements = (
                requirements_result[
                    "data"
                ].get(
                    "requirements",
                    []
                )
            )

            st.session_state.requirements = (
                requirements
            )

            if requirements:

                for index, requirement in enumerate(
                    requirements,
                    start=1
                ):

                    required_text = (
                        "Required"
                        if requirement.get(
                            "required",
                            False
                        )
                        else "Optional"
                    )

                    st.write(
                        f"**{index}. "
                        f"{requirement.get(
                            'name',
                            'Requirement'
                        )}**"
                    )

                    st.caption(
                        f"{required_text} • "
                        f"{requirement.get(
                            'description',
                            ''
                        )}"
                    )

            else:

                st.info(
                    "No requirements were returned."
                )

            st.warning(
                requirements_result[
                    "data"
                ].get(
                    "verification_note",
                    "Verify requirements on the official government website."
                )
            )

        else:

            st.error(
                requirements_result.get(
                    "error",
                    "Unable to retrieve requirements."
                )
            )


# ============================================================
# APPLICATION TAB
# ============================================================

with application_tab:

    st.header(
        "📝 Application"
    )

    service = (
        st.session_state.selected_service
    )

    if not service:

        st.info(
            "Identify a government service first."
        )

    elif st.session_state.application_decision != "yes":

        st.info(
            "Choose **Yes, apply for me** in the Assistant "
            "before filling an application."
        )

    else:

        st.success(
            "Application mode enabled."
        )

        st.subheader(
            service.get(
                "service_name",
                "Government Service"
            )
        )

        st.write(
            f"Jurisdiction: "
            f"**{service.get('jurisdiction', 'Unknown')}**"
        )

        st.divider()

        # ----------------------------------------------------
        # APPLICANT INFORMATION
        # ----------------------------------------------------

        st.subheader(
            "👤 Applicant information"
        )

        full_name = st.text_input(
            "Full name",
            key="application_full_name"
        )

        phone = st.text_input(
            "Phone number",
            key="application_phone"
        )

        email = st.text_input(
            "Email address",
            key="application_email"
        )

        address = st.text_area(
            "Address",
            key="application_address"
        )

        extra_information = st.text_area(
            "Additional information",
            key="application_extra"
        )

        # ----------------------------------------------------
        # OFFICIAL URL
        # ----------------------------------------------------

        st.subheader(
            "🏛️ Official service information"
        )

        st.write(
            "Add the official service webpage if available. "
            "NextStep AI can read the page and look for an "
            "explicitly published processing timeline."
        )

        official_url = st.text_input(
            "Official government service URL",
            key="official_service_url",
            placeholder="https://..."
        )

        verify_timeline_button = st.button(
            "🔎 Verify processing timeline",
            use_container_width=True
        )

        if verify_timeline_button:

            if not official_url:

                st.warning(
                    "Enter the official service URL first."
                )

            elif not valid_url(
                official_url
            ):

                st.error(
                    "Invalid URL."
                )

            elif not official_domain(
                official_url
            ):

                st.warning(
                    "Please use an official government "
                    "or public-sector URL."
                )

            else:

                with st.spinner(
                    "Reading the official service information..."
                ):

                    timeline_result = verify_timeline(

                        service.get(
                            "service_name",
                            ""
                        ),

                        service.get(
                            "jurisdiction",
                            ""
                        ),

                        official_url,

                        st.session_state.language
                    )

                st.session_state.timeline_result = (
                    timeline_result
                )

        timeline = (
            st.session_state.timeline_result
        )

        if timeline:

            if timeline.get(
                "verified"
            ):

                st.success(
                    f"Official processing timeline: "
                    f"{timeline['processing_days']} "
                    f"{timeline['timeline_type'].replace('_', ' ')}"
                )

            else:

                st.info(
                    "No exact processing time could be verified "
                    "from this official webpage."
                )

        st.divider()

        # ----------------------------------------------------
        # REVIEW
        # ----------------------------------------------------

        st.subheader(
            "🔐 Review before submission"
        )

        st.write(
            f"**Name:** {full_name}"
        )

        st.write(
            f"**Phone:** {phone}"
        )

        st.write(
            f"**Email:** {email}"
        )

        st.write(
            f"**Address:** {address}"
        )

        st.write(
            f"**Additional information:** "
            f"{extra_information}"
        )

        authorization = st.checkbox(
            "I have reviewed the information and authorize NextStep AI to submit this application."
        )

        submit_button = st.button(
            "🚀 Submit Application",
            type="primary",
            use_container_width=True
        )

        if submit_button:

            errors = []

            if not full_name.strip():

                errors.append(
                    "Full name is required."
                )

            if not phone.strip():

                errors.append(
                    "Phone number is required."
                )

            if not email.strip():

                errors.append(
                    "Email address is required."
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

                submission_date = date.today()

                processing_days = 0

                timeline_type = "unknown"

                if timeline:

                    if timeline.get(
                        "verified"
                    ):

                        processing_days = int(
                            timeline[
                                "processing_days"
                            ]
                        )

                        timeline_type = (
                            timeline[
                                "timeline_type"
                            ]
                        )

                expected_completion = ""

                if processing_days:

                    if timeline_type == "calendar_days":

                        deadline = (
                            submission_date
                            + timedelta(
                                days=processing_days
                            )
                        )

                    else:

                        deadline = (
                            add_working_days(
                                submission_date,
                                processing_days
                            )
                        )

                    expected_completion = (
                        deadline.isoformat()
                    )

                application = {

                    "service_name":
                        service.get(
                            "service_name",
                            ""
                        ),

                    "service_category":
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
                        full_name,

                    "applicant_data": {

                        "full_name":
                            full_name,

                        "phone":
                            phone,

                        "email":
                            email,

                        "address":
                            address,

                        "additional_information":
                            extra_information
                    },

                    "submission_date":
                        submission_date.isoformat(),

                    "official_processing_days":
                        processing_days,

                    "timeline_type":
                        timeline_type,

                    "expected_completion_date":
                        expected_completion,

                    "official_source":
                        official_url,

                    "status":
                        "Application Submitted"
                }

                with st.spinner(
                    "Submitting application..."
                ):

                    result = submit_application(
                        application
                    )

                if result["success"]:

                    application[
                        "application_id"
                    ] = result[
                        "application_id"
                    ]

                    application[
                        "status"
                    ] = result.get(
                        "status",
                        "Application Submitted"
                    )

                    application[
                        "government_reference"
                    ] = result.get(
                        "government_reference",
                        ""
                    )

                    application[
                        "created_at"
                    ] = datetime.now().isoformat()

                    application[
                        "updated_at"
                    ] = datetime.now().isoformat()

                    try:

                        save_application(
                            application
                        )

                        st.session_state[
                            "last_application_id"
                        ] = application[
                            "application_id"
                        ]

                        st.success(
                            "Application submitted successfully."
                        )

                        st.subheader(
                            "🆔 Application ID"
                        )

                        st.code(
                            application[
                                "application_id"
                            ]
                        )

                        if expected_completion:

                            st.info(
                                f"Expected completion: "
                                f"**{expected_completion}**"
                            )

                        st.success(
                            "You can now track this application "
                            "from the Track Status tab."
                        )

                    except Exception as error:

                        st.error(
                            f"Application was processed but "
                            f"could not be saved locally: {error}"
                        )

                else:

                    st.error(
                        result.get(
                            "error",
                            "Application submission failed."
                        )
                    )


# ============================================================
# TRACKING
# ============================================================

with tracking_tab:

    st.header(
        "📊 Track application"
    )

    tracking_id = st.text_input(
        "Application ID",
        value=st.session_state.last_application_id,
        placeholder="NS-YYYYMMDD-XXXXXXXX"
    )

    track_button = st.button(
        "🔍 Track",
        type="primary",
        use_container_width=True
    )

    if track_button:

        if not tracking_id.strip():

            st.warning(
                "Enter an application ID."
            )

        else:

            application = load_application(
                tracking_id.strip()
            )

            if not application:

                st.error(
                    "Application not found."
                )

            else:

                status_result = fetch_status(
                    application
                )

                current_status = (
                    status_result.get(
                        "status",
                        application.get(
                            "status",
                            "Processing"
                        )
                    )
                )

                st.success(
                    "Application found."
                )

                c1, c2, c3 = st.columns(3)

                with c1:

                    st.metric(
                        "Status",
                        current_status
                    )

                with c2:

                    st.metric(
                        "Application ID",
                        application[
                            "application_id"
                        ]
                    )

                with c3:

                    st.metric(
                        "Submitted",
                        application[
                            "submission_date"
                        ]
                    )

                processing_days = application.get(
                    "official_processing_days",
                    0
                )

                timeline_type = application.get(
                    "timeline_type",
                    "unknown"
                )

                if processing_days:

                    remaining = (
                        calculate_remaining_days(

                            application[
                                "submission_date"
                            ],

                            processing_days,

                            timeline_type
                        )
                    )

                    submitted = parse_date(
                        application[
                            "submission_date"
                        ]
                    )

                    if timeline_type == "calendar_days":

                        deadline = (
                            submitted
                            + timedelta(
                                days=processing_days
                            )
                        )

                    else:

                        deadline = (
                            add_working_days(

                                submitted,

                                processing_days
                            )
                        )

                    c1, c2, c3 = st.columns(3)

                    with c1:

                        st.metric(
                            "Official timeline",
                            f"{processing_days} days"
                        )

                    with c2:

                        st.metric(
                            "Remaining",
                            f"{remaining} days"
                        )

                    with c3:

                        st.metric(
                            "Expected completion",
                            deadline.strftime(
                                "%d %b %Y"
                            )
                        )

                    completed = (
                        processing_days
                        - remaining
                    )

                    progress = (
                        completed
                        / processing_days
                    )

                    progress = max(
                        0,
                        min(
                            1,
                            progress
                        )
                    )

                    st.progress(
                        progress
                    )

                    if remaining == 0:

                        st.success(
                            "The expected processing period "
                            "has been reached."
                        )

                    else:

                        st.info(
                            f"{remaining} processing days remaining."
                        )

                else:

                    st.info(
                        "No verified processing timeline "
                        "is available."
                    )

                st.divider()

                st.write(
                    f"**Service:** "
                    f"{application['service_name']}"
                )

                st.write(
                    f"**Jurisdiction:** "
                    f"{application['jurisdiction']}"
                )

                st.write(
                    f"**Department:** "
                    f"{application.get('department', 'Unknown')}"
                )

                if application.get(
                    "government_reference"
                ):

                    st.write(
                        f"**Government reference:** "
                        f"{application['government_reference']}"
                    )

                if application.get(
                    "official_source"
                ):

                    st.write(
                        f"**Official source:** "
                        f"{application['official_source']}"
                    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "NextStep AI • Discover • Prepare • Submit • Track"
)
