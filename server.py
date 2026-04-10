import os, json, requests, random
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
from ytmusicapi import YTMusic

app = Flask(__name__)
CORS(app)
ytmusic = YTMusic(language='en', location='IN')

GEMINI_KEY = os.getenv("GEMINI_KEY", "AIzaSyAg7g8iSQjwLMoHIMyiaSSGqqVMpElfvlw")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"

# ── TASTE MEMORY ─────────────────────────────
def save_taste(artist, title=""):
    try:
        taste = {}
        if os.path.exists('taste.json'):
            with open('taste.json', 'r') as f: taste = json.load(f)
        taste[artist] = taste.get(artist, 0) + 1
        history = taste.get('_history', [])
        history.insert(0, {'artist': artist, 'title': title})
        taste['_history'] = history[:50]
        with open('taste.json', 'w') as f: json.dump(taste, f)
    except: pass

def load_taste():
    try:
        if os.path.exists('taste.json'):
            with open('taste.json', 'r') as f: return json.load(f)
    except: pass
    return {}

def ask_gemini(prompt, timeout=8):
    try:
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(GEMINI_URL, json=payload, timeout=timeout)
        return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

def format_results(data):
    res = []
    for s in data:
        try:
            thumb = s['thumbnails'][-1]['url'] if s.get('thumbnails') else ""
            if "googleusercontent" in thumb:
                thumb = thumb.split('=')[0] + "=w600-h600-l90-rj"
            res.append({
                "id": s['videoId'],
                "title": s['title'],
                "artist": s['artists'][0]['name'] if s.get('artists') else "Unknown",
                "thumbnail": thumb
            })
        except: pass
    return res

# ── HOME ─────────────────────────────────────
@app.route('/')
def home():
    return send_file('Jaatplayer final red backup.html')

@app.route('/sw.js')
def service_worker():
    return send_file('sw.js', mimetype='application/javascript')

# ── AI RECOMMEND ─────────────────────────────
@app.route('/ai_recommend')
def ai_recommend():
    taste = load_taste()
    top_artists = sorted(
        {k: v for k, v in taste.items() if not k.startswith('_')}.items(),
        key=lambda x: x[1], reverse=True
    )[:5]
    top_names = [a[0] for a in top_artists] if top_artists else []
    history = taste.get('_history', [])
    recent = history[0]['artist'] if history else 'Karan Aujla'

    prompt = f"User's top artists: {top_names}. Recently played: {recent}. Suggest ONE artist name for music recommendation. Same language as recent songs. Just the name only."
    query = ask_gemini(prompt) or recent

    try:
        results = ytmusic.search(query.strip(), filter="songs")
        return jsonify({"results": format_results(results[:20])})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── SEARCH ───────────────────────────────────
