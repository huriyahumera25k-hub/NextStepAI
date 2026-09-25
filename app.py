import streamlit as st
import requests
import json
import re
import sqlite3
import os
import uuid
import base64
from datetime import datetime, date, timedelta
from urllib.parse import urlparse, quote_plus, unquote


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
    "official_url_candidates": [],

    "application_id": None,
    "submission_result": None,

    "last_ai_response": "",

    "portal_status": None
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
        values = json.loads(HOLIDAYS_RAW)

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

            real_submission INTEGER,

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

    conn = sqlite3.connect(DATABASE_FILE)

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

            real_submission,

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
            ?,
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

            application["real_submission"],

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

            real_submission,

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

        "real_submission",

        "created_at",
        "updated_at"
    ]

    return dict(zip(columns, row))


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
        return json.loads(text.strip())

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
            "error":
                "OPENROUTER_API_KEY is not configured."
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
                "error":
                    f"OpenRouter error "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
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
You are NextStep AI, an intelligent government-service
navigation assistant.

Identify the government/public service requested by the citizen.

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
    "country": "",
    "department": "",
    "intent": "",
    "confidence": 0,
    "search_query": "",
    "explanation": ""
}}

Rules:

- Identify the most likely service.
- Identify the likely country and jurisdiction.
- Do not invent an exact department.
- Use "Unknown" when necessary.
- confidence must be between 0 and 1.
- search_query must be a concise web-search query
  for finding the official government service portal.
- Do not put a fake URL in this response.
"""

    result = call_ai(
        [
            {
                "role": "system",
                "content":
                    "Accurately identify government services."
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
# OFFICIAL DOMAIN CHECK
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

        hostname = hostname.rstrip(".")

        official_patterns = [
            r"\.gov\.in$",
            r"\.nic\.in$",
            r"\.gov$",
            r"\.gov\.[a-z]{2}$",
            r"\.gouv\.fr$",
            r"\.gc\.ca$",
            r"\.gov\.uk$",
            r"\.gov\.au$",
            r"\.gov\.nz$",
            r"\.gov\.sg$",
            r"\.go\.jp$",
            r"\.gov\.ae$",
            r"\.gov\.sa$"
        ]

        for pattern in official_patterns:

            if re.search(pattern, hostname):
                return True

        return False

    except Exception:

        return False


# ============================================================
# URL NORMALIZATION
# ============================================================

def normalize_url(url):

    if not url:
        return ""

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


# ============================================================
# SEARCH FOR OFFICIAL PORTAL
# ============================================================

def search_official_portals(
    search_query
):

    if not search_query:
        return {
            "success": False,
            "error": "No search query was generated.",
            "results": []
        }

    search_url = (
        "https://html.duckduckgo.com/html/?q="
        + quote_plus(search_query)
    )

    try:

        response = requests.get(
            search_url,
            headers={
                "User-Agent":
                    "Mozilla/5.0 NextStepAI/1.0"
            },
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:

            return {
                "success": False,
                "error":
                    "Official portal search failed.",
                "results": []
            }

        html = response.text

        matches = re.findall(
            r'nofollow" class="result__a" href="([^"]+)"',
            html
        )

        results = []

        for raw_url in matches:

            url = unquote(raw_url)

            if "uddg=" in url:

                try:
                    url = url.split(
                        "uddg=",
                        1
                    )[1]

                    url = unquote(
                        url.split("&", 1)[0]
                    )

                except Exception:
                    continue

            url = normalize_url(url)

            if is_official_url(url):

                if url not in results:

                    results.append(url)

            if len(results) >= 5:
                break

        if not results:

            return {
                "success": False,
                "error":
                    "No verified official government portal "
                    "was found.",
                "results": []
            }

        return {
            "success": True,
            "results": results
        }

    except requests.exceptions.Timeout:

        return {
            "success": False,
            "error":
                "Portal search timed out.",
            "results": []
        }

    except Exception as e:

        return {
            "success": False,
            "error":
                f"Portal search error: {str(e)}",
            "results": []
        }


# ============================================================
# FIND OFFICIAL SERVICE PORTAL
# ============================================================

def find_official_service_portal(
    service
):

    search_query = service.get(
        "search_query",
        ""
    )

    if not search_query:

        search_query = (
            service.get("service_name", "")
            + " "
            + service.get("jurisdiction", "")
            + " official government portal"
        )

    result = search_official_portals(
        search_query
    )

    if not result["success"]:

        return result

    candidates = result["results"]

    # Let AI select the most relevant result.
    candidate_text = "\n".join(
        f"{index + 1}. {url}"
        for index, url in enumerate(candidates)
    )

    prompt = f"""
