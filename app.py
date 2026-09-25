import streamlit as st
import requests
import json
import re
import sqlite3
import os
import uuid
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

APP_NAME = "NextStep AI"

DATABASE_FILE = "nextstep_ai.db"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_MODEL = "openai/gpt-4o-mini"

REQUEST_TIMEOUT = 45

SUPPORTED_LANGUAGES = [
    "English",
    "Hindi",
    "Telugu",
    "Tamil",
    "Kannada",
    "Malayalam",
    "Marathi",
    "Bengali",
    "Gujarati",
    "Urdu"
]

DEFAULT_PROCESSING_DAYS = 0


# ============================================================
# SECRET / ENVIRONMENT HELPER
# ============================================================

def get_secret(name, default=None):
    """
    Safely read a Streamlit secret or environment variable.
    """

    try:
        if name in st.secrets:
            value = st.secrets[name]

            if value is not None:
                return str(value)

    except Exception:
        pass

    return os.getenv(name, default)


# ============================================================
# API CONFIGURATION
# ============================================================

OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY")

OPENROUTER_MODEL = get_secret(
    "OPENROUTER_MODEL",
    DEFAULT_MODEL
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

if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_service" not in st.session_state:
    st.session_state.selected_service = None

if "requirements" not in st.session_state:
    st.session_state.requirements = []

if "application_data" not in st.session_state:
    st.session_state.application_data = {}

if "language" not in st.session_state:
    st.session_state.language = "English"

if "ai_result" not in st.session_state:
    st.session_state.ai_result = None


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

            jurisdiction TEXT,

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
# DATABASE FUNCTIONS
# ============================================================

def save_application(application):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO applications (
            application_id,
            service_name,
            jurisdiction,
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

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application["application_id"],
            application["service_name"],
            application["jurisdiction"],
            application["applicant_name"],
            json.dumps(application.get("applicant_data", {})),
            application["status"],
            application["submission_date"],
            application["official_processing_days"],
            application["timeline_type"],
            application["expected_completion_date"],
            application.get("official_source", ""),
            application.get("government_reference", ""),
            application["created_at"],
            application["updated_at"]
        )
    )

    connection.commit()
    connection.close()


def load_application(application_id):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            application_id,
            service_name,
            jurisdiction,
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
        (application_id,)
    )

    row = cursor.fetchone()

    connection.close()

    if not row:
        return None

    return {
        "application_id": row[0],
        "service_name": row[1],
        "jurisdiction": row[2],
        "applicant_name": row[3],
        "applicant_data": json.loads(row[4] or "{}"),
        "status": row[5],
        "submission_date": row[6],
        "official_processing_days": row[7],
        "timeline_type": row[8],
        "expected_completion_date": row[9],
        "official_source": row[10],
        "government_reference": row[11],
        "created_at": row[12],
        "updated_at": row[13]
    }


def update_application(application_id, **updates):

    if not updates:
        return

    connection = get_connection()

    cursor = connection.cursor()

    allowed_fields = {
        "status",
        "government_reference",
        "expected_completion_date",
        "official_processing_days",
        "timeline_type",
        "official_source",
        "updated_at"
    }

    fields = []
    values = []

    for field, value in updates.items():

        if field not in allowed_fields:
            continue

        fields.append(f"{field} = ?")
        values.append(value)

    if not fields:
        connection.close()
        return

    fields.append("updated_at = ?")
    values.append(datetime.now().isoformat())

    values.append(application_id)

    query = f"""
        UPDATE applications
        SET {", ".join(fields)}
        WHERE application_id = ?
    """

    cursor.execute(query, values)

    connection.commit()
    connection.close()


# ============================================================
# DATE FUNCTIONS
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


def get_configured_holidays():

    try:

        if isinstance(HOLIDAYS_CONFIG, list):
            values = HOLIDAYS_CONFIG

        else:
            values = json.loads(
                str(HOLIDAYS_CONFIG)
            )

        holidays = set()

        for value in values:

            parsed = parse_date(value)

            if parsed:
                holidays.add(parsed)

        return holidays

    except Exception:
        return set()


def is_working_day(day):

    if day.weekday() >= 5:
        return False

    if day in get_configured_holidays():
        return False

    return True


