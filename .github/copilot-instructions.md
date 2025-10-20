# Copilot Instructions for SENAR Agent API

## Project Overview

This is an AI Agent API built on Agno framework with FastAPI, designed for SENAR support system with a hub-and-spoke workflow architecture. The system uses PostgreSQL with pgvector for knowledge storage and implements multi-agent teams for intelligent support ticket routing and resolution.

## Language
You talk in portuguese, but code and comments in english.

## Model Configuration
This project uses Google Gemini models, not OpenAI. All agents are configured with:
- `Gemini(id="gemini-2.0-flash")` as the default model for all agents
- `GeminiEmbedder(id="models/embedding-001")` for embeddings
- Environment variable: `GOOGLE_API_KEY` (not OPENAI_API_KEY)## Architecture Patterns

### Agent Registry Pattern
- All agents and teams register through `core/agent_registry.py` using the singleton `AGENT_REGISTRY`
- Import agent instances from their definition files, not classes
- Register both individual agents and complete teams for flexible usage

```python
# In core/agent_registry.py
from agents.support_triage_coordinator import triage_agent  # Instance, not class
self._registry[triage_agent.name] = triage_agent
```

### Hub-and-Spoke Workflow
- Central triage coordinator routes requests to specialized agents (N1, N2, N3)
- All agents return to triage for next-step decisions
- Triage uses JSON output format: `{"next_node": "N1_SupportAgent"}`
- Workflow definitions in `workflows/` with conditional routing logic

### Shared Rules System
- Common instructions stored in `shared_rules.py` for consistency
- All agents compose instructions from: `GENERAL_BEGIN_INSTRUCTIONS + specific_instructions + SECURITY_RULES + GENERAL_END_INSTRUCTIONS`
- Mission-specific instructions defined per agent role

## Key Conventions

### Agent Definition Pattern
```python
# agents/[role]_agent.py
from agno.agent import Agent
from shared_rules import GENERAL_BEGIN_INSTRUCTIONS, SECURITY_RULES, GENERAL_END_INSTRUCTIONS

# Define specific instructions as list
specific_instructions = ["# MISSION:", "..."]

# Compose full instructions
full_instructions = GENERAL_BEGIN_INSTRUCTIONS + specific_instructions + SECURITY_RULES + GENERAL_END_INSTRUCTIONS

# Create agent instance (not class)
agent_name = Agent(
    name="AgentName",
    instructions="\n".join(full_instructions),
    # ... other config
)
```

### Repository Pattern
- All data access through repository classes in `repositories/`
- Base repository handles database connections with environment-based config
- Repositories instantiated in toolkits, not injected as dependencies

### Toolkit Integration
- Tools defined in `toolkits/` using Agno's `@tool` decorator
- Repository instances created at module level in toolkits
- Follow pattern: import repositories, instantiate, define tools

## Development Workflow

### Environment Setup
- Use `uv` for dependency management (not pip)
- Run `./scripts/dev_setup.sh` for local development setup
- Python 3.11+ required, using Python 3.12 in dev environment
- Requires `GOOGLE_API_KEY` environment variable for Gemini models

### Docker Development
- `docker compose up -d` starts pgvector DB and API with hot reload
- API runs on port 8000, DB on 5432
- Environment variables: `GOOGLE_API_KEY`, `DB_*` settings in `compose.yaml`

### Adding New Agents
1. Create agent definition in `agents/[name].py` with instance export
2. Register in `core/agent_registry.py`
3. Add to team in `teams/` if part of workflow
4. Update workflow routing in `workflows/` if needed

### API Structure
- Routes in `api/routes/` grouped by functionality
- All routes included in `v1_router.py`
- CORS configured for Agno playground and localhost development

## Critical Files

- `core/agent_registry.py` - Central registry for all agents/teams
- `shared_rules.py` - Common prompt instructions and security rules
- `teams/support_team.py` - Team composition for multi-agent workflows
- `workflows/support_workflow.py` - Conditional routing logic
- `api/routes/v1_router.py` - Main API router configuration
- `repositories/base_repository.py` - Database connection management

## Testing & Quality

- Use `./scripts/format.sh` for code formatting with ruff
- `./scripts/validate.sh` for type checking with mypy
- Build with `./scripts/build_image.sh` for production images
- Follow existing patterns for database queries and error handling

## Integration Notes

- Connects to external Directus database for knowledge base
- Supports Agno Playground at https://app.agno.com for testing
- Uses pgvector for embeddings and knowledge storage
- Environment variables control database connections and API behavior
