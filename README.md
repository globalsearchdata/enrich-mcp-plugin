# Enrich MCP Server

Company intelligence for AI agents. Look up company name, country,
contacts, and social profiles by domain or company name — from any MCP-compatible client.

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
| `enrich_company_by_name` | Company name → domain, country, contact emails, phone numbers, social profiles |

## Try Asking

> "Enrich skylineproductionsacademy.com — who works there and how can I reach them?"

> "Look up stripe.com and tell me about the company"

> "Find the company named Tesla and give me their contact info"

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


[![smithery badge](https://smithery.ai/badge/globalsearchdata/enrich-mcp-plugin)](https://smithery.ai/servers/globalsearchdata/enrich-mcp-plugin)

## License

MIT
