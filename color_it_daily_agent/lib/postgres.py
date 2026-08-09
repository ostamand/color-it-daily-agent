import os
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from contextlib import contextmanager
import psycopg2
import psycopg2.pool
from ..app_configs import configs

logger = logging.getLogger(__name__)

PAGES_TABLE = "pages"
PAGE_TAGS_TABLE = "page_tags"
TAGS_TABLE = "tags"
ORGANIZATION_USERS_TABLE = "organization_users"

_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def setup_database_pool(minconn: int = 1, maxconn: int = 10) -> Optional[psycopg2.pool.ThreadedConnectionPool]:
    """
    Initializes a global PostgreSQL connection pool.
    Replicates the setupDatabasePool pattern used in coloring-pages/backend.
    """
    global _pool
    if _pool is not None and not _pool.closed:
        return _pool

    host = configs.postgres_host or os.environ.get("POSTGRES_HOST")
    port = configs.postgres_port or os.environ.get("POSTGRES_PORT", "5432")
    db = configs.postgres_db or os.environ.get("POSTGRES_DB")
    user = configs.postgres_user or os.environ.get("POSTGRES_USER")
    password = configs.postgres_password or os.environ.get("POSTGRES_PASSWORD")

    if not host or not db or not user:
        logger.warning("PostgreSQL configuration missing or incomplete; pool cannot be initialized.")
        return None

    try:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            host=host,
            port=port,
            dbname=db,
            user=user,
            password=password
        )
        logger.info(f"Initialized PostgreSQL connection pool (host={host}, min={minconn}, max={maxconn})")
        return _pool
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
        return None


def get_pool() -> Optional[psycopg2.pool.ThreadedConnectionPool]:
    """Returns the active database pool, initializing it if necessary."""
    global _pool
    if _pool is None or _pool.closed:
        return setup_database_pool()
    return _pool


@contextmanager
def get_postgres_connection():
    """
    Context manager that gets a connection from the pool and releases it back to the pool when done.
    Usage:
        with get_postgres_connection() as conn:
            if conn:
                cursor = conn.cursor()
                ...
    """
    pool = get_pool()
    if not pool:
        yield None
        return

    conn = None
    try:
        conn = pool.getconn()
        yield conn
    except Exception as e:
        logger.error(f"Error acquiring connection from pool: {e}")
        yield None
    finally:
        if conn and pool and not pool.closed:
            pool.putconn(conn)


def close_database_pool():
    """Closes all connections in the pool."""
    global _pool
    if _pool is not None and not _pool.closed:
        _pool.closeall()
        _pool = None
        logger.info("Closed PostgreSQL connection pool.")


def slugify(text: str) -> str:
    """
    Generates a clean URL slug.
    Replaces special characters, spaces, and consecutive hyphens with a single hyphen.
    """
    if not text:
        return ""
    s = text.lower().replace("'s", "").replace("'", "")
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def get_page_unique_name(cursor, name: str) -> str:
    """
    Generates a unique slug for the page name.
    Replicates logic: clean slugify, append counter if exists.
    """
    base_name = slugify(name) or "sample"
    
    query = f"SELECT unique_name FROM {PAGES_TABLE} WHERE unique_name LIKE %s"
    cursor.execute(query, (f"{base_name}%",))
    rows = cursor.fetchall()
    
    existing_names = {row[0] for row in rows}
    
    if base_name not in existing_names:
        return base_name
    
    count = 1
    while True:
        candidate = f"{base_name}-{count}"
        if candidate not in existing_names:
            return candidate
        count += 1


def ensure_tags_exist(cursor, tags: List[str]) -> List[Tuple[str, int]]:
    """
    Ensures all tags exist in the 'tags' table.
    Returns a list of (tag_name, tag_id).
    """
    if not tags:
        return []

    cursor.execute(f"SELECT name, id FROM {TAGS_TABLE} WHERE name = ANY(%s)", (tags,))
    existing_tags = cursor.fetchall()
    existing_map = {row[0]: row[1] for row in existing_tags}
    
    result = []
    for tag_name in tags:
        if tag_name in existing_map:
            result.append((tag_name, existing_map[tag_name]))
        else:
            cursor.execute(f"INSERT INTO {TAGS_TABLE} (name) VALUES (%s) RETURNING id", (tag_name,))
            new_id = cursor.fetchone()[0]
            result.append((tag_name, new_id))
            
    return result


def lookup_user_id_by_email(user_email: str) -> Optional[int]:
    """
    Looks up user_id from organization_users by email.
    """
    if not user_email or not str(user_email).strip():
        return None

    with get_postgres_connection() as conn:
        if not conn:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT id FROM {ORGANIZATION_USERS_TABLE} WHERE email = %s LIMIT 1", (str(user_email).strip(),))
            row = cursor.fetchone()
            if row:
                return row[0]
        except Exception as e:
            logger.warning(f"Could not look up user_id for email '{user_email}': {e}")
        finally:
            cursor.close()

    return None


def lookup_user_email_by_id(user_id: int) -> Optional[str]:
    """
    Looks up user_email from organization_users by user_id.
    """
    if not user_id:
        return None

    with get_postgres_connection() as conn:
        if not conn:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute(f"SELECT email FROM {ORGANIZATION_USERS_TABLE} WHERE id = %s LIMIT 1", (user_id,))
            row = cursor.fetchone()
            if row:
                return row[0]
        except Exception as e:
            logger.warning(f"Could not look up user_email for user_id '{user_id}': {e}")
        finally:
            cursor.close()

    return None


