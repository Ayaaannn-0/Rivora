# Rivora

Rivora is a web-based competitive intelligence dashboard that monitors target URLs for changes, tracks a rolling historical snapshot, and leverages the Groq AI API to generate strategic insights.

## Features
- **Continuous Monitoring**: Scans watched target URLs and tracks changes against historical baselines.
- **Rule of 5 Snapshot Queue**: Automatically maintains up to 5 historical snapshots per URL to prevent database bloat.
- **Historical Comparison**: Instantly compare the live site against any historical snapshot via an intuitive dropdown.
- **AI-Powered Strategic Impact**: Automatically generates an executive summary, strategic analysis, detailed breakdowns, and quantitative metrics using Groq's high-speed inference.
- **PDF Export**: Generate perfectly styled intelligence reports with one click.

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/Ayaaannn-0/Rivora.git](https://github.com/Ayaaannn-0/Rivora.git)
   cd Rivora
   ```

2. **Set up a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Rename `.env.example` to `.env` and add your Groq API Key:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

4. **Run the Application:**
   ```bash
   python app.py
   ```
   Open `http://127.0.0.1:5000` in your browser.

## Architecture & Data
- **Backend:** Flask, Python, ThreadPoolExecutor (for parallel scraping)
- **Frontend:** Vanilla JS, Chart.js, html2pdf.js, custom CSS
- **AI Engine:** Groq API (`qwen/qwen3.6-27b`)
- **Storage:** Flat JSON (`data.json`) and flat-file text snapshots (`snapshots/`)

## License
MIT License
