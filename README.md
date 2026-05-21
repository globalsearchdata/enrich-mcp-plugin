# Enrich MCP Plugin

Domain → company intelligence for AI agents. Look up company name, country,
contacts, and social profiles from any MCP-compatible client.

## Connect

### Claude Desktop / Cursor / VS Code

```json
{
  "mcpServers": {
    "enrich": {
      "type": "http",
      "url": "https://www.tradego.ai/mcp"
    }
  }
}
```

Or via CLI:

```bash
npx mcp-remote https://www.tradego.ai/mcp
```

### Claude Code

```bash
claude mcp add enrich https://www.tradego.ai/mcp --transport http
```

## Tools

| Tool | What it does |
|------|-------------|
| `enrich_company` | Domain → company name, country, contact emails, phone numbers, social profiles |

## Try Asking

> "Enrich skylineproductionsacademy.com — who works there and how can I reach them?"

> "Look up stripe.com and tell me about the company"

> "Find contact information for the team at github.com"

## Prerequisites

- An MCP-compatible client (Claude Desktop, Cursor, VS Code, Claude Code)
- No API key required (public access)

## Repository Structure

```
.mcp.json                  ← MCP server registration
.claude-plugin/            ← Claude plugin metadata
.codex-plugin/             ← Codex/OpenAI plugin metadata
assets/                    ← Logo and brand assets
README.md                  ← This file
LICENSE
```

## License

MIT