def add_working_days(start_date, number_of_days):

    current = start_date
    days_added = 0

    while days_added < number_of_days:

        current += timedelta(days=1)

        if is_working_day(current):
            days_added += 1

    return current


def count_working_days(start_date, end_date):

    if end_date <= start_date:
        return 0

    current = start_date
    count = 0

    while current < end_date:

        current += timedelta(days=1)

        if is_working_day(current):
            count += 1

    return count


def calculate_remaining_days(
    submission_date,
    processing_days
):

    submission = parse_date(submission_date)

    if not submission:
        return None

    if not processing_days:
        return None

    today = date.today()

    deadline = add_working_days(
        submission,
        int(processing_days)
    )

    if today >= deadline:
        return 0

    return count_working_days(
        today,
        deadline
    )


# ============================================================
# VALIDATION
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    return str(value).strip()


def is_valid_url(url):

    if not url:
        return False

    try:

        parsed = urlparse(url)

        return parsed.scheme in (
            "http",
            "https"
        ) and bool(parsed.netloc)

    except Exception:
        return False


def is_official_domain(url):

    if not is_valid_url(url):
        return False

    hostname = urlparse(url).hostname

    if not hostname:
        return False

    hostname = hostname.lower()

    official_extensions = [
        ".gov",
        ".gov.in",
        ".nic.in",
        ".ac.in"
    ]

    return any(
        hostname.endswith(extension)
        for extension in official_extensions
    )


# ============================================================
# OPENROUTER
# ============================================================

