"""Role-specific legal documents. DRAFT: replace and formally approve before deployment."""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/legal", tags=["Legal documents"])
DOCS = json.loads(Path(__file__).with_name("legal_documents_catalog.json").read_text(encoding="utf-8"))
ROLES = {"client", "driver", "navigator", "dispatcher", "admin"}

@router.get("/roles/{role}")
def list_documents(role: str):
    if role not in ROLES: raise HTTPException(404, "Unknown role")
    return [{k:v for k,v in d.items() if k != "body"} for d in DOCS if d["role"] in {role, "common"}]

@router.get("/roles/{role}/{document_id}")
def document_text(role: str, document_id: str):
    for item in DOCS:
        if item["role"] in {role, "common"} and item["id"] == document_id: return item
    raise HTTPException(404, "Document not found")

def validate_acceptances(role: str, acceptances: list[dict]) -> list[dict]:
    if role not in ROLES: raise ValueError("Unknown role")
    ids = [item.get("id") for item in acceptances]
    if len(set(ids)) != len(ids): raise ValueError("Duplicate acceptance")
    valid = {d["id"]:d for d in DOCS if d["role"] == role}
    # Common references are readable, not acceptance/consent checkboxes.
    checked = {}
    for item in acceptances:
        doc = valid.get(item.get("id"))
        if doc is None: raise ValueError("Unknown document")
        if item.get("version") != doc["version"] or item.get("sha256") != doc["sha256"]:
            raise ValueError("Outdated document version")
        if item.get("accepted") is not True: raise ValueError("Only affirmative selections may be sent")
        checked[doc["id"]] = {"id": doc["id"], "version":doc["version"], "sha256":doc["sha256"]}
    if any(d["required"] and d["id"] not in checked for d in valid.values()):
        raise ValueError("Required documents not accepted")
    return list(checked.values())
