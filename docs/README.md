# LLM Council Documentation

Welcome to the LLM Council documentation. This guide will help you understand, run, and extend the codebase even if you have no prior experience with LLM applications.

## What is LLM Council?

LLM Council is a web application that queries multiple Large Language Models (LLMs) simultaneously and synthesizes their responses into a single, high-quality answer. Instead of relying on a single AI model, the system uses a "council" of models that:

1. Each provide their own answer to your question
2. Anonymously review and rank each other's answers
3. Have a "chairman" model synthesize the best final answer

This approach leverages the collective intelligence of multiple AI models to produce better, more reliable responses.

## Documentation Index

### Context & Background

| Document | Description |
|----------|-------------|
| [Article Summary](./ARTICLE_SUMMARY.md) | **Start here** - VentureBeat article analysis explaining the "orchestration layer" concept and why this codebase matters |

### For Beginners

| Document | Description |
|----------|-------------|
| [**Quick Start Use Cases**](./QUICK_START_USE_CASES.md) | **START HERE** - 10 hands-on tutorials from basic to advanced |
| [Getting Started](./GETTING_STARTED.md) | Step-by-step setup guide with prerequisites |
| [How It Works](./HOW_IT_WORKS.md) | Conceptual explanation of the 3-stage process |
| [Understanding OpenRouter](./OPENROUTER.md) | What OpenRouter is and why/how LLM Council uses it |
| [Glossary](./GLOSSARY.md) | Definitions of technical terms used in this project |

### For Understanding the Code

| Document | Description |
|----------|-------------|
| [Architecture](./ARCHITECTURE.md) | System design, data flow, and component overview |
| [Backend Guide](./BACKEND_GUIDE.md) | Detailed explanation of Python backend code |
| [Frontend Guide](./FRONTEND_GUIDE.md) | Detailed explanation of React frontend code |
| [API Reference](./API_REFERENCE.md) | Complete HTTP API documentation |

### For Extending the Project

| Document | Description |
|----------|-------------|
| [**Comprehensive Feature Guide**](./COMPREHENSIVE_FEATURE_GUIDE.md) | **COMPLETE REFERENCE** - All 21 features explained with code details |
| [Feature Ideas](./FEATURE_IDEAS.md) | Original 21 feature proposals |
| [Roadmap](./ROADMAP.md) | **Current plan** - phased work list, decisions taken, open items |
| [Development Plan](./DEVELOPMENT_PLAN.md) | Implementation order, dependencies, effort estimates |
| [Extending the Codebase](./EXTENDING.md) | How to add features and customize the system |
| [Troubleshooting](./TROUBLESHOOTING.md) | Common problems and solutions |

### Version Control & Contributing

| Document | Description |
|----------|-------------|
| [**Git & GitHub Guide**](./GIT_GITHUB_GUIDE.md) | Complete guide to Git and GitHub CLI for beginners |

## Quick Start

```bash
# 1. Clone and enter the project
cd llm-council-master

# 2. Create .env file with your OpenRouter API key
echo "OPENROUTER_API_KEY=sk-or-v1-your-key-here" > .env

# 3. Install backend dependencies
uv sync

# 4. Install frontend dependencies
cd frontend && npm install && cd ..

# 5. Start both servers (use two terminals)
# Terminal 1:
uv run python -m backend.main

# Terminal 2:
cd frontend && npm run dev

# 6. Open http://localhost:5173 in your browser
```

## Project Structure at a Glance

```
llm-council-master/
├── backend/                 # Python FastAPI server
│   ├── config.py           # Model configuration
│   ├── openrouter.py       # API client for LLM queries
│   ├── council.py          # 3-stage orchestration logic
│   ├── storage.py          # Conversation persistence
│   └── main.py             # HTTP API endpoints
│
├── frontend/               # React web application
│   └── src/
│       ├── App.jsx         # Main app component
│       ├── api.js          # Backend API client
│       └── components/     # UI components
│
├── data/                   # Created at runtime
│   └── conversations/      # Saved conversation JSON files
│
└── docs/                   # This documentation
```

## Key Concepts

### The 3-Stage Process

1. **Stage 1 (First Opinions)**: Your question goes to all council models in parallel. Each model independently generates a response.

2. **Stage 2 (Peer Review)**: Each model reviews and ranks ALL responses (including its own, but anonymized so it doesn't know which is which). This prevents bias.

3. **Stage 3 (Synthesis)**: A designated "chairman" model reads all responses and all rankings, then produces the final, synthesized answer.

### Technologies Used

- **Backend**: Python 3.10+, FastAPI, httpx (async HTTP client)
- **Frontend**: React 19, Vite, react-markdown
- **LLM Access**: OpenRouter API (unified access to multiple LLM providers)
- **Storage**: JSON files (no database required)

## Getting Help

If you encounter issues:
1. Check the [Troubleshooting Guide](./TROUBLESHOOTING.md)
2. Read the [Glossary](./GLOSSARY.md) if you encounter unfamiliar terms
3. Review the relevant code guide ([Backend](./BACKEND_GUIDE.md) or [Frontend](./FRONTEND_GUIDE.md))

## Next Steps

- **New to the project?** Start with [Getting Started](./GETTING_STARTED.md)
- **Want to understand how it works?** Read [How It Works](./HOW_IT_WORKS.md)
- **Ready to modify the code?** Jump to [Extending the Codebase](./EXTENDING.md)
