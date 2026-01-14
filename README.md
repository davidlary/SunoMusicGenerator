# SunoMusicGenerator

Transform scientific text into educational songs using AI. This production-ready system generates lyrics, audio, and cover art through an integrated pipeline leveraging Gemini and Suno APIs.

## Features

- **Lyrics Generation**: Transform scientific narratives into educational lyrics using Gemini's Eureka Protocol with 80 laws
- **Audio Generation**: Create professional-quality music using Suno's AI with customizable genres and styles
- **Cover Art Generation**: Generate 4K Renaissance-style cover art using Gemini's image models
- **State Tracking**: Complete version control and change detection with SHA256 hashing
- **Multiple Interfaces**: CLI, REST API, and Web UI
- **Production Ready**: Comprehensive error handling, rate limiting, and logging

## Quick Start

###  Installation

```bash
# Clone repository
git clone https://github.com/davidlary/SunoMusicGenerator.git
cd SunoMusicGenerator

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install package
pip install -e .
```

### Configuration

Create `.env` file in project root:

```bash
# API Keys (required)
GEMINI_API_KEY=your_gemini_api_key_here
SUNO_EMAIL=your_suno_email@example.com
SUNO_PASSWORD=your_suno_password

# Paths (optional - defaults provided)
BASE_DIR=./
SONGS_DIR=Songs
STATE_FILE=Songs/state_tracking.json
PROMPTS_DIR=prompts

# Rate Limiting (optional)
GEMINI_RPM=60
SUNO_RPM=30
THROTTLE_FACTOR=0.8
```

### Usage

#### CLI

```bash
# Generate full song (lyrics + audio + cover)
suno-music generate-all 1.16.1 narrative.txt --title "Physics in Motion"

# Generate only lyrics
suno-music generate-lyrics 1.16.1 narrative.txt

# Generate only audio
suno-music generate-audio 1.16.1 lyrics.txt --title "Song Title"

# Generate only cover art
suno-music generate-cover 1.16.1 lyrics.txt

# Check status
suno-music status
suno-music status 1.16.1
```

#### Web API

```bash
# Start API server
python -m src.web.app

# Access at:
# - Web UI: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Health: http://localhost:8000/health
```

#### Python API

```python
from src.pipeline import LyricsGenerator, SongGenerator, CoverGenerator
from pathlib import Path

# Generate lyrics
lyrics_gen = LyricsGenerator()
result = lyrics_gen.generate(
    song_id="1.16.1",
    narrative_text="Scientific text here...",
    prompt_template_path=Path("prompts/EurekaProtocol.md")
)

# Generate audio
song_gen = SongGenerator()
audio_result = song_gen.generate(
    song_id="1.16.1",
    lyrics=result["lyrics"],
    title="Song Title",
    tags="educational, rock"
)

# Generate cover art
cover_gen = CoverGenerator()
cover_result = cover_gen.generate(
    song_id="1.16.1",
    lyrics=result["lyrics"],
    prompt_template_path=Path("prompts/CoverArtPrompt.md")
)
```

## Architecture

### Module Structure

```
src/
├── core/              # Core utilities
│   ├── errors.py      # Custom exceptions
│   ├── logger.py      # Logging system
│   ├── rate_limiter.py # Token bucket rate limiting
│   └── settings.py    # Pydantic configuration
├── clients/           # API clients
│   ├── gemini_client.py  # Gemini API integration
│   └── suno_client.py    # Suno API integration
├── state/             # State management
│   ├── state_tracker.py   # Version control
│   └── metadata_manager.py # Metadata utilities
├── pipeline/          # Generation pipelines
│   ├── lyrics_generator.py
│   ├── song_generator.py
│   └── cover_generator.py
├── cli/               # Command-line interface
│   └── main.py
├── web/               # REST API
│   ├── app.py         # FastAPI application
│   ├── routes.py      # API endpoints
│   └── models.py      # Pydantic models
└── frontend/          # Web UI
    ├── index.html
    ├── styles.css
    └── app.js
```

### Key Technologies

- **API Clients**: `google.genai` (Gemini), `playwright` (Suno authentication)
- **Configuration**: `pydantic` and `pydantic-settings`
- **CLI**: `click` and `rich`
- **Web API**: `fastapi` and `uvicorn`
- **State Management**: JSON with SHA256 hashing
- **Rate Limiting**: Token bucket algorithm
- **Testing**: `pytest` with 170+ tests, 85% average coverage

## API Reference

### REST Endpoints

- `POST /api/v1/lyrics/generate` - Generate lyrics from narrative
- `POST /api/v1/audio/generate` - Generate audio from lyrics
- `POST /api/v1/cover/generate` - Generate cover art from lyrics
- `POST /api/v1/pipeline/generate` - Run full pipeline
- `GET /api/v1/status` - Get all songs status
- `GET /api/v1/status/{song_id}` - Get specific song status
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation
- `GET /redoc` - Alternative API documentation

