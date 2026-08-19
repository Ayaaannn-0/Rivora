import os
import json
import hashlib
import difflib
from datetime import datetime, timedelta
import re
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from groq import Groq
from dotenv import load_dotenv

import config

load_dotenv()

app = Flask(__name__)

DATA_FILE = 'data.json'
SNAPSHOTS_DIR = 'snapshots'
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

GROQ_API_KEY = os.environ.get('GROQ_API_KEY') or config.GROQ_API_KEY
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

import tempfile
import shutil

def save_data(data):
    # Atomic write to prevent data.json corruption
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(DATA_FILE)))
    try:
        with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, DATA_FILE)
    except Exception as e:
        os.remove(temp_path)
        print(f"Error saving data: {e}")

def fetch_clean_text(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        # lxml is significantly faster than html.parser
        soup = BeautifulSoup(r.text, 'lxml')
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
        lines = [line.strip() for line in soup.get_text(separator='\n').splitlines() if line.strip()]
        return '\n'.join(lines)
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def summarize_diff_groq(added, removed):
    if not groq_client:
        return {"short_summary": "API Key missing", "strategic_summary": "", "detailed_analysis": [], "metrics": []}
    
    prompt = (
        "You are a competitive intelligence analyst. Review the following website text changes.\n"
        "Replace the placeholder values in the JSON below with your ACTUAL analysis of the Added and Removed text.\n"
        "CRITICAL: Output ONLY valid JSON matching this schema exactly:\n"
        "{\n"
        "  \"short_summary\": \"<A punchy 1-sentence TL;DR of the changes>\",\n"
        "  \"strategic_summary\": \"<A 2-3 sentence strategic impact analysis of what these changes mean for the market/company>\",\n"
        "  \"detailed_analysis\": [\n"
        "    \"<Detailed point 1 about what changed>\",\n"
        "    \"<Detailed point 2 about what changed>\"\n"
        "  ],\n"
        "  \"metrics\": [\n"
        "    {\"label\": \"<Metric Name>\", \"old_value\": <number>, \"new_value\": <number>}\n"
        "  ]\n"
        "}\n\n"
        f"Added text:\n{added[:1500]}\n\n"
        f"Removed text:\n{removed[:1500]}\n"
    )
    try:
        completion = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.1
        )
        res = completion.choices[0].message.content.strip()
        
        # Strip <think> blocks
        res = re.sub(r'<think>.*?</think>', '', res, flags=re.DOTALL).strip()
        
        # Robustly extract JSON block using raw_decode
        start_idx = res.find('{')
        if start_idx != -1:
            try:
                obj, _ = json.JSONDecoder().raw_decode(res[start_idx:])
                return obj
            except Exception:
                pass
                
        return json.loads(res)
    except Exception as e:
        print(f"Groq parsing error: {e}")
        return {"short_summary": "Failed to parse structured data.", "strategic_summary": "", "detailed_analysis": [str(e)], "metrics": []}

