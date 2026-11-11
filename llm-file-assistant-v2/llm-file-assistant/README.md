# LLM-Powered File System Assistant

A command-line assistant that lets you manage resume files with natural
language. The LLM (via OpenRouter) decides which file system tools to call
(read, list, write, search), and the program executes them locally.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Get an OpenRouter key and a free model

1. Sign up at https://openrouter.ai and create a key at https://openrouter.ai/keys.
2. Find a free model that supports tools at https://openrouter.ai/models
   (filter by **Free** and **Tools**) and copy its model ID.

Set both variables in the same terminal you'll run the assistant from:

macOS/Linux:
```bash
export OPENROUTER_API_KEY="your-key-here"
export OPENROUTER_MODEL="paste-a-free-model-id-here"
```

Windows (PowerShell):
```powershell
$env:OPENROUTER_API_KEY="your-key-here"
$env:OPENROUTER_MODEL="paste-a-free-model-id-here"
```

Generate sample data (6 resumes: 2 PDF, 2 DOCX, 2 TXT). The zip already includes them, so this is optional:

```bash
python make_sample_resumes.py
```

## Usage

Interactive mode:

```bash
python llm_file_assistant.py
```

One-shot mode:

```bash
python llm_file_assistant.py "Find resumes mentioning Python experience"
```

Example queries:

- "Read all resumes in the resumes folder"
- "Find resumes mentioning Python experience"
- "Which candidates have Kubernetes experience?"
- "Create a summary file for resume_john_doe.pdf"

Summaries are saved to `./summaries/` by default. Type `exit` to quit interactive mode.

## Tools

| Tool | Purpose |
|------|---------|
| `read_file(filepath)` | Extract text from PDF/TXT/DOCX with metadata |
| `list_files(directory, extension=None)` | List files with name, size, modified date |
| `write_file(filepath, content)` | Write text, creating directories as needed |
| `search_in_file(filepath, keyword, context_lines=1)` | Case-insensitive keyword search with context |

## Project layout

- `fs_tools.py`: the tool implementations and their JSON schemas (no LLM dependency)
- `llm_file_assistant.py`: the OpenRouter tool-calling loop and CLI
- `make_sample_resumes.py`: test data generator

## Troubleshooting

- **"Missing dependency"**: run `pip install -r requirements.txt` with the virtual environment active.
- **"Set OPENROUTER_MODEL"**: the model variable isn't set in this terminal.
- **"No endpoints found that support tool use"**: the chosen model doesn't support tool calling. Pick another with the Tools filter.
- **429 / rate-limit errors**: free models have request limits. Wait a minute or try another free model.
- **401 errors**: the key is wrong or wasn't exported in this terminal.
- **PDF returns no text**: the PDF is probably scanned, and OCR (e.g. `pytesseract`) is needed.