@app.route('/search')
def search():
    query = request.args.get('name', '').strip()
    if not query: return jsonify({"error": "No query"}), 400
    try:
        results = ytmusic.search(query, filter="songs")
        return jsonify({"results": format_results(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── GET AUDIO URL ─────────────────────────────
@app.route('/get_url')
def get_url():
    video_id = request.args.get('id', '').strip()
    artist   = request.args.get('artist', '')
    title    = request.args.get('title', '')
    if not video_id: return jsonify({"error": "No ID"}), 400
    if artist: save_taste(artist, title)
    try:
                ydl_opts = {
            'format': 'bestaudio/best', # pick the best working stream
            'quiet': True,
            'nocheckcertificate': True,
            'cookiefile': 'cookies.txt', # uses your session
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}}, # signature fix
            'js_runtimes': {'node': {'path': 'node'}} # allows Node.js to run
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            return jsonify({"url": info.get('url')})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── SMART QUEUE ───────────────────────────────
@app.route('/smart_queue')
def smart_queue():
    title   = request.args.get('title', '').strip()
    artist  = request.args.get('artist', '').strip()
    song_id = request.args.get('id', '').strip()

    taste = load_taste()

    # Top 8 artists by play count
    top_artists = sorted(
        {k: v for k, v in taste.items() if not k.startswith('_')}.items(),
        key=lambda x: x[1], reverse=True
    )[:8]
    top_names = [a[0] for a in top_artists]

    # Recent history
    history = taste.get('_history', [])
    recent_artists = list(dict.fromkeys([h.get('artist','') for h in history[:10]]))

    # Known similar artists map — fallback if Gemini fails
    similar_map = {
        'Karan Aujla':   ['AP Dhillon','Sidhu Moosewala','Shubh','Diljit Dosanjh','Divine'],
        'AP Dhillon':    ['Karan Aujla','Gurinder Gill','Shubh','The Weeknd','Drake'],
        'Sidhu Moosewala':['Karan Aujla','Diljit Dosanjh','Ninja','Parmish Verma'],
        'Diljit Dosanjh':['Gurdas Maan','Ammy Virk','Jassie Gill','Karan Aujla'],
        'Arijit Singh':  ['Jubin Nautiyal','Atif Aslam','Armaan Malik','KK'],
        'Jubin Nautiyal':['Arijit Singh','Armaan Malik','Darshan Raval','Atif Aslam'],
        'Badshah':       ['Honey Singh','Yo Yo Honey Singh','Divine','Raftaar'],
        'Divine':        ['Naezy','Raftaar','Badshah','Seedhe Maut'],
        'Shreya Ghoshal':['Sunidhi Chauhan','Neha Kakkar','Monali Thakur'],
        'Shubh':         ['AP Dhillon','Karan Aujla','The Weeknd','Drake'],
    }
    fallback_similar = similar_map.get(artist, [])

    # Build Gemini prompt — force variety
    prompt = f"""You are a music recommendation AI like Spotify Radio.

Current song: "{title}" by {artist}
User's most played artists: {top_names}
User's recently played artists: {recent_artists}

Generate EXACTLY 6 search queries for YouTube Music to build a smart radio queue.
STRICT RULES:
1. Maximum 1 query can be about "{artist}" — rest must be DIFFERENT artists
2. Match the MOOD and ENERGY and LANGUAGE of "{title}" by {artist}
3. Include artists similar to {artist} that user might like
4. If user has taste history, include 1-2 queries from their top artists
5. Keep same language (Punjabi→Punjabi, Hindi→Hindi, English→English)
6. Make queries specific like "artist name best songs" or "song name artist"
7. Return ONLY a valid JSON array of 6 strings. No explanation. No markdown.

Example format: ["query1","query2","query3","query4","query5","query6"]"""

    queries = None
    gemini_reply = ask_gemini(prompt, timeout=10)

    if gemini_reply:
        try:
            clean = gemini_reply.replace('```json','').replace('```','').strip()
            # Find the JSON array in response
            start = clean.find('[')
            end = clean.rfind(']') + 1
            if start != -1 and end > start:
                parsed = json.loads(clean[start:end])
                if isinstance(parsed, list) and len(parsed) >= 3:
                    queries = parsed
                    print(f"Gemini queries: {queries}")
        except Exception as e:
            print(f"Gemini parse error: {e} | Reply: {gemini_reply}")

    # Fallback if Gemini failed
    if not queries:
        print("Using fallback queries")
        queries = []
        # 1 query from same artist
        queries.append(f"{artist} best songs")
        # Rest from similar artists
        if fallback_similar:
            for sim in fallback_similar[:3]:
                queries.append(f"{sim} best songs")
        # Fill remaining from user taste
        for ta in top_names[:3]:
            if ta != artist and ta not in queries:
                queries.append(f"{ta} hits")
        # Safety net
        if len(queries) < 4:
            queries += ["Punjabi hits 2024", "Trending Punjabi songs"]

    # Fetch songs for each query — ensure variety across artists
    all_results = []
    seen_ids = {song_id}
    seen_artists = {}  # Track how many songs per artist

    for q in queries:
        try:
            results = ytmusic.search(q.strip(), filter="songs")
            formatted = format_results(results)
            added = 0
            for s in formatted:
                sid = s['id']
                sartist = s['artist']
                # Max 4 songs per artist to ensure variety
                if sid not in seen_ids and seen_artists.get(sartist, 0) < 4:
                    seen_ids.add(sid)
                    seen_artists[sartist] = seen_artists.get(sartist, 0) + 1
                    all_results.append(s)
                    added += 1
                if added >= 5: break  # Max 5 per query
        except Exception as e:
            print(f"Query failed '{q}': {e}")

        if len(all_results) >= 30: break

    # Shuffle slightly for natural feel — but keep first few relevant
    if len(all_results) > 6:
        first = all_results[:3]
        rest = all_results[3:]
        random.shuffle(rest)
        all_results = first + rest

    print(f"Smart queue built: {len(all_results)} songs, artists: {list(seen_artists.keys())}")
    return jsonify({"results": all_results[:30]})

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)