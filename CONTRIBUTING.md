# Contributing

## Setup

```bash
git clone https://github.com/damonyang007/video-audio-extractor.git
cd video-audio-extractor
pip install -r requirements.txt
pip install pytest pyinstaller  # dev dependencies
```

## Development

```bash
python app.py          # Start dev server (opens browser at :17777)
pytest tests/ -v        # Run tests
```

## Project Structure

See [README.md](README.md#project-structure).

## Building

```bash
pyinstaller --onedir --noconsole --name AudioExtract \
  --add-data "templates;templates" \
  --add-data "static;static" \
  app.py
```

## Adding a Platform Parser

1. Create `audioextract/yourplatform.py` with a `resolve(url) -> (url, title)` function
2. Add it to the parser loop in `app.py`'s `api_extract_url` route
3. Return `(None, "")` to fall through to yt-dlp

## Code Style

- Python: follow standard conventions, use `pathlib` for paths
- JavaScript: Alpine.js 3.x, ES6+
- CSS: CSS variables with light/dark via `.light` class
- HTML: Jinja2 partials in `templates/partials/`
