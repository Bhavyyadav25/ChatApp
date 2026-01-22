# Interview Assistant

AI-powered interview assistant for Linux (Ubuntu) with screen-share avoidance capabilities. Captures interviewer audio, transcribes questions in real-time, and provides AI-generated answers via Claude.

## Features

- **Interview Mode**: Real-time audio capture and transcription of interviewer questions
- **AI Answers**: Claude-powered responses with code examples and complexity analysis
- **Screen-Share Avoidance**: Multiple stealth modes to stay invisible during screen sharing
- **Multiple Interview Types**: DSA, System Design, and Behavioral modes with specialized prompts
- **Glassmorphism UI**: Beautiful, modern dark theme with semi-transparent panels
- **History**: SQLite-backed Q&A history with search and export
- **System Tray**: Quick access controls from system tray

## Requirements

- Ubuntu 22.04+ (or other Linux with GTK4)
- Python 3.10+
- PipeWire or PulseAudio
- Anthropic API key

## Installation

### 1. Install System Dependencies

```bash
sudo apt update
sudo apt install -y \
    libgtk-4-dev \
    gir1.2-gtk-4.0 \
    libadwaita-1-dev \
    gir1.2-adw-1 \
    libgtksourceview-5-dev \
    gir1.2-gtksource-5 \
    libpulse-dev \
    pipewire \
    pipewire-pulse \
    ffmpeg \
    python3-pip \
    python3-venv
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -e .
# Or using requirements.txt
pip install -r requirements.txt
```

### 4. Download Whisper Model

```bash
# The model will download automatically on first run
# Or pre-download with:
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

### 5. Set Up AI Backend

The app supports two AI backends:

#### Option A: Ollama (Recommended - Free & Offline)

1. **Install Ollama**:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Start Ollama**:
   ```bash
   ollama serve
   ```

3. **Pull a model** (choose one):
   ```bash
   # Fast, good for coding (recommended)
   ollama pull llama3.1:8b

   # Best for coding interviews
   ollama pull deepseek-coder-v2:16b

   # Lightweight alternative
   ollama pull mistral:7b
   ```

4. The app uses Ollama by default - just run it!

#### Option B: Claude API (Cloud, Paid)

1. Create account at https://console.anthropic.com
2. Add billing and generate API key
3. Configure in the app:
   - Open Settings > AI
   - Select "Claude (Cloud, Paid)" as backend
   - Enter your API key

## Usage

### Run the Application

```bash
# From project directory
python -m interview_assistant

# Or if installed
interview-assistant
```

### Interview Mode

1. **Select Interview Type**: Choose DSA, System Design, or Behavioral from the dropdown
2. **Start Recording**: Click the record button or press `Ctrl+Alt+R`
3. **Speak Questions**: The app captures system audio and transcribes questions
4. **View Answers**: AI-generated answers appear with syntax highlighting

### Stealth Modes

Configure in Settings > Stealth:

- **Normal**: Standard window (visible in screen share)
- **Overlay**: X11 window tricks to bypass some capture tools
- **Secondary Monitor**: Shows only on secondary display
- **Hotkey Popup**: Brief popup that auto-hides

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Alt+R` | Toggle recording |
| `Ctrl+Alt+I` | Toggle window visibility |
| `Ctrl+Q` | Quit application |

## Project Structure

```
interview_assistant/
├── core/           # Config, events, session management
├── audio/          # Audio capture and VAD
├── transcription/  # Whisper transcription
├── ai/             # Claude API integration
├── ui/             # GTK4 UI components
├── stealth/        # Screen-share avoidance
├── storage/        # SQLite database
├── services/       # System tray, shortcuts
└── resources/      # CSS themes, icons
```

## Configuration

Configuration is stored in `~/.config/interview-assistant/config.toml`

```toml
[ai]
api_key = "your-api-key"
model = "claude-sonnet-4-5-20250929"
max_tokens = 4096

[transcription]
model_size = "base"
language = "en"

[stealth]
mode = "normal"
auto_hide_timeout = 5000
opacity = 0.95
```

## Limitations

### Screen-Share Avoidance

There is **no guaranteed method** to hide windows from all screen capture tools. Effectiveness depends on:
- Screen capture method (X11 vs XDG Portal)
- Desktop environment and compositor
- Screen sharing mode (entire screen vs window)

**Recommendation**: Secondary monitor mode is most reliable if you share only your primary display.

### Audio Capture

System audio capture requires PipeWire or PulseAudio monitor sources. Ensure your audio is routed through the default output device.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black interview_assistant/
ruff check interview_assistant/
```

## License

MIT License - See LICENSE file