Select the most relevant official government service portal.

Service:
{service.get("service_name", "")}

Jurisdiction:
{service.get("jurisdiction", "")}

Country:
{service.get("country", "")}

Candidate official URLs:
{candidate_text}

Return ONLY JSON:

{{
    "selected_url": "",
    "reason": ""
}}

Select ONLY one URL from the candidate list.
Never invent or modify a URL.
"""

    ai_result = call_ai(
        [
            {
                "role": "system",
                "content":
                    "Select the correct official government portal."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=500
    )

    if ai_result["success"]:

        selected = safe_json(
            ai_result["content"],
            {}
        )

        selected_url = normalize_url(
            selected.get(
                "selected_url",
                ""
            )
        )

        if (
            selected_url
            and selected_url in candidates
            and is_official_url(selected_url)
        ):

            return {
                "success": True,
                "official_url": selected_url,
                "candidates": candidates,
                "reason":
                    selected.get(
                        "reason",
                        ""
                    )
            }

    # Safe fallback
    return {
        "success": True,
        "official_url": candidates[0],
        "candidates": candidates,
        "reason":
            "Selected from verified official-domain results."
    }


# ============================================================
# CHECK OFFICIAL PAGE
# ============================================================

def read_official_page(url):

    if not is_official_url(url):

        return {
            "success": False,
            "error":
                "The URL is not recognized as an official "
                "government domain."
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
# REQUIREMENTS
# ============================================================

def generate_requirements(
    service,
    language
):

    prompt = f"""
Prepare useful requirements for this government service.

Service:
{service.get("service_name", "Unknown")}

Category:
{service.get("service_category", "Unknown")}

Jurisdiction:
{service.get("jurisdiction", "Unknown")}

Department:
{service.get("department", "Unknown")}

Official portal:
{service.get("official_url", "Unknown")}

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

