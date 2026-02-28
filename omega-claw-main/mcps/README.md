# MCPs (Model Context Protocol)

Drop MCP config files here to wire external services into your Antigravity builds.

When Omega Claw drops a FOUNDER_JOB, it includes the MCP configs.
Claude Code / Antigravity reads these and connects to the services automatically.

## Config Format

```json
{
  "name": "supabase",
  "type": "database",
  "connection": {
    "url": "env:SUPABASE_URL",
    "key": "env:SUPABASE_KEY"
  }
}
```

## Installing an MCP

```bash
# From omega-store
cp ~/omega-store/mcps/supabase-mcp.json ./mcps/

# Or manually create the JSON config
```

Keys use `env:VAR_NAME` format — actual values are read from `.env` at runtime.