def lookup_user_by_email(user_email: str) -> Optional[Tuple[int, int, str]]:
    """
    Looks up (user_id, org_id, email) from organization_users by email.
    Returns None if not found.
    """
    if not user_email or not str(user_email).strip():
        return None

    with get_postgres_connection() as conn:
        if not conn:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SELECT id, org_id, email FROM {ORGANIZATION_USERS_TABLE} WHERE email = %s LIMIT 1",
                (str(user_email).strip(),)
            )
            row = cursor.fetchone()
            if row:
                return row[0], row[1], row[2]
        except Exception as e:
            logger.warning(f"Could not look up user for email '{user_email}': {e}")
        finally:
            cursor.close()

    return None


def lookup_user_by_id(user_id: int) -> Optional[Tuple[int, int, str]]:
    """
    Looks up (user_id, org_id, email) from organization_users by user_id.
    Returns None if not found.
    """
    if not user_id:
        return None

    with get_postgres_connection() as conn:
        if not conn:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SELECT id, org_id, email FROM {ORGANIZATION_USERS_TABLE} WHERE id = %s LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return row[0], row[1], row[2]
        except Exception as e:
            logger.warning(f"Could not look up user for user_id '{user_id}': {e}")
        finally:
            cursor.close()

    return None


def lookup_user_id(cursor, user_email: Optional[str]) -> Optional[int]:
    """
    Looks up user_id in organization_users table using email.
    """
    if not user_email:
        return None

    try:
        cursor.execute(f"SELECT id FROM {ORGANIZATION_USERS_TABLE} WHERE email = %s LIMIT 1", (user_email,))
        row = cursor.fetchone()
        if row:
            return row[0]
    except Exception as e:
        logger.warning(f"Could not look up user_id for '{user_email}': {e}")

    return None


def add_new_page(cursor, page_data: Dict[str, Any]) -> int:
    """
    Inserts a new page and its tags into the database.
    """
    full_path = page_data['full_path']
    thumbnail_path = page_data['thumbnail_path']
    generate_script = page_data.get('generate_script', None)
    prompt = page_data.get('prompt', '')
    seed = page_data.get('seed', None)
    generated_on = page_data.get('generated_on') or datetime.now()
    created_on = datetime.now()
    name = page_data['name']
    model_name = page_data.get('model_name', 'unknown')
    prompt_model_name = page_data.get('prompt_model_name', 'unknown')
    height = page_data.get('height', 3300)
    width = page_data.get('width', 2550)
    colored_path = page_data.get('colored_path', None)
    tags = page_data.get('tags', [])
    reasoning = page_data.get("reasoning", None)
    target_audience = page_data.get("target_audience", None)
    collection_unique_name = page_data.get('collection_unique_name', None)
    micro_style = page_data.get('micro_style', None)

    user_email = page_data.get('user_email', None)
    document_id = page_data.get('document_id', None)

    user_id = page_data.get('user_id', None)
    if not user_id and user_email:
        user_id = lookup_user_id(cursor, user_email)

    user_flag = bool(user_id is not None or page_data.get('user', False))

    unique_name = get_page_unique_name(cursor, name)
    
    insert_query = f"""
        INSERT INTO {PAGES_TABLE} (
            full_path, 
            thumbnail_path, 
            generate_script,
            prompt, 
            seed, 
            generated_on, 
            created_on,
            name, 
            model_name, 
            prompt_model_name,
            height, 
            width, 
            unique_name,
            collection_unique_name,
            colored_path,
            published,
            reasoning,
            target_audience,
            micro_style,
            user_id,
            "user",
            document_id
        ) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false, %s, %s, %s, %s, %s, %s) 
        RETURNING id
    """

    cursor.execute(insert_query, (
        full_path,
        thumbnail_path,
        generate_script,
        prompt,
        seed,
        generated_on,
        created_on,
        name,
        model_name,
        prompt_model_name,
        height,
        width,
        unique_name,
        collection_unique_name,
        colored_path,
        reasoning,
        target_audience,
        micro_style,
        user_id,
        user_flag,
        document_id
    ))
    
    page_id = cursor.fetchone()[0]
    
    tag_list = ensure_tags_exist(cursor, tags)
    for _, tag_id in tag_list:
        cursor.execute(f"INSERT INTO {PAGE_TAGS_TABLE} (page_id, tag_id) VALUES (%s, %s)", (page_id, tag_id))
        
    return page_id


def publish_to_postgres(page_data: Dict[str, Any]) -> Optional[int]:
    """
    Wrapper function to handle connection pool lifecycle and insert page into Postgres.
    Returns page_id if successful, or None if skipped/failed.
    """
    with get_postgres_connection() as conn:
        if not conn:
            logger.info("Postgres connection not established. Skipping Postgres publish.")
            return None

        cursor = conn.cursor()
        try:
            page_id = add_new_page(cursor, page_data)
            conn.commit()
            logger.info(f"Successfully inserted page '{page_data.get('name')}' into Postgres with ID {page_id}")
            return page_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to insert page into Postgres: {e}")
            return None
        finally:
            cursor.close()
