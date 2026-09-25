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
# NEXTSTEP AI
# Government Services Assistant
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

APP_NAME = "NextStep AI"

DATABASE_FILE = "nextstep_ai.db"

OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)

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

    return os.getenv(name, default)


OPENROUTER_API_KEY = get_secret(
    "OPENROUTER_API_KEY"
)

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

DEFAULT_STATE = {
    "messages": [],
    "selected_service": None,
    "requirements": [],
    "timeline_result": None,
    "application_data": None,
    "language": "English",
    "last_service_request": ""
}

for key, value in DEFAULT_STATE.items():

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
# DATABASE: SAVE
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
            application["service_name"],
            application.get(
                "service_category",
                ""
            ),
            application["jurisdiction"],
            application.get(
                "department",
                ""
            ),
            application["applicant_name"],
            json.dumps(
                application.get(
                    "applicant_data",
                    {}
                )
            ),
            application["status"],
            application["submission_date"],
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
            application["created_at"],
            application["updated_at"]
        )
    )

    connection.commit()
    connection.close()


# ============================================================
# DATABASE: LOAD
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
        (application_id,)
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
# DATABASE: UPDATE
# ============================================================

def update_application(
    application_id,
    **updates
):

    if not updates:
        return

    allowed_fields = {
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

        if field not in allowed_fields:
            continue

        fields.append(
            f"{field} = ?"
        )

        values.append(value)

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
# DATABASE: RECENT APPLICATIONS
# ============================================================

def get_recent_applications(limit=10):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            application_id,
            service_name,
            status,
            submission_date
        FROM applications
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()

    connection.close()

    return rows


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

            parsed = parse_date(value)

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
    added = 0

    while added < number_of_days:

        current += timedelta(days=1)

        if is_working_day(current):
            added += 1

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

        current += timedelta(days=1)

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

        parsed = urlparse(url)

        return (
            parsed.scheme in [
                "http",
                "https"
            ]
            and bool(parsed.netloc)
        )

    except Exception:

        return False


def official_domain(url):

    if not valid_url(url):
        return False

    try:

        hostname = (
            urlparse(url)
            .hostname
            .lower()
        )

    except Exception:

        return False

    official_endings = [
        ".gov",
        ".gov.in",
        ".nic.in",
        ".ac.in"
    ]

    return any(
        hostname.endswith(
            ending
        )
        for ending in official_endings
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
                    "No AI response was returned."
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
                "The AI request timed out."
        }

    except requests.exceptions.HTTPError:

        detail = ""

        try:
            detail = response.text[:500]
        except Exception:
            pass

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
# SERVICE IDENTIFICATION
# ============================================================

def identify_service(
    user_text,
    language
):

    system_prompt = f"""
You are the intelligence engine of NextStep AI.

Identify the government/public service the user is
asking about.

Preferred language:
{language}

Return ONLY JSON.

Do not invent information.

If jurisdiction is unclear, use "Unknown".

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
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_text
            }
        ]
    )

    if not result["success"]:
        return result

    data = extract_json(
        result["content"]
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error":
                "The AI returned invalid service data."
        }

    return {
        "success": True,
        "data": data
    }


# ============================================================
# REQUIREMENTS
# ============================================================

def generate_requirements(
    service_name,
    jurisdiction,
    language
):

    system_prompt = f"""
You are the requirements engine for NextStep AI.

Service:
{service_name}

Jurisdiction:
{jurisdiction}

Language:
{language}

Give likely application information and documents.

Do not pretend that AI-generated requirements are
official legal requirements.

Return ONLY JSON.

Schema:

{{
    "requirements": [
        {{
            "name": "",
            "type": "information|document|optional",
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
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content":
                    "Generate the requirements."
            }
        ]
    )

    if not result["success"]:
        return result

    data = extract_json(
        result["content"]
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "error":
                "Invalid requirements response."
        }

    return {
        "success": True,
        "data": data
    }


# ============================================================
# OFFICIAL PAGE READER
# ============================================================

def read_official_page(
    url
):

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
            flags=re.DOTALL | re.IGNORECASE
        )

        html = re.sub(
            r"<style.*?</style>",
            " ",
            html,
            flags=re.DOTALL | re.IGNORECASE
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
            "text": text[:18000]
        }

    except Exception as error:

        return {
            "success": False,
            "error":
                f"Unable to read the page: {error}"
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
                "Please provide an official government "
                "or public-sector URL."
        }

    page = read_official_page(
        url
    )

    if not page["success"]:
        return page

    system_prompt = """
You verify processing timelines for NextStep AI.

Use ONLY the supplied official webpage content.

Find an explicitly stated processing period.

Examples:

"7 working days"
"15 days"
"within 30 calendar days"

Do NOT infer a timeline.

Return ONLY JSON.

Schema:

{
    "processing_days": null,
    "timeline_type": "working_days|calendar_days|unknown",
    "service_name": "",
    "department": "",
    "notes": ""
}
"""

    user_prompt = f"""
Service:
{service_name}

Jurisdiction:
{jurisdiction}

Official URL:
{url}

Official webpage content:
{page["text"]}

Language:
{language}
"""

    result = call_ai(
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
        max_tokens=1500
    )

    if not result["success"]:
        return result

    data = extract_json(
        result["content"]
    )

    if not isinstance(data, dict):

        return {
            "success": False,
            "verified": False,
            "error":
                "Could not interpret the official page."
        }

    processing_days = data.get(
        "processing_days"
    )

    try:

        processing_days = int(
            processing_days
        )

    except Exception:

        processing_days = None

    if not processing_days:

        return {
            "success": True,
            "verified": False,
            "data": data,
            "message":
                "No explicit processing timeline "
                "was found."
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
# GOVERNMENT SUBMISSION CONNECTOR
# ============================================================

def submit_application(
    application
):

    # If an authorized endpoint exists,
    # use it.

    if GOVERNMENT_SUBMISSION_URL:

        payload = {
            "service_name":
                application["service_name"],

            "jurisdiction":
                application["jurisdiction"],

            "department":
                application.get(
                    "department",
                    ""
                ),

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

            if government_id:

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
                    str(error)
            }

    # Internal application workflow.
    # This makes the application usable even before
    # an external government API is connected.

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
# GOVERNMENT STATUS CONNECTOR
# ============================================================

def fetch_status(
    application
):

    if not GOVERNMENT_STATUS_URL:

        return {
            "success": True,
            "status":
                application.get(
                    "status",
                    "Application Submitted"
                ),
            "connected":
                False
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
                ),
            "connected":
                True
        }

    except Exception:

        return {
            "success": True,
            "status":
                application.get(
                    "status",
                    "Application Submitted"
                ),
            "connected":
                False
        }


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background:
            linear-gradient(
                180deg,
                #f8fafc 0%,
                #eef2ff 100%
            );
    }

    section[data-testid="stSidebar"] {
        background: #111827;
    }

    section[data-testid="stSidebar"] * {
        color: #f9fafb !important;
    }

    .hero-box {
        padding: 35px;
        border-radius: 24px;
        background:
            linear-gradient(
                135deg,
                #111827,
                #1d4ed8
            );
        color: white;
        margin-bottom: 25px;
        box-shadow:
            0 12px 35px
            rgba(30, 64, 175, 0.20);
    }

    .hero-title {
        font-size: 44px;
        font-weight: 800;
        margin: 0;
        color: white;
    }

    .hero-subtitle {
        font-size: 18px;
        margin-top: 10px;
        color: #dbeafe;
    }

    .feature-card {
        padding: 22px;
        border-radius: 18px;
        background: white;
        border: 1px solid #e5e7eb;
        min-height: 150px;
        box-shadow:
            0 5px 18px
            rgba(15, 23, 42, 0.05);
    }

    .feature-icon {
        font-size: 30px;
    }

    .feature-title {
        font-size: 18px;
        font-weight: 700;
        margin-top: 8px;
    }

    .feature-text {
        color: #64748b;
        font-size: 14px;
        margin-top: 5px;
    }

    .service-card {
        padding: 20px;
        border-radius: 18px;
        background: white;
        border: 1px solid #e2e8f0;
        margin-bottom: 15px;
    }

    .success-card {
        padding: 20px;
        border-radius: 16px;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
    }

    .timeline-card {
        padding: 20px;
        border-radius: 16px;
        background: white;
        border: 1px solid #e2e8f0;
        text-align: center;
    }

    .timeline-number {
        font-size: 34px;
        font-weight: 800;
    }

    .timeline-label {
        color: #64748b;
        font-size: 13px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## 🤖 NextStep AI"
    )

    st.caption(
        "Your intelligent government-services assistant"
    )

    st.divider()

    st.session_state.language = st.selectbox(
        "🌐 Language",
        SUPPORTED_LANGUAGES,
        index=SUPPORTED_LANGUAGES.index(
            st.session_state.language
        )
    )

    st.divider()

    st.markdown(
        "### System"
    )

    if OPENROUTER_API_KEY:

        st.success(
            "AI connected"
        )

    else:

        st.error(
            "AI key required"
        )

    st.divider()

    st.caption(
        "NextStep AI helps discover services, "
        "prepare applications and track progress."
    )


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero-box">

        <div class="hero-title">
            🤖 NextStep AI
        </div>

        <div class="hero-subtitle">
            One intelligent assistant for
            discovering, preparing and tracking
            public services.
        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HOME FEATURES
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:

    st.markdown(
        """
        <div class="feature-card">

            <div class="feature-icon">
                🔎
            </div>

            <div class="feature-title">
                Discover
            </div>

            <div class="feature-text">
                Describe the service naturally
                and let AI identify the
                relevant government service.
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


with col2:

    st.markdown(
        """
        <div class="feature-card">

            <div class="feature-icon">
                📋
            </div>

            <div class="feature-title">
                Prepare
            </div>

            <div class="feature-text">
                Understand requirements,
                organize applicant information
                and prepare your application.
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


with col3:

    st.markdown(
        """
        <div class="feature-card">

            <div class="feature-icon">
                ⏳
            </div>

            <div class="feature-title">
                Track
            </div>

            <div class="feature-text">
                Store your application,
                monitor status and calculate
                remaining processing time.
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


st.write("")


# ============================================================
# TABS
# ============================================================

assistant_tab, application_tab, tracking_tab = st.tabs(
    [
        "🤖 AI Assistant",
        "📝 Application",
        "📊 Track Status"
    ]
)


# ============================================================
# AI ASSISTANT
# ============================================================

with assistant_tab:

    st.header(
        "What government service do you need?"
    )

    st.write(
        "Describe what you want in your own words."
    )

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):

            st.markdown(
                message["content"]
            )

    prompt = st.chat_input(
        "Example: I need to apply for a birth certificate..."
    )

    if prompt:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )

        with st.chat_message("user"):

            st.write(prompt)

        with st.chat_message("assistant"):

            with st.spinner(
                "Understanding your request..."
            ):

                result = identify_service(
                    prompt,
                    st.session_state.language
                )

                if result["success"]:

                    service = result["data"]

                    st.session_state.selected_service = service

                    st.session_state.last_service_request = prompt

                    service_name = service.get(
                        "service_name",
                        "Unknown service"
                    )

                    jurisdiction = service.get(
                        "jurisdiction",
                        "Unknown"
                    )

                    category = service.get(
                        "service_category",
                        "Public service"
                    )

                    department = service.get(
                        "department",
                        "Unknown"
                    )

                    intent = service.get(
                        "intent",
                        "Application"
                    )

                    st.markdown(
                        "### 🔎 Service identified"
                    )

                    c1, c2 = st.columns(2)

                    with c1:

                        st.write(
                            f"**Service**  \n"
                            f"{service_name}"
                        )

                        st.write(
                            f"**Category**  \n"
                            f"{category}"
                        )

                    with c2:

                        st.write(
                            f"**Jurisdiction**  \n"
                            f"{jurisdiction}"
                        )

                        st.write(
                            f"**Department**  \n"
                            f"{department}"
                        )

                    st.write(
                        f"**Request type:** {intent}"
                    )

                    st.info(
                        service.get(
                            "explanation",
                            "The service has been identified."
                        )
                    )

                    with st.spinner(
                        "Preparing requirements..."
                    ):

                        requirements_result = (
                            generate_requirements(
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
                            "### 📋 What you may need"
                        )

                        for requirement in requirements:

                            name = requirement.get(
                                "name",
                                "Requirement"
                            )

                            description = requirement.get(
                                "description",
                                ""
                            )

                            required = requirement.get(
                                "required",
                                False
                            )

                            marker = (
                                "Required"
                                if required
                                else "Optional"
                            )

                            st.markdown(
                                f"**{name}** "
                                f"• {marker}"
                            )

                            if description:

                                st.caption(
                                    description
                                )

                    response = (
                        f"Your request was identified as "
                        f"**{service_name}**. "
                        f"Open the **Application** tab to "
                        f"continue preparing it."
                    )

                else:

                    response = (
                        "I couldn't identify the service yet. "
                        f"{result.get('error', '')}"
                    )

                    st.error(response)

                st.markdown(response)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response
            }
        )


# ============================================================
# APPLICATION TAB
# ============================================================

with application_tab:

    st.header(
        "📝 Prepare Application"
    )

    service = (
        st.session_state.selected_service
    )

    if not service:

        st.info(
            "Start by describing a government service "
            "in the AI Assistant."
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

        department = service.get(
            "department",
            "Unknown"
        )

        st.markdown(
            f"""
            <div class="service-card">

                <b>Service</b><br>
                {service_name}

                <br><br>

                <b>Jurisdiction</b><br>
                {jurisdiction}

                <br><br>

                <b>Department</b><br>
                {department}

            </div>
            """,
            unsafe_allow_html=True
        )

        st.subheader(
            "👤 Applicant information"
        )

        applicant_name = st.text_input(
            "Full name"
        )

        phone = st.text_input(
            "Phone number"
        )

        email = st.text_input(
            "Email address"
        )

        address = st.text_area(
            "Address"
        )

        st.subheader(
            "📄 Service information"
        )

        additional_information = st.text_area(
            "Additional information"
        )

        st.subheader(
            "🔎 Official service information"
        )

        official_url = st.text_input(
            "Official government service URL",
            placeholder="https://..."
        )

        verify_button = st.button(
            "Verify Official Information",
            use_container_width=True
        )

        if verify_button:

            if not official_url:

                st.warning(
                    "Enter the official service webpage first."
                )

                st.session_state.timeline_result = None

            elif not valid_url(official_url):

                st.error(
                    "Please enter a valid URL."
                )

                st.session_state.timeline_result = None

            elif not official_domain(official_url):

                st.warning(
                    "Please use an official government "
                    "or public-sector webpage."
                )

                st.session_state.timeline_result = None

            else:

                with st.spinner(
                    "Checking the official information..."
                ):

                    timeline = verify_timeline(
                        service_name,
                        jurisdiction,
                        official_url,
                        st.session_state.language
                    )

                st.session_state.timeline_result = (
                    timeline
                )

        timeline = (
            st.session_state.timeline_result
        )

        if timeline:

            if timeline.get(
                "verified"
            ):

                days = timeline[
                    "processing_days"
                ]

                timeline_type = timeline[
                    "timeline_type"
                ]

                st.success(
                    f"Official processing timeline found: "
                    f"{days} {timeline_type.replace('_', ' ')}."
                )

                notes = (
                    timeline
                    .get("data", {})
                    .get("notes", "")
                )

                if notes:

                    st.info(notes)

            else:

                st.info(
                    "The official webpage did not provide "
                    "an exact processing timeline."
                )

        st.subheader(
            "🔐 Review"
        )

        application_information = {

            "name":
                applicant_name,

            "phone":
                phone,

            "email":
                email,

            "address":
                address,

            "additional_information":
                additional_information
        }

        with st.expander(
            "Review applicant information",
            expanded=True
        ):

            st.json(
                application_information
            )

        authorize = st.checkbox(
            "I have reviewed my information and authorize NextStep AI to create and process this application."
        )

        submit = st.button(
            "🚀 Create Application",
            type="primary",
            use_container_width=True
        )

        if submit:

            errors = []

            if not applicant_name.strip():

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

            if not authorize:

                errors.append(
                    "Please authorize the application."
                )

            if errors:

                for error in errors:

                    st.error(error)

            else:

                submission_date = date.today()

                processing_days = 0

                timeline_type = "unknown"

                if timeline:

                    if timeline.get(
                        "verified"
                    ):

                        processing_days = (
                            int(
                                timeline[
                                    "processing_days"
                                ]
                            )
                        )

                        timeline_type = (
                            timeline[
                                "timeline_type"
                            ]
                        )

                expected_completion = ""

                if processing_days:

                    if (
                        timeline_type
                        == "calendar_days"
                    ):

                        deadline = (
                            submission_date
                            + timedelta(
                                days=
                                processing_days
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
                        service_name,

                    "service_category":
                        service.get(
                            "service_category",
                            ""
                        ),

                    "jurisdiction":
                        jurisdiction,

                    "department":
                        department,

                    "applicant_name":
                        applicant_name,

                    "applicant_data":
                        application_information,

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
                        "Application Submitted",

                    "created_at":
                        datetime.now().isoformat(),

                    "updated_at":
                        datetime.now().isoformat()
                }

                with st.spinner(
                    "Creating your application..."
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

                    try:

                        save_application(
                            application
                        )

                        st.session_state[
                            "application_data"
                        ] = application

                        st.session_state[
                            "last_application_id"
                        ] = application[
                            "application_id"
                        ]

                        st.markdown(
                            """
                            <div class="success-card">

                            <h3>
                            ✅ Application created successfully
                            </h3>

                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        st.markdown(
                            "### 🆔 Your Application ID"
                        )

                        st.code(
                            application[
                                "application_id"
                            ],
                            language=None
                        )

                        if expected_completion:

                            st.info(
                                f"Expected completion: "
                                f"**{expected_completion}**"
                            )

                        st.success(
                            "You can now open the "
                            "**Track Status** tab."
                        )

                    except sqlite3.IntegrityError:

                        st.error(
                            "Could not save the application. "
                            "Please try again."
                        )

                else:

                    st.error(
                        result.get(
                            "error",
                            "Application creation failed."
                        )
                    )


# ============================================================
# TRACKING TAB
# ============================================================

with tracking_tab:

    st.header(
        "📊 Track Application"
    )

    default_id = st.session_state.get(
        "last_application_id",
        ""
    )

    tracking_id = st.text_input(
        "Application ID",
        value=default_id,
        placeholder="NS-YYYYMMDD-XXXXXXXX"
    )

    track = st.button(
        "🔍 Track Application",
        type="primary",
        use_container_width=True
    )

    if track:

        application = load_application(
            tracking_id.strip()
        )

        if not application:

            st.error(
                "No application was found with that ID."
            )

        else:

            status_result = fetch_status(
                application
            )

            if status_result["success"]:

                current_status = (
                    status_result["status"]
                )

                if current_status != (
                    application["status"]
                ):

                    update_application(
                        application[
                            "application_id"
                        ],
                        status=current_status
                    )

                    application[
                        "status"
                    ] = current_status

            st.markdown(
                f"## {application['service_name']}"
            )

            c1, c2, c3 = st.columns(3)

            with c1:

                st.metric(
                    "Status",
                    application["status"]
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

            st.divider()

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

                submission_date = parse_date(
                    application[
                        "submission_date"
                    ]
                )

                if timeline_type == "calendar_days":

                    deadline = (
                        submission_date
                        + timedelta(
                            days=
                            int(
                                processing_days
                            )
                        )
                    )

                else:

                    deadline = (
                        add_working_days(
                            submission_date,
                            int(
                                processing_days
                            )
                        )
                    )

                c1, c2, c3 = st.columns(3)

                with c1:

                    st.markdown(
                        f"""
                        <div class="timeline-card">

                        <div class="timeline-number">
                        {processing_days}
                        </div>

                        <div class="timeline-label">
                        Official processing days
                        </div>

                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with c2:

                    st.markdown(
                        f"""
                        <div class="timeline-card">

                        <div class="timeline-number">
                        {remaining}
                        </div>

                        <div class="timeline-label">
                        Remaining days
                        </div>

                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with c3:

                    st.markdown(
                        f"""
                        <div class="timeline-card">

                        <div class="timeline-number">
                        {deadline.strftime("%d %b")}
                        </div>

                        <div class="timeline-label">
                        Expected completion
                        </div>

                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                completed = max(
                    0,
                    processing_days - remaining
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
                    "No exact official processing timeline "
                    "has been recorded for this application."
                )

            st.divider()

            st.subheader(
                "Application details"
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
                "official_source"
            ):

                st.write(
                    f"**Official source:** "
                    f"{application['official_source']}"
                )

            if application.get(
                "government_reference"
            ):

                st.write(
                    f"**Government reference:** "
                    f"{application['government_reference']}"
                )


# ============================================================
# RECENT APPLICATIONS
# ============================================================

st.divider()

st.subheader(
    "🗂️ Recent applications"
)

recent = get_recent_applications(
    5
)

if recent:

    for item in recent:

        application_id = item[0]
        service_name = item[1]
        status = item[2]
        submitted = item[3]

        with st.expander(
            f"{service_name} • {application_id}"
        ):

            st.write(
                f"**Status:** {status}"
            )

            st.write(
                f"**Submitted:** {submitted}"
            )

else:

    st.caption(
        "Your applications will appear here."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "🤖 NextStep AI • Intelligent public-service workflow"
)

st.caption(
    "AI identifies services and assists with preparation. "
    "External government submission/status requires an "
    "authorized government integration."
)
