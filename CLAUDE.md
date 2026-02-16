# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a **dual-project repository** containing:

1. **BiliSub** (root directory) - Bilibili/XiaoHongShu subtitle download and transcription tool
2. **MediaCrawler** (`MediaCrawler/` subdirectory) - Multi-platform social media crawler

The two projects are independent and serve different purposes.

---

## BiliSub (Root Directory)

### Purpose
Download and process video subtitles from Bilibili and XiaoHongShu. When built-in subtitles are unavailable, it uses OpenAI Whisper for speech-to-text transcription.

### Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Main transcription tool (recommended)
python ultimate_transcribe.py -u "VIDEO_URL" -m medium -f srt

# Batch process from CSV file
python ultimate_transcribe.py -csv videos.csv -m medium -f srt

# Optimize subtitles with GLM API (requires config_api.py)
python optimize_srt_glm.py -s output/transcripts/video.srt -p tech

# Check for built-in subtitles first
python check_subtitle.py "VIDEO_URL"
```

### Architecture

**Processing Priority:**
1. Built-in subtitle extraction (fastest)
2. Video OCR using PaddleOCR (medium, extracts on-screen text)
3. Whisper speech recognition (slowest, transcribes audio)

**Key Files:**
- `ultimate_transcribe.py` - Main entry point, handles all three methods
- `optimize_srt_glm.py` - GLM-based subtitle optimization
- `check_subtitle.py` - Check for built-in subtitles
- `srt_prompts.py` - Prompt definitions for different optimization modes
- `config_api.py` - API configuration (must be created by user)

**Whisper Models:** tiny/base/small/medium/large (default: medium)

**Output Formats:** SRT, ASS, VTT, JSON, TXT, LRC

**Optimization Modes:** optimization, simple, conservative, aggressive, tech, interview, vlog

### Important Notes

- **Anti-hotlinking**: Uses custom headers and Referer for Bilibili downloads
- **Streaming**: Enabled with `concurrentfragments: 4` for faster downloads
- **Windows encoding**: UTF-8 wrapper applied to stdout/stderr for Chinese character support
- **GLM API**: Requires `config_api.py` with Zhipu API credentials

---

## MediaCrawler (MediaCrawler/ Directory)

### Purpose
Multi-platform social media crawler supporting XHS, Douyin, Kuaishou, Bilibili, Weibo, Tieba, and Zhihu.

### Key Commands

```bash
cd MediaCrawler

# Install dependencies (uses uv, Python 3.11+)
uv sync

# Run crawler (platform specified via config or command line)
python main.py

# Run tests
pytest

# With documentation
npm run docs:dev
```

### Architecture

**Factory Pattern:** `CrawlerFactory` creates platform-specific crawlers
- Supported platforms: xhs, dy, ks, bili, wb, tieba, zhihu

**Key Components:**
- `media_platform/` - Platform-specific crawler implementations
- `base/base_crawler.py` - Abstract base class `AbstractCrawler`
- `store/` - Storage implementations (CSV, JSON, DB, Excel)
- `config/` - Platform-specific configurations
- `proxy/` - IP proxy pool management
- `database/` - SQLAlchemy ORM layer

**Authentication:** Uses Playwright browser automation for login state caching

**License:** NON-COMMERCIAL LEARNING LICENSE 1.1 - strictly for educational use

---

## Shared Patterns

**Error Handling:** Both projects use `tenacity` for retry logic

**Async:** MediaCrawler uses asyncio throughout; BiliSub is primarily synchronous

**Encoding:** UTF-8 is enforced for stdout/stderr in both projects to handle Chinese characters

**Configuration:** Both use external config files that must be created by the user (API keys, cookies)
