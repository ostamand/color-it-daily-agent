#!/usr/bin/env python3
"""
Seed Collections Script (PostgreSQL -> Firestore)

Connects to the PostgreSQL database, retrieves all collections from the `collections` table,
maps the columns (display_name -> name, sub_heading -> description, background_url -> image_url),
and seeds/upserts them into the Firestore `coloritdaily_collections` collection.

Usage:
  python seed_collections.py [--dry-run]
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load .env files (check local .env and sibling backend .env)
load_dotenv("/home/ostamand/git/color-it-daily-agent/.env")
load_dotenv("/home/ostamand/git/coloring-pages/backend/.env")

import psycopg2
import psycopg2.extras

from color_it_daily_agent.lib.database import get_db
from color_it_daily_agent.app_configs import configs
from color_it_daily_agent.lib.collections import COLLECTIONS_FIRESTORE_COLLECTION, DEFAULT_CREATIVE_SKILL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_collections")


def get_pg_connection():
    host = os.environ.get("POSTGRES_HOST") or os.environ.get("DB_HOSTNMAME") or os.environ.get("DB_HOSTNAME") or "localhost"
    port = int(os.environ.get("POSTGRES_PORT") or os.environ.get("DB_PORT") or 5432)
    dbname = os.environ.get("POSTGRES_DB") or os.environ.get("DB_NAME") or "coloring_pages"
    user = os.environ.get("POSTGRES_USER") or os.environ.get("DB_USER") or "postgres"
    password = os.environ.get("POSTGRES_PASSWORD") or os.environ.get("DB_PASSWORD") or ""

    logger.info(f"Connecting to PostgreSQL at {host}:{port}/{dbname} (user: {user})...")
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn


def get_default_skill_for_collection(name: str, display_name: str) -> str:
    name_lower = (name or "").lower()
    disp_lower = (display_name or "").lower()

    if "pirate" in name_lower or "pirate" in disp_lower:
        return "Pirate Adventure Line Art – Playful, bold outlines featuring friendly pirates, treasure maps, ships, and sea adventures suitable for children."
    elif "halloween" in name_lower or "halloween" in disp_lower:
        return "Creepy-Cute Halloween Line Art – Whimsical, non-scary Halloween line art featuring friendly ghosts, cute pumpkins, and innocent magical creatures."
    elif "alphabet" in name_lower or "alphabet" in disp_lower:
        return "Educational Alphabet Line Art – Clear, bold, simple line art focusing on A-Z objects and letters designed for easy coloring and learning."
    elif "holiday" in name_lower or "holiday" in disp_lower:
        return "Festive Holiday Line Art – Cozy, festive line art with winter magic, holiday traditions, and joyous seasonal themes."
    
    return DEFAULT_CREATIVE_SKILL


def seed_collections(dry_run: bool = False):
    conn = get_pg_connection()
    cursor = conn.cursor()

    logger.info("Fetching collections from PostgreSQL 'collections' table...")
    try:
        cursor.execute("""
            SELECT * FROM collections;
        """)
        rows = cursor.fetchall()
def get_default_context_for_collection(name: str, display_name: str) -> str:
    name_lower = (name or "").lower()
    disp_lower = (display_name or "").lower()
    if "pirate" in name_lower or "pirate" in disp_lower:
        return "A swashbuckling, child-safe sea adventure collection featuring brave little pirate captains, friendly sea creatures, island treasure hunts, and cozy shipboard life. Every page captures joyful maritime discoveries with bold, uncluttered outlines."
    elif "halloween" in name_lower or "halloween" in disp_lower:
        return "A whimsical 'creepy-cute' autumn collection centered around cheerful midnight magic, cozy pumpkin patches, friendly trick-or-treating woodland animals, and playful non-scary ghosts. Every page highlights comforting fall themes with zero frightening elements."
    elif "alphabet" in name_lower or "alphabet" in disp_lower:
        return "An engaging early-learning collection pairing giant, colorable letter forms with delightful matching subjects doing fun activities (e.g., A for Astronaut Bear, B for Baker Bunny). Every page balances educational clarity with playful storybook illustrations."
    elif "holiday" in name_lower or "holiday" in disp_lower:
        return "A festive seasonal collection celebrating winter magic, joyful family traditions, gift-giving, gingerbread treats, and cozy snowy wonderlands. Every page evokes warmth, celebration, and holiday cheer."
    return "A rich daily storybook collection combining unexpected animal mashups, magical micro-worlds, and cozy architectural wonderlands. Every page tells a miniature story designed to spark childhood imagination and offer satisfying coloring regions."

def seed_collections(dry_run: bool = False):
    conn = get_pg_connection()
    cursor = conn.cursor()

    logger.info("Fetching collections from PostgreSQL 'collections' table...")
    try:
        cursor.execute("""
            SELECT * FROM collections;
        """)
        rows = cursor.fetchall()
    except Exception as e:
        logger.error(f"Failed to query PostgreSQL collections table: {e}")
        conn.close()
        sys.exit(1)

    logger.info(f"Retrieved {len(rows)} collection(s) from PostgreSQL.\n")

    if not rows:
        logger.warning("No collections found in PostgreSQL table.")
        conn.close()
        return

    db = None
    if not dry_run:
        db = get_db()
        target_project = configs.firestore_project_id or configs.gcp_project
        logger.info(f"Connected to Firestore project '{target_project}', collection '{COLLECTIONS_FIRESTORE_COLLECTION}'.\n")

    success_count = 0
    for row in rows:
        cid = str(row.get("id"))
        slug_name = row.get("name") or f"collection-{cid}"
        display_name = row.get("display_name") or slug_name
        heading = row.get("heading") or ""
        sub_heading = row.get("sub_heading") or ""
        
        frontend_description = sub_heading or heading or f"A collection of {display_name} coloring pages."
        agent_context = get_default_context_for_collection(slug_name, display_name)
        image_url = row.get("background_url")
        is_active = True

        creative_skill = row.get("creative_skill") or get_default_skill_for_collection(slug_name, display_name)
        
        created_on = row.get("created_on")
        created_at = created_on.isoformat() if hasattr(created_on, "isoformat") else datetime.now(timezone.utc).isoformat()

        doc_data = {
            "id": cid,
            "name": display_name,
            "slug": slug_name,
            "heading": heading,
            "description": frontend_description,
            "context": agent_context,
            "image_url": image_url,
            "is_active": is_active,
            "creative_skill": creative_skill,
            "created_at": created_at,
            "updated_at": created_at,
        }

        logger.info(f"📦 Collection: '{display_name}' (slug: '{slug_name}', id: {cid})")
        logger.info(f"   Frontend Description: {frontend_description}")
        logger.info(f"   Agent Context: {agent_context}")
        logger.info(f"   Creative Skill: {creative_skill}")

        if dry_run:
            logger.info(f"   [DRY-RUN] Would write document to Firestore '{COLLECTIONS_FIRESTORE_COLLECTION}/{slug_name}'\n")
        else:
            try:
                # Write single canonical document indexed by slug_name
                db.collection(COLLECTIONS_FIRESTORE_COLLECTION).document(slug_name).set(doc_data, merge=True)
                success_count += 1
                logger.info(f"   ✅ Successfully written document '{slug_name}' to Firestore.\n")
            except Exception as e:
                logger.error(f"   ❌ Failed to write to Firestore: {e}\n")

    conn.close()

    if dry_run:
        logger.info(f"🎉 [DRY-RUN COMPLETE] Evaluated {len(rows)} collection(s). No changes written to Firestore.")
    else:
        logger.info(f"🎉 [SEEDING COMPLETE] Successfully seeded {success_count}/{len(rows)} collection(s) to Firestore.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed collections from PostgreSQL to Firestore")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to Firestore")
    args = parser.parse_args()

    seed_collections(dry_run=args.dry_run)
