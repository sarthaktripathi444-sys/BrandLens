# database.py
# Connects to MongoDB and exposes the collections BrandLens uses.
# If MongoDB cannot be reached, it falls back to an in-memory database so the demo still runs.

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import DB_NAME, MONGO_URI, USE_MEMORY_DB


def _memory_client(reason):
    """A fake MongoDB that lives in RAM. All data is lost when the server restarts."""
    import mongomock  # imported here so it is only needed for the fallback

    print(f"[database] {reason}. Using the in-memory database (data resets on restart).")
    return mongomock.MongoClient()


def _connect():
    """Try the real MongoDB first; use the in-memory one if it is not reachable."""
    if USE_MEMORY_DB:
        return _memory_client("USE_MEMORY_DB is set")

    real_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    try:
        real_client.admin.command("ping")  # a quick "are you there?" check
        print("[database] Connected to MongoDB.")
        return real_client
    except PyMongoError as error:
        real_client.close()
        return _memory_client(f"MongoDB is not reachable ({type(error).__name__})")


client = _connect()
database = client[DB_NAME]

# The three collections (like tables):
rulebooks = database["rulebooks"]  # every uploaded rule book; exactly one has active=True
contents = database["contents"]    # submitted content + its status and score
reviews = database["reviews"]      # the AI findings for a piece of content
audit_events = database["audit_events"]  # append-only log of everything that happens to a piece of content

def close_database():
    """Called when the server shuts down."""
    client.close()


def strip_id(doc):
    """MongoDB adds an internal '_id' that cannot be sent as JSON; remove it."""
    return {key: value for key, value in doc.items() if key != "_id"}
