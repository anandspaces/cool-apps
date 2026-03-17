import pandas as pd

# Load Spotify listening behavior dataset
df = pd.read_csv("dataset/spotify_listening_behavior_500k.csv")

# Build one record per user: stable id = user_id, text = searchable description
def row_to_text(row):
    """Build a searchable text description of a user's listening behavior."""
    parts = [
        f"Age {row['user_age']}, {row['country']}, {row['subscription_type']}, {row['device_type']}.",
        f"Favorite genre: {row['favorite_genre']}. {row['playlist_count']} playlists, {row['liked_songs']} liked songs.",
        f"Daily listening: {row['daily_listening_minutes']} min, monthly: {row['monthly_listening_hours']:.1f} hours.",
        f"Skip rate {row['skip_rate']:.2f}, repeat rate {row['repeat_song_rate']:.2f}, discovery rate {row['music_discovery_rate']:.2f}.",
        f"Ads per hour: {row['ads_per_hour']}, typical hour: {row['typical_listening_hour']}, avg session: {row['avg_session_length_minutes']} min.",
        f"Weekend usage ratio: {row['weekend_usage_ratio']:.2f}. Timestamp: {row['timestamp']}.",
    ]
    return " ".join(parts)

all_chunks = df.apply(row_to_text, axis=1).tolist()

# Build metadata from dataframe (one record per user)
records = df.to_dict(orient="records")
chunk_metadata = []
for r in records:
    r = r.copy()
    user_id = r["user_id"]
    r["chunk_id"] = user_id
    r["source_id"] = user_id
    # Ensure numeric types
    for k in ("user_age", "playlist_count", "liked_songs", "daily_listening_minutes", "ads_per_hour", "typical_listening_hour", "avg_session_length_minutes"):
        r[k] = int(r[k])
    for k in ("monthly_listening_hours", "skip_rate", "repeat_song_rate", "music_discovery_rate", "weekend_usage_ratio"):
        r[k] = float(r[k])
    r["timestamp"] = str(r["timestamp"])
    chunk_metadata.append(r)

# Lookup by chunk_id (here = user_id) for vector DB and retrieval
chunk_by_id = {m["chunk_id"]: m for m in chunk_metadata}
text_by_id = {m["chunk_id"]: all_chunks[i] for i, m in enumerate(chunk_metadata)}

print(f"Loaded {len(all_chunks)} user profiles from Spotify listening behavior dataset")
print(f"Example chunk_id (user_id): {chunk_metadata[0]['chunk_id']}")
print(f"Example text (first 200 chars): {all_chunks[0][:200]}...")
