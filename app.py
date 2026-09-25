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
# CONFIG
# ============================================================

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


# ============================================================
# SECRETS
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

if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_service" not in st.session_state:
    st.session_state.selected_service = None

if "requirements" not in st.session_state:
    st.session_state.requirements = []

if "timeline_result" not in st.session_state:
    st.session_state.timeline_result = None

if "language" not in st.session_state:
    st.session_state.language = "English"

if "last_application_id" not in st.session_state:
    st.session_state.last_application_id = ""


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
                "service_category",
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
            application["applicant_name"],
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
# RECENT APPLICATIONS
# ============================================================

def get_recent_applications(limit=5):

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
    count = 0

    while count < number_of_days:

        current += timedelta(days=1)

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
# URL FUNCTIONS
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

        hostname = urlparse(
            url
        ).hostname

        if not hostname:
            return False

        hostname = hostname.lower()

    except Exception:

        return False

    endings = [
        ".gov",
        ".gov.in",
        ".nic.in",
        ".ac.in"
    ]

    return any(
        hostname.endswith(
            ending
        )
        for ending in endings
    )


# ============================================================
# OPENROUTER
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
                    "No response was returned by the AI."
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
You are the main intelligence engine of NextStep AI.

Identify the government or public service requested by
the user.

Preferred language:
{language}

Do not invent facts.

If the jurisdiction cannot be determined, use "Unknown".

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
You are the requirements assistant for NextStep AI.

Service:
{service_name}

Jurisdiction:
{jurisdiction}

Language:
{language}

Generate likely information and documents needed.

Do not present AI-generated information as official
legal requirements.

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
        "data": data
    }


