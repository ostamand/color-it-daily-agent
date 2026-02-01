import psycopg2
from datetime import datetime

PAGES_TABLE = "pages"
PAGE_TAGS_TABLE = "page_tags"
TAGS_TABLE = "tags"
COLLECTIONS_TABLE = "collections"

COLORING_PAGE_COLLECTION_NAME="wonder-daily"
COLORING_PAGE_COLLECTION_DISPLAY_NAME="Wonder Daily"


def get_page_unique_name(cursor, name: str) -> str:
    """
    Generates a unique slug for the page name.
    Replicates logic: lowercase, replace spaces with '-', remove "'s", append counter if exists.
    """
    if not name:
        base_name = "sample"
    else:
        base_name = name.lower().replace(" ", "-").replace("'s", "")
    
    # Check for existing unique_names starting with this base
    # distinct from the Deno script which checks 'LIKE base_name%', we can be more specific
    # Deno: WHERE unique_name LIKE '${uniqueName}%'
    query = f"SELECT unique_name FROM {PAGES_TABLE} WHERE unique_name LIKE %s"
    cursor.execute(query, (f"{base_name}%",))
    rows = cursor.fetchall()
    
    existing_names = {row[0] for row in rows}
    
    if base_name not in existing_names:
        return base_name
    
    # If exists, find the next number
    count = 1
    while True:
        candidate = f"{base_name}-{count}"
        if candidate not in existing_names:
            return candidate
        count += 1

def ensure_tags_exist(cursor, tags: list[str]) -> list[tuple[str, int]]:
    """
    Ensures all tags exist in the 'tags' table.
    Returns a list of (tag_name, tag_id).
    """
    if not tags:
        return []

    # 1. Find existing tags
    cursor.execute(f"SELECT name, id FROM {TAGS_TABLE} WHERE name = ANY(%s)", (tags,))
    existing_tags = cursor.fetchall() # [(name, id), ...]
    existing_map = {row[0]: row[1] for row in existing_tags}
    
    result = []
    for tag_name in tags:
        if tag_name in existing_map:
            result.append((tag_name, existing_map[tag_name]))
        else:
            # Create new tag
            cursor.execute(f"INSERT INTO {TAGS_TABLE} (name) VALUES (%s) RETURNING id", (tag_name,))
            new_id = cursor.fetchone()[0]
            result.append((tag_name, new_id))
            
    return result

def get_collection_by_name(cursor, collection_name: str):
    """
    Attempts to fetch collection details. 
    Returns dict with 'name' and 'display_name' or None.
    """
    # Assuming a 'collections' table exists based on Deno script usage
    try:
        cursor.execute(f"SELECT name, display_name FROM {COLLECTIONS_TABLE} WHERE name = %s", (collection_name,))
        row = cursor.fetchone()
        if row:
            return {"name": row[0], "display_name": row[1]}
    except psycopg2.Error:
        # If table doesn't exist or other error, ignore
        pass
    return None

def add_new_page(cursor, page_data: dict):
    """
    Inserts a new page and its tags into the database.
    """
    # Unpack data
    full_path = page_data['full_path']
    thumbnail_path = page_data['thumbnail_path']
    generate_script = page_data.get('generate_script', None)
    prompt = page_data.get('prompt', '')
    seed = page_data.get('seed', None) # likely None
    generated_on = page_data.get('generated_on', datetime.now())
    created_on = datetime.now()
    name = page_data['name']
    model_name = page_data.get('model_name', 'unknown')
    prompt_model_name = page_data.get('prompt_model_name', 'unknown') # Optional
    height = page_data.get('height', 3300)
    width = page_data.get('width', 2550)
    colored_path = page_data.get('colored_path', None)
    tags = page_data.get('tags', [])
    reasoning = page_data.get("reasoning", None)
    
    upd_collection_name = COLORING_PAGE_COLLECTION_NAME
    display_collection_name = COLORING_PAGE_COLLECTION_DISPLAY_NAME

    # 2. Get Unique Name
    unique_name = get_page_unique_name(cursor, name)
    
    # 3. Insert Page
    insert_query = f"""
        INSERT INTO {PAGES_TABLE} (
            full_path, 
            thumbnail_path, 
            generate_script,
            prompt, 
            seed, 
            collection_name, 
            generated_on, 
            created_on,
            name, 
            model_name, 
            prompt_model_name,
            height, 
            width, 
            unique_name,
            upd_collection_name,
            colored_path,
            published,
            reasoning
        ) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false, %s) 
        RETURNING id
    """

    cursor.execute(insert_query, (
        full_path,
        thumbnail_path,
        generate_script,
        prompt,
        seed,
        display_collection_name,
        generated_on,
        created_on,
        name,
        model_name,
        prompt_model_name,
        height,
        width,
        unique_name,
        upd_collection_name,
        colored_path,
        reasoning
    ))
    
    page_id = cursor.fetchone()[0]
    
    # 4. Handle Tags
    tag_list = ensure_tags_exist(cursor, tags)
    for _, tag_id in tag_list:
        cursor.execute(f"INSERT INTO {PAGE_TAGS_TABLE} (page_id, tag_id) VALUES (%s, %s)", (page_id, tag_id))
        
    return page_id