def process_url(item):
    url = item['url']
    current_text = fetch_clean_text(url)
    if not current_text:
        item['status'] = "Error fetching"
        return item
        
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    target_dir = os.path.join(SNAPSHOTS_DIR, url_hash)
    os.makedirs(target_dir, exist_ok=True)
    
    # Migrate old format if exists
    old_file = os.path.join(SNAPSHOTS_DIR, f"{url_hash}.txt")
    if os.path.exists(old_file):
        mtime = os.path.getmtime(old_file)
        dt_str = datetime.utcfromtimestamp(mtime).strftime("%Y-%m-%d_%H-%M-%S")
        os.rename(old_file, os.path.join(target_dir, f"{dt_str}.txt"))
        
    existing_files = sorted(os.listdir(target_dir))
    now_str = get_ist_now().strftime("%Y-%m-%d_%H-%M-%S")
    new_file_path = os.path.join(target_dir, f"{now_str}.txt")
    
    if not existing_files:
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(current_text)
        item['status'] = "First scan, baseline saved"
        item['summary'] = {"short_summary": "Baseline established.", "strategic_summary": "", "detailed_analysis": [], "metrics": []}
        item['timestamp'] = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
        item['history'] = [{"file": f"{now_str}.txt", "label": now_str.replace('_', ' ')}]
        return item
        
    latest_file = os.path.join(target_dir, existing_files[-1])
    with open(latest_file, 'r', encoding='utf-8') as f:
        old_text = f.read()
        
    if old_text == current_text:
        item['status'] = "No change"
        item['summary'] = {"short_summary": "No material page-text changes since the last scan.", "strategic_summary": "", "detailed_analysis": [], "metrics": []}
        item['timestamp'] = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
        hist = [{"file": fname, "label": fname.replace('.txt', '').replace('_', ' ')} for fname in sorted(os.listdir(target_dir), reverse=True)]
        item['history'] = hist
        return item
        
    old_lines = old_text.splitlines()
    new_lines = current_text.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, n=0, lineterm=''))
    
    added = [l[1:].strip() for l in diff if l.startswith('+') and not l.startswith('+++')]
    removed = [l[1:].strip() for l in diff if l.startswith('-') and not l.startswith('---')]
    
    if not added and not removed:
        item['status'] = "No change"
        return item
        
    analysis = summarize_diff_groq("\n".join(added), "\n".join(removed))
    
    # Save the new baseline
    with open(new_file_path, 'w', encoding='utf-8') as f:
        f.write(current_text)
        
    # Enforce Rule of 5
    all_files = sorted(os.listdir(target_dir))
    while len(all_files) > 5:
        os.remove(os.path.join(target_dir, all_files.pop(0)))
        
    item['status'] = "CHANGED"
    item['summary'] = analysis
    item['timestamp'] = get_ist_now().strftime("%Y-%m-%d %H:%M:%S")
    
    hist = [{"file": fname, "label": fname.replace('.txt', '').replace('_', ' ')} for fname in sorted(os.listdir(target_dir), reverse=True)]
    item['history'] = hist
    return item

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/competitors', methods=['GET', 'POST'])
def handle_competitors():
    data = load_data()
    if request.method == 'POST':
        req = request.json
        url = req.get('url')
        if not url.startswith('http'):
            url = 'https://' + url
        if not any(d['url'] == url for d in data):
            data.append({
                "id": hashlib.md5(url.encode()).hexdigest()[:8],
                "url": url,
                "name": url.replace('https://','').replace('http://','').strip('/'),
                "status": "Pending",
                "summary": {"short_summary": "Waiting for scan...", "strategic_summary": "", "detailed_analysis": [], "metrics": []},
                "timestamp": "-",
                "history": []
            })
            save_data(data)
        return jsonify({"status": "success"})
    return jsonify(data)

@app.route('/scan', methods=['POST'])
def run_scan():
    data = load_data()
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_url, data))
    save_data(results)
    return jsonify({"status": "Scan complete"})

@app.route('/api/compare', methods=['POST'])
def compare_snapshot():
    req = request.json
    url = req.get('url')
    filename = req.get('filename')
    
    current_text = fetch_clean_text(url)
    if not current_text:
        return jsonify({"error": "Failed to fetch current site"}), 500
        
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    snapshot_path = os.path.join(SNAPSHOTS_DIR, url_hash, filename)
    
    if not os.path.exists(snapshot_path):
        return jsonify({"error": "Historical snapshot not found"}), 404
        
    with open(snapshot_path, 'r', encoding='utf-8') as f:
        old_text = f.read()
        
    if old_text == current_text:
        return jsonify({
            "status": "No change",
            "summary": {
                "short_summary": "No text changes detected compared to this historical snapshot.",
                "strategic_summary": "",
                "detailed_analysis": [],
                "metrics": []
            }
        })
        
    old_lines = old_text.splitlines()
    new_lines = current_text.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, n=0, lineterm=''))
    
    added = [l[1:].strip() for l in diff if l.startswith('+') and not l.startswith('+++')]
    removed = [l[1:].strip() for l in diff if l.startswith('-') and not l.startswith('---')]
    
    if not added and not removed:
        return jsonify({
            "status": "No change",
            "summary": {
                "short_summary": "No substantive changes detected.",
                "strategic_summary": "",
                "detailed_analysis": [],
                "metrics": []
            }
        })
        
    analysis = summarize_diff_groq("\n".join(added), "\n".join(removed))
    return jsonify({"status": "CHANGED", "summary": analysis})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