def call_openrouter(
    messages,
    temperature=0.2,
    max_tokens=1800
):

    if not OPENROUTER_API_KEY:

        return {
            "success": False,
            "error": "OPENROUTER_API_KEY is not configured."
        }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://nextstep-ai.streamlit.app",
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

        response.raise_for_status()

        data = response.json()

        choices = data.get("choices", [])

        if not choices:

            return {
                "success": False,
                "error": "The AI returned no response."
            }

        content = choices[0].get(
            "message",
            {}
        ).get(
            "content",
            ""
        )

        if not content:

            return {
                "success": False,
                "error": "The AI returned an empty response."
            }

        return {
            "success": True,
            "content": content
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "error": "The AI request timed out. Please try again."
        }

    except requests.exceptions.HTTPError as error:

        detail = ""

        try:
            detail = response.text[:500]
        except Exception:
            pass

        return {
            "success": False,
            "error": f"AI service error: {error}. {detail}"
        }

    except requests.exceptions.RequestException as error:

        return {
            "success": False,
            "error": f"Network error: {error}"
        }

    except Exception as error:

        return {
            "success": False,
            "error": f"Unexpected AI error: {error}"
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
        return json.loads(cleaned)

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
# AI SERVICE DISCOVERY
# ============================================================

def discover_service(user_text, language):

    system_prompt = """
You are the service identification engine for NextStep AI.

NextStep AI helps users understand and prepare applications
for government and public services.

Analyze the user's request.

Identify:

1. The government/public service.
2. The likely jurisdiction.
3. Whether the user appears to be asking for an application,
   renewal, certificate, license, registration, complaint,
   status tracking, or another service.
4. A short explanation.

IMPORTANT:

Do not invent a government department.
Do not claim that a service exists if it is unclear.
If the jurisdiction is unclear, say "Unknown".
If the service is unclear, say "Unknown".

Return ONLY valid JSON.

Schema:

{
  "service_name": "",
  "service_category": "",
  "jurisdiction": "",
  "department": "",
  "intent": "",
  "confidence": 0,
  "explanation": ""
}
"""

    user_prompt = f"""
User language: {language}

User request:
{user_text}
"""

    result = call_openrouter(
        [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
    )

    if not result["success"]:
        return {
            "success": False,
            "error": result["error"]
        }

    data = extract_json(
        result["content"]
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error": "AI returned invalid service information."
        }

    return {
        "success": True,
        "data": data
    }


# ============================================================
# AI REQUIREMENT DISCOVERY
# ============================================================

def discover_requirements(
    service_name,
    jurisdiction,
    language
):

    system_prompt = """
You are the requirements analysis engine for NextStep AI.

Identify the information and documents that an applicant
would normally need to prepare for the requested government
service.

Do not invent highly specific legal requirements.

Clearly distinguish:

- likely information
- commonly required documents
- information that must be verified against the official
  government portal

Return ONLY valid JSON.

Schema:

{
  "requirements": [
    {
      "name": "",
      "type": "information|document|optional",
      "description": "",
      "required": true
    }
  ],
  "verification_note": ""
}
"""

    user_prompt = f"""
Service:
{service_name}

Jurisdiction:
{jurisdiction}

Preferred language:
{language}
"""

    result = call_openrouter(
        [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
    )

    if not result["success"]:

        return {
            "success": False,
            "error": result["error"]
        }

    data = extract_json(
        result["content"]
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error": "AI returned invalid requirements."
        }

    return {
        "success": True,
        "data": data
    }


# ============================================================
# OFFICIAL SOURCE ANALYSIS
# ============================================================

def analyze_official_source(
    service_name,
    jurisdiction,
    official_url,
    language
):

    if not official_url:

        return {
            "success": False,
            "error": "No official source was provided."
        }

    if not is_valid_url(official_url):

        return {
            "success": False,
            "error": "The provided URL is invalid."
        }

    system_prompt = """
You are the official-source verification assistant for
NextStep AI.

The user has provided a government/public-service webpage.

Use ONLY the information supplied in the webpage content.

Extract:

1. Service name
2. Department
3. Processing time, if explicitly stated
4. Whether the processing time is working days or calendar days
5. Documents
6. Application URL
7. Important notes

CRITICAL:

Never invent a processing time.

If no processing time is clearly stated, return null.

Return ONLY valid JSON.

Schema:

{
  "service_name": "",
  "department": "",
  "processing_days": null,
  "timeline_type": "working_days|calendar_days|unknown",
  "documents": [],
  "application_url": "",
  "notes": ""
}
"""

    try:

        response = requests.get(
            official_url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent":
                "NextStep-AI/1.0"
            }
        )

        response.raise_for_status()

        html = response.text

        # Remove scripts and styles
        html = re.sub(
            r"<script.*?</script>",
            " ",
            html,
            flags=re.DOTALL | re.IGNORECASE
        )

        html = re.sub(
            r"<style.*?</style>",
            " ",
            html,
            flags=re.DOTALL | re.IGNORECASE
        )

        # Remove HTML tags
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

        # Keep prompt size manageable
        text = text[:18000]

    except Exception as error:

        return {
            "success": False,
            "error": f"Could not read official webpage: {error}"
        }

    user_prompt = f"""
Service requested:
{service_name}

Jurisdiction:
{jurisdiction}

Official URL:
{official_url}

Webpage content:
{text}

Preferred language:
{language}
"""

    result = call_openrouter(
        [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        max_tokens=2000
    )

    if not result["success"]:
        return result

    data = extract_json(
        result["content"]
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error": "Could not interpret the official source."
        }

    return {
        "success": True,
        "data": data
    }


# ============================================================
# TIMELINE DISCOVERY
# ============================================================

def discover_service_timeline(
    service_name,
    jurisdiction,
    official_url="",
    language="English"
):

    if not official_url:

        return {
            "success": False,
            "verified": False,
            "error":
                "An official government source is required "
                "to verify the processing timeline."
        }

    if not is_official_domain(official_url):

        return {
            "success": False,
            "verified": False,
            "error":
                "For timeline verification, please provide "
                "an official government or public-sector URL."
        }

    result = analyze_official_source(
        service_name,
        jurisdiction,
        official_url,
        language
    )

    if not result["success"]:

        return result

    data = result["data"]

    processing_days = data.get(
        "processing_days"
    )

    timeline_type = data.get(
        "timeline_type",
        "unknown"
    )

    if processing_days is None:

        return {
            "success": True,
            "verified": False,
            "data": data,
            "message":
                "No exact processing time was found "
                "on the supplied official source."
        }

    try:

        processing_days = int(
            processing_days
        )

    except Exception:

        processing_days = None

    if processing_days is None:

        return {
            "success": True,
            "verified": False,
            "data": data,
            "message":
                "The official source did not provide "
                "a usable numeric processing time."
        }

    return {
        "success": True,
        "verified": True,
        "processing_days": processing_days,
        "timeline_type": timeline_type,
        "data": data
    }


# ============================================================
# APPLICATION VALIDATION
# ============================================================

def validate_application(
    service_name,
    applicant_name,
    applicant_data
):

    errors = []

    if not clean_text(service_name):
        errors.append(
            "Service name is missing."
        )

    if not clean_text(applicant_name):
        errors.append(
            "Applicant name is required."
        )

    if not isinstance(
        applicant_data,
        dict
    ):
        errors.append(
            "Applicant information is invalid."
        )

    return errors


# ============================================================
# APPLICATION ID
# ============================================================

def generate_application_id():

    return (
        "NS-"
        + datetime.now().strftime("%Y%m%d")
        + "-"
        + uuid.uuid4().hex[:8].upper()
    )


# ============================================================
# GOVERNMENT SUBMISSION
# ============================================================

def submit_to_government(
    application
):

    # --------------------------------------------------------
    # DEMO MODE
    # --------------------------------------------------------

    if not GOVERNMENT_SUBMISSION_URL:

        application_id = generate_application_id()

        return {
            "success": True,
            "demo": True,
            "application_id": application_id,
            "government_reference": "",
            "status": "Submitted",
            "message":
                "Demo application created. "
                "No real government submission was performed."
        }

    # --------------------------------------------------------
    # REAL BACKEND
    # --------------------------------------------------------

    payload = {
        "service_name":
            application["service_name"],

        "jurisdiction":
            application["jurisdiction"],

        "applicant_name":
            application["applicant_name"],

        "applicant_data":
            application["applicant_data"],

        "submission_date":
            application["submission_date"]
    }

    try:

        response = requests.post(
            GOVERNMENT_SUBMISSION_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            headers={
                "Content-Type":
                    "application/json"
            }
        )

        response.raise_for_status()

        data = response.json()

        application_id = (
            data.get("application_id")
            or data.get("applicationId")
            or data.get("id")
        )

        if not application_id:

            return {
                "success": False,
                "error":
                    "Government backend did not return "
                    "an application ID."
            }

        return {
            "success": True,
            "demo": False,
            "application_id":
                str(application_id),

            "government_reference":
                str(
                    data.get(
                        "reference",
                        ""
                    )
                ),

            "status":
                data.get(
                    "status",
                    "Submitted"
                ),

            "message":
                data.get(
                    "message",
                    "Application submitted."
                )
        }

    except Exception as error:

        return {
            "success": False,
            "error":
                f"Government submission failed: {error}"
        }


# ============================================================
# GOVERNMENT STATUS
# ============================================================

def get_government_status(
    application
):

    # --------------------------------------------------------
    # DEMO MODE
    # --------------------------------------------------------

    if not GOVERNMENT_STATUS_URL:

        return {
            "success": True,
            "demo": True,
            "status":
                application.get(
                    "status",
                    "Submitted"
                ),
            "message":
                "Live government status is not configured."
        }

    # --------------------------------------------------------
    # REAL STATUS API
    # --------------------------------------------------------

    payload = {
        "application_id":
            application["application_id"],

        "government_reference":
            application.get(
                "government_reference",
                ""
            )
    }

    try:

        response = requests.post(
            GOVERNMENT_STATUS_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            headers={
                "Content-Type":
                    "application/json"
            }
        )

        response.raise_for_status()

        data = response.json()

        status = data.get(
            "status"
        )

        if not status:

            status = "Unknown"

        return {
            "success": True,
            "demo": False,
            "status": status,
            "message":
                data.get(
                    "message",
                    ""
                )
        }

    except Exception as error:

        return {
            "success": False,
            "error":
                f"Status request failed: {error}"
        }


# ============================================================
# AI GENERAL ASSISTANT
# ============================================================

def ask_ai(
    user_message,
    language
):

    system_prompt = f"""
You are NextStep AI, an AI assistant for government and
public services.

Preferred response language:
{language}

Your job is to:

- understand government service requests
- explain procedures
- identify likely requirements
- help users prepare applications
- explain application tracking
- explain processing timelines

Important rules:

1. Never claim that a real government application was
   submitted unless a configured government backend confirms it.

2. Never invent an exact government processing time.

3. If a processing time is not verified from an official source,
   clearly say that it needs official verification.

4. Do not claim access to private government databases.

5. Keep responses clear and useful.

6. If the user asks for a service, identify what information
   should be collected before application preparation.
"""

    result = call_openrouter(
        [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ]
    )

    if not result["success"]:

        return result["error"]

    return result["content"]


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .main {
        background-color: #f7f9fc;
    }

    .hero {
        padding: 25px;
        border-radius: 20px;
        background:
            linear-gradient(
                135deg,
                #111827,
                #1e3a8a
            );
        color: white;
        margin-bottom: 25px;
    }

    .hero h1 {
        font-size: 42px;
        margin-bottom: 5px;
    }

    .hero p {
        font-size: 17px;
        opacity: 0.9;
    }

    .card {
        padding: 20px;
        border-radius: 16px;
        background: white;
        border: 1px solid #e5e7eb;
        margin-bottom: 15px;
    }

    .status-card {
        padding: 18px;
        border-radius: 16px;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        text-align: center;
    }

    .big-number {
        font-size: 34px;
        font-weight: 700;
    }

    .small-label {
        color: #6b7280;
        font-size: 14px;
    }

    .demo-warning {
        padding: 14px;
        border-radius: 12px;
        background: #fff7ed;
        border: 1px solid #fed7aa;
        color: #9a3412;
        margin-bottom: 15px;
    }

    .verified {
        padding: 12px;
        border-radius: 10px;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        color: #065f46;
    }

    .unverified {
        padding: 12px;
        border-radius: 10px;
        background: #fff7ed;
        border: 1px solid #fed7aa;
        color: #9a3412;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.title("🤖 NextStep AI")

    st.caption(
        "AI-powered government services assistant"
    )

    st.divider()

    st.session_state.language = st.selectbox(
        "🌐 Preferred language",
        SUPPORTED_LANGUAGES,
        index=SUPPORTED_LANGUAGES.index(
            st.session_state.language
        )
    )

    st.divider()

    st.subheader("System")

    if OPENROUTER_API_KEY:

        st.success(
            "AI service configured"
        )

    else:

        st.error(
            "AI service not configured"
        )

    if GOVERNMENT_SUBMISSION_URL:

        st.success(
            "Government submission backend configured"
        )

    else:

        st.warning(
            "Demo submission mode"
        )

    if GOVERNMENT_STATUS_URL:

        st.success(
            "Live status backend configured"
        )

    else:

        st.warning(
            "Demo status mode"
        )

    st.divider()

    st.caption(
        "NextStep AI never pretends a demo "
        "application is a real government submission."
    )


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">

        <h1>🤖 NextStep AI</h1>

        <p>
        One intelligent assistant for discovering,
        preparing and tracking government services.
        </p>

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# DEMO MODE WARNING
# ============================================================

if not GOVERNMENT_SUBMISSION_URL:

    st.markdown(
        """
        <div class="demo-warning">

        <b>Demo mode:</b>
        Real government submission is not connected yet.
        Applications created here are demonstrations only.

        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# MAIN TABS
# ============================================================

tab_assistant, tab_application, tab_tracking = st.tabs(
    [
        "🤖 AI Assistant",
        "📝 Application",
        "📊 Track Status"
    ]
)


# ============================================================
# TAB 1: ASSISTANT
# ============================================================

with tab_assistant:

    st.subheader(
        "Tell me what government service you need"
    )

    st.write(
        "You can describe the service naturally. "
        "For example: certificate, license, registration, "
        "renewal, public-service request or application status."
    )

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):

            st.markdown(
                message["content"]
            )

    user_prompt = st.chat_input(
        "Describe the government service you need..."
    )

    if user_prompt:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_prompt
            }
        )

        with st.chat_message("user"):

            st.markdown(
                user_prompt
            )

        with st.chat_message("assistant"):

            with st.spinner(
                "Understanding your request..."
            ):

                service_result = discover_service(
                    user_prompt,
                    st.session_state.language
                )

                if service_result["success"]:

                    service = service_result["data"]

                    st.session_state.selected_service = service

                    service_name = service.get(
                        "service_name",
                        "Unknown"
                    )

                    jurisdiction = service.get(
                        "jurisdiction",
                        "Unknown"
                    )

                    confidence = service.get(
                        "confidence",
                        0
                    )

                    st.markdown(
                        "### 🔎 Service identified"
                    )

                    st.write(
                        f"**Service:** {service_name}"
                    )

                    st.write(
                        f"**Jurisdiction:** {jurisdiction}"
                    )

                    st.write(
                        f"**Category:** "
                        f"{service.get('service_category', 'Unknown')}"
                    )

                    st.write(
                        f"**Intent:** "
                        f"{service.get('intent', 'Unknown')}"
                    )

                    if confidence:

                        try:

                            confidence_value = (
                                float(confidence)
                            )

                            confidence_value = max(
                                0,
                                min(
                                    100,
                                    confidence_value
                                )
                            )

                            st.progress(
                                confidence_value / 100
                            )

                        except Exception:
                            pass

                    st.info(
                        service.get(
                            "explanation",
                            ""
                        )
                    )

                    requirements_result = (
                        discover_requirements(
                            service_name,
                            jurisdiction,
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

                        st.markdown(
                            "### 📋 Information you may need"
                        )

                        for item in requirements:

                            name = item.get(
                                "name",
                                "Requirement"
                            )

                            description = item.get(
                                "description",
                                ""
                            )

                            required = item.get(
                                "required",
                                False
                            )

                            label = (
                                "Required"
                                if required
                                else "Optional"
                            )

                            st.write(
                                f"**{name}** "
                                f"({label})"
                            )

                            if description:
                                st.caption(
                                    description
                                )

                        note = (
                            requirements_result[
                                "data"
                            ].get(
                                "verification_note",
                                ""
                            )
                        )

                        if note:

                            st.info(note)

                    response_text = (
                        f"I identified this as **{service_name}** "
                        f"for **{jurisdiction}**. "
                        "You can continue to the Application tab "
                        "to prepare the application."
                    )

                else:

                    response_text = (
                        "I couldn't identify the service reliably. "
                        f"{service_result['error']}"
                    )

                st.markdown(
                    response_text
                )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response_text
            }
        )


# ============================================================
# TAB 2: APPLICATION
# ============================================================

with tab_application:

    st.subheader(
        "📝 Prepare your application"
    )

    service = (
        st.session_state.selected_service
    )

    if not service:

        st.info(
            "First describe the government service "
            "you need in the AI Assistant tab."
        )

    else:

        service_name = service.get(
            "service_name",
            "Unknown"
        )

        jurisdiction = service.get(
            "jurisdiction",
            "Unknown"
        )

        st.markdown(
            f"""
            <div class="card">

            <b>Service</b><br>
            {service_name}

            <br><br>

            <b>Jurisdiction</b><br>
            {jurisdiction}

            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            "### 👤 Applicant information"
        )

        applicant_name = st.text_input(
            "Full name",
            key="applicant_name"
        )

        phone_number = st.text_input(
            "Phone number",
            key="phone_number"
        )

        email = st.text_input(
            "Email address",
            key="email"
        )

        address = st.text_area(
            "Address",
            key="address"
        )

        st.markdown(
            "### 📎 Additional information"
        )

        additional_information = st.text_area(
            "Additional information required for this service",
            key="additional_information"
        )

        st.markdown(
            "### 📄 Official source"
        )

        st.write(
            "For accurate processing-time information, "
            "provide the official government/public-service "
            "webpage for this service."
        )

        official_url = st.text_input(
            "Official government service URL",
            placeholder="https://example.gov.in/service",
            key="official_url"
        )

        timeline_result = None

        if st.button(
            "🔎 Verify official timeline",
            use_container_width=True
        ):

            if not official_url:

                st.warning(
                    "Please enter the official service URL."
                )

            elif not is_valid_url(
                official_url
            ):

                st.error(
                    "Please enter a valid URL."
                )

            elif not is_official_domain(
                official_url
            ):

                st.warning(
                    "For timeline verification, "
                    "please use an official government "
                    "or public-sector domain."
                )

            else:

                with st.spinner(
                    "Reading the official source..."
                ):

                    timeline_result = (
                        discover_service_timeline(
                            service_name,
                            jurisdiction,
                            official_url,
                            st.session_state.language
                        )
                    )

                    st.session_state[
                        "timeline_result"
                    ] = timeline_result

        timeline_result = st.session_state.get(
            "timeline_result"
        )

        if timeline_result:

            if timeline_result.get(
                "verified"
            ):

                processing_days = (
                    timeline_result[
                        "processing_days"
                    ]
                )

                timeline_type = (
                    timeline_result[
                        "timeline_type"
                    ]
                )

                st.markdown(
                    f"""
                    <div class="verified">

                    ✅ <b>Official timeline detected</b><br><br>

                    Processing time:
                    <b>{processing_days} days</b><br>

                    Timeline type:
                    <b>{timeline_type}</b>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:

                st.markdown(
                    """
                    <div class="unverified">

                    ⚠️ An exact processing timeline
                    could not be verified from the
                    supplied official source.

                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.markdown(
            "### 🔐 Review and authorize"
        )

        review_data = {
            "name": applicant_name,
            "phone": phone_number,
            "email": email,
            "address": address,
            "additional_information":
                additional_information
        }

        with st.expander(
            "Review application information",
            expanded=True
        ):

            st.json(
                review_data
            )

        authorization = st.checkbox(
            "I have reviewed the information and authorize NextStep AI to submit this application when a real government backend is configured."
        )

        submit_button = st.button(
            "🚀 Submit Application",
            type="primary",
            use_container_width=True
        )

        if submit_button:

            errors = validate_application(
                service_name,
                applicant_name,
                review_data
            )

            if errors:

                for error in errors:

                    st.error(error)

            elif not authorization:

                st.error(
                    "Please authorize the application "
                    "before submitting."
                )

            else:

                submission_date = date.today()

                timeline_days = None
                timeline_type = "unknown"

                if timeline_result:

                    if timeline_result.get(
                        "verified"
                    ):

                        timeline_days = (
                            timeline_result[
                                "processing_days"
                            ]
                        )

                        timeline_type = (
                            timeline_result[
                                "timeline_type"
                            ]
                        )

                application_payload = {

                    "service_name":
                        service_name,

                    "jurisdiction":
                        jurisdiction,

                    "applicant_name":
                        applicant_name,

                    "applicant_data":
                        review_data,

                    "submission_date":
                        submission_date.isoformat(),

                    "official_processing_days":
                        timeline_days or 0,

                    "timeline_type":
                        timeline_type,

                    "official_source":
                        official_url,

                    "status":
                        "Submitted"
                }

                with st.spinner(
                    "Submitting application..."
                ):

                    result = (
                        submit_to_government(
                            application_payload
                        )
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

                    expected_completion = ""

                    if timeline_days:

                        if timeline_type == "calendar_days":

                            deadline = (
                                submission_date
                                + timedelta(
                                    days=int(
                                        timeline_days
                                    )
                                )
                            )

                        else:

                            deadline = (
                                add_working_days(
                                    submission_date,
                                    int(
                                        timeline_days
                                    )
                                )
                            )

                        expected_completion = (
                            deadline.isoformat()
                        )

                    application = {

                        "application_id":
                            application_id,

                        "service_name":
                            service_name,

                        "jurisdiction":
                            jurisdiction,

                        "applicant_name":
                            applicant_name,

                        "applicant_data":
                            review_data,

                        "status":
                            result.get(
                                "status",
                                "Submitted"
                            ),

                        "submission_date":
                            submission_date.isoformat(),

                        "official_processing_days":
                            timeline_days or 0,

                        "timeline_type":
                            timeline_type,

                        "expected_completion_date":
                            expected_completion,

                        "official_source":
                            official_url,

                        "government_reference":
                            result.get(
                                "government_reference",
                                ""
                            ),

                        "created_at":
                            datetime.now().isoformat(),

                        "updated_at":
                            datetime.now().isoformat()
                    }

                    try:

                        save_application(
                            application
                        )

                        st.session_state[
                            "application_data"
                        ] = application

                    except sqlite3.IntegrityError:

                        st.error(
                            "This application ID already exists. "
                            "Please try again."
                        )

                        st.stop()

                    st.success(
                        result.get(
                            "message",
                            "Application created successfully."
                        )
                    )

                    st.markdown(
                        f"""
                        ### 🆔 Application ID

                        ## `{application_id}`
                        """
                    )

                    if result.get(
                        "demo"
                    ):

                        st.warning(
                            "⚠️ This is a DEMO application ID. "
                            "It is not a real government application."
                        )

                    if expected_completion:

                        st.info(
                            f"Expected completion date: "
                            f"**{expected_completion}**"
                        )

                    st.success(
                        "Go to the **Track Status** tab "
                        "to monitor this application."
                    )


# ============================================================
# TAB 3: TRACK STATUS
# ============================================================

with tab_tracking:

    st.subheader(
        "📊 Track your application"
    )

    tracking_id = st.text_input(
        "Enter your NextStep AI application ID",
        placeholder="NS-20260926-XXXXXXXX"
    )

    track_button = st.button(
        "🔍 Track Application",
        use_container_width=True
    )

    if track_button:

        if not tracking_id.strip():

            st.warning(
                "Please enter an application ID."
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

                # ------------------------------------------------
                # LIVE GOVERNMENT STATUS
                # ------------------------------------------------

                status_result = (
                    get_government_status(
                        application
                    )
                )

                if status_result["success"]:

                    latest_status = (
                        status_result[
                            "status"
                        ]
                    )

                    if latest_status != application[
                        "status"
                    ]:

                        update_application(
                            application[
                                "application_id"
                            ],
                            status=latest_status
                        )

                        application[
                            "status"
                        ] = latest_status

                # ------------------------------------------------
                # STATUS
                # ------------------------------------------------

                st.markdown(
                    f"""
                    <div class="card">

                    <h2>
                    {application['service_name']}
                    </h2>

                    <p>
                    <b>Application ID:</b>
                    {application['application_id']}
                    </p>

                    <p>
                    <b>Jurisdiction:</b>
                    {application['jurisdiction']}
                    </p>

                    <p>
                    <b>Status:</b>
                    {application['status']}
                    </p>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # ------------------------------------------------
                # PROCESSING TIMELINE
                # ------------------------------------------------

                processing_days = application.get(
                    "official_processing_days",
                    0
                )

                submission_date = parse_date(
                    application.get(
                        "submission_date"
                    )
                )

                timeline_type = application.get(
                    "timeline_type",
                    "unknown"
                )

                if processing_days and submission_date:

                    today = date.today()

                    if timeline_type == "calendar_days":

                        deadline = (
                            submission_date
                            + timedelta(
                                days=int(
                                    processing_days
                                )
                            )
                        )

                        if today >= deadline:

                            remaining_days = 0

                        else:

                            remaining_days = (
                                deadline - today
                            ).days

                    else:

                        deadline = (
                            add_working_days(
                                submission_date,
                                int(
                                    processing_days
                                )
                            )
                        )

                        remaining_days = (
                            calculate_remaining_days(
                                submission_date,
                                processing_days
                            )
                        )

                    col1, col2, col3 = st.columns(3)

                    with col1:

                        st.markdown(
                            f"""
                            <div class="status-card">

                            <div class="big-number">
                            {processing_days}
                            </div>

                            <div class="small-label">
                            Official processing days
                            </div>

                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    with col2:

                        st.markdown(
                            f"""
                            <div class="status-card">

                            <div class="big-number">
                            {remaining_days}
                            </div>

                            <div class="small-label">
                            Remaining days
                            </div>

                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    with col3:

                        st.markdown(
                            f"""
                            <div class="status-card">

                            <div class="big-number">
                            {deadline.strftime("%d %b")}
                            </div>

                            <div class="small-label">
                            Expected completion
                            </div>

                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    st.progress(
                        min(
                            1.0,
                            max(
                                0.0,
                                (
                                    processing_days
                                    - remaining_days
                                )
                                / processing_days
                            )
                        )
                    )

                    if remaining_days == 0:

                        st.success(
                            "The expected processing period "
                            "has been reached."
                        )

                    else:

                        st.info(
                            f"{remaining_days} working days "
                            "remaining based on the recorded "
                            "official processing timeline."
                        )

                else:

                    st.warning(
                        "No verified processing timeline "
                        "is stored for this application."
                    )

                # ------------------------------------------------
                # SUBMISSION INFORMATION
                # ------------------------------------------------

                st.markdown(
                    "### 📅 Application timeline"
                )

                st.write(
                    f"**Submitted:** "
                    f"{application['submission_date']}"
                )

                if application.get(
                    "official_source"
                ):

                    st.write(
                        "**Official source:** "
                        f"{application['official_source']}"
                    )

                if application.get(
                    "government_reference"
                ):

                    st.write(
                        "**Government reference:** "
                        f"{application['government_reference']}"
                    )

                if status_result.get(
                    "demo"
                ):

                    st.caption(
                        "Live government status is not connected. "
                        "The displayed status is stored by NextStep AI."
                    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "NextStep AI • AI-powered government services assistant"
)

st.caption(
    "Demo mode must not be represented as a real government submission."
)
