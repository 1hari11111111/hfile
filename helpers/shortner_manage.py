"""
Shortener Management Helper
CRUD operations for the shorteners collection.
Multiple shorteners can be active at the same time — random selection
at link-generation time distributes traffic evenly.
"""
from database.database import shortener_col


async def add_shortener(name: str, api_url: str, api_key: str) -> dict:
    """
    Add or update a shortener by name.
    New shorteners are inactive by default.
    """
    if shortener_col.find_one({"name": name}):
        shortener_col.update_one(
            {"name": name},
            {"$set": {"api_url": api_url, "api_key": api_key}}
        )
        return {"ok": True, "action": "updated"}

    shortener_col.insert_one({
        "name": name,
        "api_url": api_url,
        "api_key": api_key,
        "active": False
    })
    return {"ok": True, "action": "added"}


async def toggle_shortener(name: str) -> dict:
    """
    Toggle the active state of a shortener (activate if inactive, deactivate if active).
    Multiple shorteners can be active at once.
    """
    doc = shortener_col.find_one({"name": name})
    if not doc:
        return {"ok": False, "error": "Shortener not found."}

    new_state = not doc.get("active", False)
    shortener_col.update_one({"name": name}, {"$set": {"active": new_state}})
    return {"ok": True, "active": new_state}


async def remove_shortener(name: str) -> dict:
    """Delete a shortener by name."""
    result = shortener_col.delete_one({"name": name})
    if result.deleted_count:
        return {"ok": True}
    return {"ok": False, "error": "Shortener not found."}


async def update_shortener_field(name: str, field: str, value: str) -> dict:
    """Update a single field (api_url or api_key) of an existing shortener."""
    if not shortener_col.find_one({"name": name}):
        return {"ok": False, "error": "Shortener not found."}
    shortener_col.update_one({"name": name}, {"$set": {field: value}})
    return {"ok": True}


async def list_shorteners() -> list:
    """Return all shorteners (without _id)."""
    return list(shortener_col.find({}, {"_id": 0}))


async def get_shortener_by_name(name: str) -> dict | None:
    return shortener_col.find_one({"name": name}, {"_id": 0})