# ============================================================
# OFFICIAL WEBPAGE READER
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
            "text": text[:18000]
        }

    except Exception as error:

        return {
            "success": False,
            "error":
                f"Unable to read webpage: {error}"
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
You verify government processing timelines.

Use ONLY the supplied official webpage content.

Find an explicitly stated processing time.

Examples:

7 working days
15 days
within 30 calendar days

Never infer a timeline.

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

Official webpage:
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

    if not isinstance(
        data,
        dict
    ):

        return {
            "success": False,
            "verified": False,
            "error":
                "Could not interpret the official webpage."
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
            "data": data
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
        "data": data
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
# SUBMISSION
# ============================================================

def submit_application(
    application
):

    if GOVERNMENT_SUBMISSION_URL:

        payload = {
            "service_name":
                application[
                    "service_name"
                ],
            "jurisdiction":
                application[
                    "jurisdiction"
                ],
            "department":
                application.get(
                    "department",
                    ""
                ),
            "applicant_name":
                application[
                    "applicant_name"
                ],
            "applicant_data":
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
# STATUS
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
# SIMPLE CSS
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

    section[data-testid="stSidebar"] * {
        color: white !important;
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
        "Intelligent government services assistant"
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

    st.subheader(
        "System"
    )

    if OPENROUTER_API_KEY:

        st.success(
            "AI connected"
        )

    else:

        st.error(
            "Add OpenRouter API key"
        )

    st.divider()

    st.caption(
        "Discover services • Prepare applications • Track progress"
    )


# ============================================================
# HOME
# ============================================================

st.title(
    "🤖 NextStep AI"
)

st.subheader(
    "Your intelligent government-services assistant"
)

st.write(
    "Discover public services, understand requirements, "
    "prepare applications and track your progress from one place."
)

st.divider()

feature1, feature2, feature3 = st.columns(3)

with feature1:

    st.subheader(
        "🔎 Discover"
    )

    st.write(
        "Describe the government service you need "
        "in natural language."
    )


with feature2:

    st.subheader(
        "📋 Prepare"
    )

    st.write(
        "Let AI organize the information and "
        "requirements needed for your application."
    )


with feature3:

    st.subheader(
        "⏳ Track"
    )

    st.write(
        "Get an application ID and monitor "
        "processing progress."
    )


st.divider()


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
        "Tell NextStep AI what you want to apply for."
    )

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):

            st.markdown(
                message["content"]
            )

    prompt = st.chat_input(
        "Example: I need a birth certificate"
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

                st.session_state.selected_service = (
                    service
                )

                service_name = service.get(
                    "service_name",
                    "Unknown"
                )

                category = service.get(
                    "service_category",
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

                intent = service.get(
                    "intent",
                    "Application"
                )

                st.success(
                    "Service identified"
                )

                col1, col2 = st.columns(2)

                with col1:

                    st.write(
                        f"**Service:** {service_name}"
                    )

                    st.write(
                        f"**Category:** {category}"
                    )

                with col2:

                    st.write(
                        f"**Jurisdiction:** {jurisdiction}"
                    )

                    st.write(
                        f"**Department:** {department}"
                    )

                st.write(
                    f"**Request type:** {intent}"
                )

                if service.get(
                    "explanation"
                ):

                    st.info(
                        service[
                            "explanation"
                        ]
                    )

                with st.spinner(
                    "Finding likely requirements..."
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

                    st.subheader(
                        "📋 Likely requirements"
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

                        label = (
                            "Required"
                            if required
                            else "Optional"
                        )

                        st.write(
                            f"**{name}** • {label}"
                        )

                        if description:

                            st.caption(
                                description
                            )

                response = (
                    f"I identified your request as "
                    f"**{service_name}**. "
                    f"Continue in the **Application** tab."
                )

                st.success(
                    response
                )

            else:

                response = (
                    "I could not identify the service. "
                    + result.get(
                        "error",
                        "Please try again."
                    )
                )

                st.error(
                    response
                )

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
        "📝 Prepare your application"
    )

    service = (
        st.session_state.selected_service
    )

    if not service:

        st.info(
            "First describe the government service "
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

        st.subheader(
            "Selected service"
        )

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Service",
                service_name
            )

        with c2:

            st.metric(
                "Jurisdiction",
                jurisdiction
            )

        with c3:

            st.metric(
                "Department",
                department
            )

        st.divider()

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

        additional_information = st.text_area(
            "Additional information"
        )

        st.subheader(
            "🔎 Official service information"
        )

        st.write(
            "Enter the official service webpage "
            "if you want NextStep AI to verify the "
            "published processing timeline."
        )

        official_url = st.text_input(
            "Official government service URL",
            placeholder="https://..."
        )

        verify = st.button(
            "Verify Official Timeline",
            use_container_width=True
        )

        if verify:

            if not official_url:

                st.warning(
                    "Please enter the official service URL."
                )

                st.session_state.timeline_result = None

            elif not valid_url(
                official_url
            ):

                st.error(
                    "Please enter a valid URL."
                )

                st.session_state.timeline_result = None

            elif not official_domain(
                official_url
            ):

                st.warning(
                    "Please use an official government "
                    "or public-sector webpage."
                )

                st.session_state.timeline_result = None

            else:

                with st.spinner(
                    "Checking the official webpage..."
                ):

                    timeline_result = verify_timeline(
                        service_name,
                        jurisdiction,
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

                days = timeline[
                    "processing_days"
                ]

                timeline_type = timeline[
                    "timeline_type"
                ]

                st.success(
                    f"Official processing timeline: "
                    f"{days} "
                    f"{timeline_type.replace('_', ' ')}"
                )

            else:

                st.info(
                    "An exact processing timeline "
                    "was not found on the supplied "
                    "official webpage."
                )

        st.divider()

        st.subheader(
            "🔐 Review and authorize"
        )

        with st.expander(
            "Review your information",
            expanded=True
        ):

            st.write(
                f"**Name:** {applicant_name}"
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
                f"{additional_information}"
            )

        authorization = st.checkbox(
            "I have reviewed the information and authorize NextStep AI to create this application."
        )

        submit = st.button(
            "🚀 Submit Application",
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

            if not authorization:

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

                    "applicant_data": {

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
                        "Application Submitted",

                    "created_at":
                        datetime.now().isoformat(),

                    "updated_at":
                        datetime.now().isoformat()
                }

                with st.spinner(
                    "Processing application..."
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
                            ],
                            language=None
                        )

                        if expected_completion:

                            st.info(
                                f"Expected completion date: "
                                f"**{expected_completion}**"
                            )

                        st.success(
                            "Open the Track Status tab "
                            "to follow this application."
                        )

                    except sqlite3.IntegrityError:

                        st.error(
                            "Unable to save this application."
                        )

                else:

                    st.error(
                        result.get(
                            "error",
                            "Application submission failed."
                        )
                    )


# ============================================================
# TRACK STATUS
# ============================================================

with tracking_tab:

    st.header(
        "📊 Track your application"
    )

    tracking_id = st.text_input(
        "Application ID",
        value=st.session_state.last_application_id,
        placeholder="NS-YYYYMMDD-XXXXXXXX"
    )

    track = st.button(
        "🔍 Track Application",
        type="primary",
        use_container_width=True
    )

    if track:

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

                if status_result["success"]:

                    current_status = (
                        status_result[
                            "status"
                        ]
                    )

                    application[
                        "status"
                    ] = current_status

                st.success(
                    "Application found."
                )

                st.subheader(
                    application[
                        "service_name"
                    ]
                )

                c1, c2, c3 = st.columns(3)

                with c1:

                    st.metric(
                        "Status",
                        application[
                            "status"
                        ]
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
                            "Official processing time",
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
                        "is available for this application."
                    )

                st.divider()

                st.subheader(
                    "Application information"
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

recent = get_recent_applications()

if recent:

    for item in recent:

        with st.expander(
            f"{item[1]} • {item[0]}"
        ):

            st.write(
                f"**Application ID:** {item[0]}"
            )

            st.write(
                f"**Status:** {item[2]}"
            )

            st.write(
                f"**Submitted:** {item[3]}"
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
    "🤖 NextStep AI"
)

st.caption(
    "Discover services • Prepare applications • Track progress"
)