Do not falsely claim something is officially required.
If uncertain, clearly say it must be verified on the official portal.
"""

    result = call_ai(
        [
            {
                "role": "system",
                "content":
                    "Explain government service requirements carefully."
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
            st.write(description)

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
            st.warning(warning)

    note = requirements.get(
        "verification_note",
        ""
    )

    if note:
        st.info(note)


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

Official page text:
{page["text"]}

Look ONLY for an explicitly stated processing timeline.

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
                    "Verify official government processing timelines."
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

        current += timedelta(days=1)

        if is_working_day(current):
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

    try:
        days = int(processing_days)
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

            current += timedelta(days=1)

            if is_working_day(current):
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

    # --------------------------------------------------------
    # AUTHORIZED GOVERNMENT API
    # --------------------------------------------------------

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
                    "real_submission": False,
                    "error":
                        f"Government API returned HTTP "
                        f"{response.status_code}."
                }

            try:
                data = response.json()
            except Exception:
                data = {}

            application_id = (
                data.get("application_id")
                or data.get("applicationId")
                or data.get("reference_number")
                or data.get("referenceNumber")
                or data.get("id")
            )

            if not application_id:

                return {
                    "success": False,
                    "real_submission": False,
                    "error":
                        "Government API accepted the request "
                        "but did not return an application ID."
                }

            return {
                "success": True,
                "real_submission": True,
                "application_id": str(application_id),
                "status": data.get(
                    "status",
                    "Submitted"
                ),
                "message": data.get(
                    "message",
                    "Application submitted successfully."
                )
            }

        except requests.exceptions.RequestException as e:

            return {
                "success": False,
                "real_submission": False,
                "error":
                    f"Government submission error: {str(e)}"
            }

    # --------------------------------------------------------
    # NO AUTHORIZED API
    # --------------------------------------------------------

    return {
        "success": False,
        "real_submission": False,
        "requires_portal":
            True,
        "error":
            "No authorized government API is configured "
            "for this service."
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
                        f"Status API returned HTTP "
                        f"{response.status_code}."
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
            "Status is stored locally. "
            "Connect the authorized government status "
            "API for live government status."
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
            "text": transcript
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

    .portal-box {
        padding: 20px;
        border-radius: 16px;
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

        **3. Official Portal**

        NextStep AI finds the official
        government service portal.

        **4. Choose**

        Choose whether to apply yourself
        or let NextStep AI prepare/submit.

        **5. Track**

        Track the application when an
        authorized status integration exists.
        """
    )

    st.divider()

    if GOVERNMENT_SUBMISSION_URL:

        st.success(
            "🟢 Authorized submission API configured"
        )

    else:

        st.info(
            "🟡 Portal/API handoff mode"
        )

    if GOVERNMENT_STATUS_URL:

        st.success(
            "🟢 Live status API configured"
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
    # TEXT
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
                ] = ""

                st.session_state[
                    "official_url_candidates"
                ] = []

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

                    **Country**

                    {service.get(
                        "country",
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

            if service.get("explanation"):

                st.info(
                    service["explanation"]
                )

            # ====================================================
            # FIND PORTAL
            # ====================================================

            if not st.session_state.get(
                "official_url"
            ):

                if st.button(
                    "🌐 Find Official Service Portal",
                    type="primary",
                    use_container_width=True,
                    key="find_portal"
                ):

                    with st.spinner(
                        "Finding the official government portal..."
                    ):

                        portal_result = (
                            find_official_service_portal(
                                service
                            )
                        )

                    if portal_result["success"]:

                        st.session_state[
                            "official_url"
                        ] = portal_result[
                            "official_url"
                        ]

                        st.session_state[
                            "official_url_candidates"
                        ] = portal_result.get(
                            "candidates",
                            []
                        )

                        st.success(
                            "✅ Official government portal found."
                        )

                        st.rerun()

                    else:

                        st.error(
                            portal_result["error"]
                        )

            # ====================================================
            # OFFICIAL PORTAL
            # ====================================================

            official_url = st.session_state.get(
                "official_url",
                ""
            )

            if official_url:

                st.divider()

                st.subheader(
                    "🏛️ Official Service Portal"
                )

                st.markdown(
                    f"""
                    <div class="portal-box">

                    <b>Verified official-domain portal</b>

                    <br><br>

                    {official_url}

                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.link_button(
                    "🌐 Open Official Government Portal",
                    official_url,
                    use_container_width=True
                )

                candidates = st.session_state.get(
                    "official_url_candidates",
                    []
                )

                if len(candidates) > 1:

                    with st.expander(
                        "View other verified official results"
                    ):

                        for candidate in candidates:

                            st.markdown(
                                f"- {candidate}"
                            )

            # ====================================================
            # APPLICATION MODE
            # ====================================================

            st.divider()

            st.subheader(
                "🚀 What would you like NextStep AI to do?"
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
                    "📋 No, just show me the portal",
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
            # NO MODE
            # ====================================================

            if st.session_state.get(
                "application_decision"
            ) == "no":

                st.info(
                    "📋 You chose to apply yourself."
                )

                if not official_url:

                    st.warning(
                        "An official service portal could not "
                        "be verified automatically."
                    )

                else:

                    if st.session_state.get(
                        "requirements"
                    ) is None:

                        with st.spinner(
                            "Preparing service requirements..."
                        ):

                            requirements = generate_requirements(
                                {
                                    **service,
                                    "official_url":
                                        official_url
                                },
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

                    st.divider()

                    st.success(
                        "No applicant information was collected."
                    )

                    st.link_button(
                        "🚀 Apply on the Official Government Portal",
                        official_url,
                        use_container_width=True
                    )

            # ====================================================
            # YES MODE
            # ====================================================

            if st.session_state.get(
                "application_mode",
                False
            ):

                st.success(
                    "🟢 Application Mode is active."
                )

                if not official_url:

                    st.warning(
                        "NextStep AI could not verify an official "
                        "service portal yet."
                    )

                    st.info(
                        "Find the official portal before continuing."
                    )

                else:

                    st.markdown(
                        """
                        NextStep AI will:

                        **1️⃣ Verify the service portal**

                        **2️⃣ Check requirements**

                        **3️⃣ Collect required information**

                        **4️⃣ Review the application**

                        **5️⃣ Request authorization**

                        **6️⃣ Submit through an authorized API if available**

                        **7️⃣ Otherwise hand you safely to the official portal**
                        """
                    )

                    st.link_button(
                        "🌐 View Official Service Portal",
                        official_url,
                        use_container_width=True
                    )

                    if st.session_state.get(
                        "requirements"
                    ) is None:

                        with st.spinner(
                            "Preparing application requirements..."
                        ):

                            requirements = generate_requirements(
                                {
                                    **service,
                                    "official_url":
                                        official_url
                                },
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

    if not st.session_state.get(
        "application_mode",
        False
    ):

        st.info(
            "Application Mode is not active."
        )

        st.write(
            "Go to the **🤖 Assistant** tab, identify a "
            "service, and select **✅ Yes, apply for me**."
        )

    else:

        service = st.session_state.get(
            "identified_service"
        )

        official_url = st.session_state.get(
            "official_url",
            ""
        )

        if not service:

            st.warning(
                "No service has been identified."
            )

        elif not official_url:

            st.warning(
                "No verified official service portal "
                "has been found."
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

                **Official Portal:** {official_url}
                """
            )

            st.link_button(
                "🌐 Open Official Portal",
                official_url,
                use_container_width=True
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
                        st.error(error)

                else:

                    # ------------------------------------------------
                    # TIMELINE
                    # ------------------------------------------------

                    timeline = verify_timeline(
                        official_url,
                        service.get(
                            "service_name",
                            "Unknown"
                        )
                    )

                    if timeline.get(
                        "success",
                        False
                    ) and timeline.get(
                        "verified",
                        False
                    ):

                        st.session_state[
                            "timeline"
                        ] = timeline

                        processing_days = int(
                            timeline.get(
                                "processing_days",
                                0
                            )
                        )

                        processing_type = (
                            timeline.get(
                                "processing_type",
                                "calendar_days"
                            )
                        )

                        timeline_source = (
                            timeline.get(
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

                    submission_date = date.today()

                    expected_date = (
                        calculate_expected_date(
                            submission_date,
                            processing_days,
                            processing_type
                        )
                    )

                    # ------------------------------------------------
                    # PAYLOAD
                    # ------------------------------------------------

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

                            "country":
                                service.get(
                                    "country",
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
                            official_url,

                        "submission_date":
                            submission_date.isoformat()
                    }

                    # ------------------------------------------------
                    # REAL API SUBMISSION
                    # ------------------------------------------------

                    with st.spinner(
                        "Checking authorized submission integration..."
                    ):

                        result = submit_application(
                            payload
                        )

                    # =================================================
                    # API AVAILABLE
                    # =================================================

                    if result["success"]:

                        application_id = result[
                            "application_id"
                        ]

                        status = result.get(
                            "status",
                            "Submitted"
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
                                official_url,

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

                            "real_submission":
                                1,

                            "created_at":
                                now,

                            "updated_at":
                                now
                        }

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
                            "🎉 Application submitted through "
                            "the configured authorized integration."
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

                        if expected_date:

                            st.info(
                                "Expected completion: "
                                + format_date(
                                    expected_date
                                )
                            )

                        st.success(
                            "➡️ Open the **🔎 Application Status** tab "
                            "to track it."
                        )

                    # =================================================
                    # NO API
                    # =================================================

                    else:

                        if result.get(
                            "requires_portal",
                            False
                        ):

                            st.warning(
                                "⚠️ No authorized automated submission "
                                "integration is configured for this "
                                "government service."
                            )

                            st.info(
                                "NextStep AI will not pretend that "
                                "your application was submitted. "
                                "You can safely continue on the "
                                "official government portal."
                            )

                            st.link_button(
                                "🚀 Continue on Official Government Portal",
                                official_url,
                                use_container_width=True
                            )

                            st.caption(
                                "Your application has NOT been submitted "
                                "by NextStep AI."
                            )

                        else:

                            st.error(
                                result.get(
                                    "error",
                                    "Application submission failed."
                                )
                            )


# ============================================================
# APPLICATION STATUS TAB
# ============================================================

with tab_status:

    st.header(
        "🔎 Application Status"
    )

    st.write(
        "Enter your application ID to check status "
        "and processing time."
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
        placeholder="NS-20260926-XXXXXXXX"
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

                st.subheader(
                    "📌 Current Application Status"
                )

                current_status = status_result.get(
                    "status",
                    "Status unavailable"
                )

                current_status_lower = (
                    str(current_status).lower()
                )

                if current_status_lower in {
                    "approved",
                    "completed",
                    "delivered"
                }:

                    st.success(
                        f"✅ {current_status}"
                    )

                elif current_status_lower in {
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

                if status_result.get("message"):

                    st.caption(
                        status_result["message"]
                    )

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

                    st.divider()

                    st.subheader(
                        "⏳ Processing Timeline"
                    )

                    if application["processing_days"]:

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
                                    str(remaining)
                                )

                        with col2:

                            st.metric(
                                "Official Timeline",
                                f"{application['processing_days']} day(s)"
                            )

                        with col3:

                            if expected:

                                st.metric(
                                    "Expected Completion",
                                    format_date(expected)
                                )

                        if remaining is not None:

                            if remaining > 0:

                                st.success(
                                    f"⏳ Approximately {remaining} "
                                    f"day(s) remaining according to "
                                    f"the verified processing timeline."
                                )

                            else:

                                st.warning(
                                    "⚠️ The official processing "
                                    "timeline has been reached."
                                )

                    else:

                        st.info(
                            "A dynamic countdown is unavailable "
                            "because no official processing timeline "
                            "was verified."
                        )

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
                        "status system, but local application "
                        "details are unavailable."
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
