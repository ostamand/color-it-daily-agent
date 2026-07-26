from google.cloud import firestore
from color_it_daily_agent.app_configs import configs

_db = None


def get_db():
    global _db
    if _db is None:
        project_id = configs.firestore_project_id or configs.gcp_project
        if project_id:
            _db = firestore.Client(project=project_id)
        else:
            _db = firestore.Client()
    return _db