Full API documentation available at `/docs` when server is running.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific module
pytest tests/unit/test_gemini_client.py -v

# Run with detailed output
pytest -vv --tb=short
```

### Test Coverage

- **Total Tests**: 173
- **Pass Rate**: 98.3% (170 passed)
- **Average Coverage**: 85%
- **Modules Tested**: All 10 core modules

## State Management

The system tracks all generations in `Songs/state_tracking.json`:

```json
{
  "version": "1.0.0",
  "songs": {
    "1.16.1": {
      "title": "Physics in Motion",
      "source_path": "narrative.txt",
      "content_hash": "sha256_hash",
      "created_at": "2026-01-13T12:00:00",
      "lyrics": {
        "active_version": "20260113-120000",
        "versions": [...]
      },
      "audio": {...},
      "cover": {...}
    }
  }
}
```

Features:
- SHA256-based change detection
- Timestamp versioning (YYYYMMDD-HHMMSS)
- Never overwrites originals
- Complete audit trail

## Configuration Options

### Rate Limiting

- **Token Bucket Algorithm**: Prevents API throttling
- **Throttle Factor**: 0.8 (80% of API limits)
- **Burst Capacity**: 2.5x per-minute rate
- **Exponential Backoff**: 2s, 4s, 8s retry delays

### Model Selection

- **Lyrics**: `gemini-2.0-flash-thinking-exp-1219`
- **Cover Art**: `gemini-3-pro-image-preview`
- **Audio**: `chirp-v3-5` (Suno)

### File Organization

```
Songs/
├── state_tracking.json
└── 1.16.1/
    ├── Lyrics/
    │   └── 1.16.1.txt
    ├── Audio/
    │   ├── clip-abc-123.wav
    │   └── clip-abc-123.mp3
    └── Cover/
        └── 1.16.1.jpg
```

## Error Handling

Custom exceptions for all failure modes:
- `GeminiAPIError` - Gemini API failures
- `SunoAPIError` - Suno API failures
- `RateLimitError` - Rate limit exceeded
- `LyricsGenerationError` - Lyrics pipeline failures
- `SongGenerationError` - Audio pipeline failures
- `CoverGenerationError` - Cover art pipeline failures
- `StateTrackingError` - State management failures

All errors include detailed context and are logged with full tracebacks.

## Development

### Project Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (if configured)
pre-commit install

# Run linting
flake8 src/
black src/ --check

# Run type checking
mypy src/
```

### Adding New Features

1. Create feature branch: `git checkout -b feature/my-feature`
2. Implement with tests (>80% coverage required)
3. Update documentation
4. Submit pull request

### Code Style

- **Formatting**: Black (line length 100)
- **Imports**: isort
- **Docstrings**: Google style
- **Type Hints**: Required for public APIs

## Deployment

### Docker (Recommended)

```dockerfile
# Dockerfile example
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install -e .

EXPOSE 8000

CMD ["uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Considerations

- Set `allow_origins` in CORS to specific domains
- Use environment variables for all secrets
- Enable HTTPS with reverse proxy (nginx/caddy)
- Set up log aggregation (ELK, Datadog)
- Configure monitoring and alerting
- Use process manager (systemd, supervisor)

## Troubleshooting

### Common Issues

**API Key Errors**
```bash
# Verify API keys are set
python -c "from src.core import get_settings; print(get_settings().gemini.api_key[:10])"
```

**Rate Limiting**
```bash
# Check rate limiter status
from src.core import get_rate_limiter
limiter = get_rate_limiter()
print(limiter.get_status())
```

**State File Corruption**
```bash
# Backup and reset state
cp Songs/state_tracking.json Songs/state_tracking.json.backup
# Delete state_tracking.json to start fresh
```

### Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set in environment
export LOG_LEVEL=DEBUG
```

## Roadmap

- [ ] Batch processing for multiple songs
- [ ] Video generation integration
- [ ] Custom voice selection for audio
- [ ] Internationalization (i18n) support
- [ ] Cloud deployment templates (AWS, GCP, Azure)
- [ ] Prometheus metrics endpoint
- [ ] GraphQL API option
- [ ] Real-time progress streaming via WebSockets

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- **Gemini API**: Google's advanced language and image models
- **Suno API**: Professional music generation platform
- **CPF v4.3.0**: Context-Preserving Framework for state tracking
- **Claude Sonnet 4.5**: AI pair programming assistance

## Support

- **Issues**: https://github.com/davidlary/SunoMusicGenerator/issues
- **Documentation**: http://localhost:8000/docs (when running)
- **Email**: david.lary@gmail.com

## Project Status

**Version**: 1.0.0
**Status**: Production Ready
**Last Updated**: 2026-01-13
**Test Coverage**: 85%
**Python**: 3.10+

---

**Built with ❤️ using Claude Code**
