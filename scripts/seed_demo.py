"""
DocuFlow AI - demo data seeder
==============================

Creates ONE ready-to-use demo account with realistic documents and tasks,
all through the real public API (nothing is written straight into the
database, so every row is exactly what the app itself produces).

    email      : demo@docuflow.ai
    password   : Demo12345!

Run it AFTER the backend is listening on port 8001:

    python scripts/seed_demo.py

It is idempotent: running it twice does not create duplicates (the
register call is answered with 409 and the script simply signs in).
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8001/api"

DEMO_EMAIL = "demo@docuflow.ai"
DEMO_PASSWORD = "Demo12345!"
DEMO_NAME = "Demo User"

# Realistic sample documents. The Mock AI engine turns these into
# summaries, entities, priorities and action items.
DOCUMENTS = [
    {
        "title": "Northwind Vendor Contract",
        "text": (
            "URGENT: The Northwind Supplies vendor contract expires on 31 January 2027 "
            "and requires renewal approval. Please review clause 7 (data processing) and "
            "send the revised pricing schedule to procurement@northwind.example.com before "
            "20 December 2026. Total annual contract value is $84,500. "
            "Reference number NW-CTR-2026-4410. Contact the Legal Department immediately "
            "to approve the indemnity wording. Our account manager can be reached on "
            "+1 412 555 0143."
        ),
        "notes": "Renewal decision needed before the December board meeting.",
    },
    {
        "title": "Q4 Infrastructure Review",
        "text": (
            "Quarterly infrastructure review for Q4 2026. The migration to the new cluster "
            "is 78 percent complete and remains on schedule. Storage costs increased to "
            "$12,750 per month, up from $11,200. Two incidents were recorded, both resolved "
            "within the four hour target. The team should prepare a rollback plan before "
            "the next phase begins on 15 February 2027. Owner: devops-lead@example.org."
        ),
        "notes": "",
    },
    {
        "title": "Product Onboarding Notes",
        "text": (
            "Customer onboarding for Acme Corp finished successfully. The client completed "
            "all six training modules and confirmed the SSO integration works. "
            "Suggested follow-up: schedule a check-in call in early March 2027 and share "
            "the advanced reporting guide with their team. Contact: "
            "maya.singh@acmecorp.example.com. Overall sentiment is positive."
        ),
        "notes": "",
    },
]

# Tasks are created straight through the task API (mixed statuses so the
# board and the charts have something to show).
TASKS = [
    {
        "title": "Send revised pricing to Northwind procurement",
        "description": "Attach the updated schedule and clause 7 redlines.",
        "priority": "High",
        "status": "in_review",
        "assigned_to": "Demo User",
        "due_date": "2026-12-20",
    },
    {
        "title": "Prepare rollback plan for cluster phase 2",
        "description": "Must be reviewed before the 15 February cutover.",
        "priority": "Medium",
        "status": "pending",
        "assigned_to": "Platform Team",
        "due_date": "2027-02-01",
    },
    {
        "title": "Share advanced reporting guide with Acme Corp",
        "description": "Requested by the client during onboarding wrap-up.",
        "priority": "Low",
        "status": "completed",
        "assigned_to": "Demo User",
        "due_date": "2026-11-14",
    },
    {
        "title": "Review indemnity wording with Legal",
        "description": "Clause 7 and 9 need a second read before signing.",
        "priority": "High",
        "status": "pending",
        "assigned_to": "Legal Department",
        "due_date": "2026-12-28",
    },
]


def request(method: str, path: str, payload=None, token: str | None = None, form: bool = False):
    """Tiny urllib wrapper so the seeder needs no extra dependencies."""
    url = f"{BASE}{path}"
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        if form:
            # multipart/form-data built by hand (text fields only)
            boundary = "----docuflowseed"
            parts = []
            for key, value in payload.items():
                if value is None:
                    continue
                parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                    f"{value}\r\n"
                )
            data = ("".join(parts) + f"--{boundary}--\r\n").encode("utf-8")
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        else:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:          # API answered with an error
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"detail": body}
    except urllib.error.URLError as exc:           # API not running at all
        print(f"\n  Cannot reach the backend at {url}")
        print(f"  -> {exc.reason}")
        print("  Start it first:  python -m uvicorn app.main:app --port 8001\n")
        sys.exit(1)


def wait_for_backend(attempts: int = 20) -> None:
    print("Waiting for the backend on port 8001", end="", flush=True)
    for _ in range(attempts):
        status, _body = request("GET", "/health")
        if status == 200:
            print("  ready.")
            return
        print(".", end="", flush=True)
        time.sleep(1)
    print("\n  Backend did not become healthy in time.")
    sys.exit(1)


def main() -> None:
    wait_for_backend()

    # ---------------- 1. account ----------------
    status, body = request(
        "POST", "/auth/register",
        {
            "full_name": DEMO_NAME,
            "email": DEMO_EMAIL,
            "password": DEMO_PASSWORD,
            # The API requires the confirmation field (mirrors the UI form).
            "confirm_password": DEMO_PASSWORD,
        },
    )
    if status == 201:
        print(f"[1/4] Created account  {DEMO_EMAIL}")
    elif status in (400, 409):
        print(f"[1/4] Account already exists  {DEMO_EMAIL}")
    else:
        print(f"[1/4] Register failed ({status}): {body.get('detail')}")
        sys.exit(1)

    status, auth = request(
        "POST", "/auth/login", {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    )
    if status != 200:
        print(f"[1/4] Login failed ({status}): {auth.get('detail')}")
        sys.exit(1)
    token = auth["access_token"]
    print("      signed in.")

    # ---------------- 2. documents ----------------
    # Skip if the demo account already has documents (keeps re-runs clean).
    status, listing = request("GET", "/documents?page_size=1", token=token)
    if status == 200 and listing.get("total", 0) > 0:
        print(f"[2/4] {listing['total']} document(s) already present - skipping.")
        doc_ids = [d["id"] for d in request("GET", "/documents?page_size=50", token=token)[1]["items"]]
    else:
        doc_ids = []
        for index, doc in enumerate(DOCUMENTS, start=1):
            status, created = request(
                "POST", "/documents/analyze",
                {"text": doc["text"], "title": doc["title"]},
                token=token, form=True,
            )
            if status != 201:
                print(f"[2/4] Analyse failed for {doc['title']!r} ({status}): {created.get('detail')}")
                sys.exit(1)
            document = created["document"]
            doc_ids.append(document["id"])
            print(
                f"[2/4] {index}/{len(DOCUMENTS)} analyzed  "
                f"{document['title']!r}  [{document['category']} · {document['priority']}] "
                f"via {created['ai_provider']}"
            )
            if doc.get("notes"):
                request(
                    "PUT", f"/documents/{document['id']}",
                    {"user_notes": doc["notes"]}, token=token,
                )

    # ---------------- 3. tasks ----------------
    status, task_listing = request("GET", "/tasks?page_size=1", token=token)
    if status == 200 and task_listing.get("total", 0) > 0:
        print(f"[3/4] {task_listing['total']} task(s) already present - skipping.")
    else:
        for index, task in enumerate(TASKS, start=1):
            payload = dict(task)
            # Attach the first task to a document so the relationship is visible.
            if index == 1 and doc_ids:
                payload["document_id"] = doc_ids[0]
            status, created = request("POST", "/tasks", payload, token=token)
            if status != 201:
                print(f"[3/4] Task failed ({status}): {created.get('detail')}")
                sys.exit(1)
            print(f"[3/4] {index}/{len(TASKS)} created  {task['title']!r} ({task['status']})")

    # ---------------- 4. summary ----------------
    _, stats = request("GET", "/dashboard/stats", token=token)
    print("[4/4] Dashboard stats:")
    print(f"        documents     = {stats.get('total_documents')}")
    print(f"        pending tasks = {stats.get('pending_tasks')}")
    print(f"        completed     = {stats.get('completed_tasks')}")

    print("\n" + "=" * 62)
    print("  DEMO ACCOUNT READY")
    print(f"  email    : {DEMO_EMAIL}")
    print(f"  password : {DEMO_PASSWORD}")
    print("  open     : http://localhost:5173/login")
    print("=" * 62)


if __name__ == "__main__":
    main()
