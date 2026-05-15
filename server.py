#!/usr/bin/env python3
"""DNS Lookup MCP — Resolve DNS records for any domain.

Usage:
  python3 server.py                    # Free tier (50 calls/instance)
  python3 server.py --pro-key PROL_XXX  # Pro tier (unlimited)
"""

import json, socket, sys
from mcp.server import Server, stdio_server
import httpx

server = Server("dns-lookup-mcp")
GOOGLE_DNS = "https://dns.google/resolve"

# ─── Rate Limiting & Pro Key ───────────────────────────────────────────
FREE_LIMIT = 50
PRO_KEYS = {"PROL_AGENTPAY_DEMO": "demo"}  # Demo key for testing

# Parse --pro-key from command line
PRO_KEY = None
for i, arg in enumerate(sys.argv):
    if arg == "--pro-key" and i + 1 < len(sys.argv):
        PRO_KEY = sys.argv[i + 1]
        break

IS_PRO = PRO_KEY in PRO_KEYS
call_counter = 0

STRIPE_LINK = "https://buy.stripe.com/5kQ3cxflRabW9PW1AD1oI0r"  # $19/mo

def check_rate_limit():
    """Check if free tier has exceeded limit. Returns error dict or None."""
    global call_counter
    if IS_PRO:
        return None
    call_counter += 1
    if call_counter > FREE_LIMIT:
        remaining = call_counter - FREE_LIMIT
        return {
            "error": f"Free tier limit reached ({FREE_LIMIT} calls). Upgrade to Pro for unlimited access.",
            "isError": True,
            "next_steps": [
                f"Purchase Pro at {STRIPE_LINK} ($19/mo, unlimited)",
                "Restart the server to reset the free counter",
                "Use --pro-key PROL_XXX to run in Pro mode"
            ],
            "calls_used": call_counter,
            "limit": FREE_LIMIT,
            "over_by": remaining
        }
    return None

async def _dns_lookup(domain, rtype):
    params = {"name": domain, "type": rtype}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GOOGLE_DNS, params=params)
        resp.raise_for_status()
        return resp.json()

@server.tool(
    name="dns_lookup_record",
    description="Lookup a specific DNS record type for a domain",
    input_schema={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Domain name (e.g. example.com)"},
            "record_type": {"type": "string", "enum": ["A", "AAAA", "MX", "NS", "CNAME", "TXT", "SOA"],
                           "description": "DNS record type", "default": "A"}
        },
        "required": ["domain"]
    }
)
async def dns_lookup_record(domain: str, record_type: str = "A") -> str:
    limit_check = check_rate_limit()
    if limit_check:
        return json.dumps(limit_check, indent=2)
    try:
        data = await _dns_lookup(domain, record_type)
        answers = data.get("Answer", [])
        if not answers:
            return json.dumps({"domain": domain, "type": record_type, "records": [], "status": "no_records"}, indent=2)
        records = []
        for a in answers:
            records.append({"name": a.get("name", domain), "type": record_type, "ttl": a.get("TTL", 0), "value": a.get("data", "")})
        return json.dumps({"domain": domain, "type": record_type, "records": records}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "isError": True, "next_steps": ["Verify the domain exists", "Check network connectivity"]}, indent=2)

@server.tool(
    name="dns_get_all_records",
    description="Get all common DNS records for a domain (A, AAAA, MX, NS, TXT)",
    input_schema={
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Domain name"}
        },
        "required": ["domain"]
    }
)
async def dns_get_all_records(domain: str) -> str:
    limit_check = check_rate_limit()
    if limit_check:
        return json.dumps(limit_check, indent=2)
    types = ["A", "AAAA", "MX", "NS", "TXT", "SOA"]
    result = {"domain": domain, "records": {}}
    for t in types:
        try:
            data = await _dns_lookup(domain, t)
            answers = data.get("Answer", [])
            result["records"][t] = [a.get("data", "") for a in answers]
        except:
            result["records"][t] = []
    return json.dumps(result, indent=2)

@server.tool(
    name="dns_reverse_lookup",
    description="Reverse DNS lookup for an IP address",
    input_schema={
        "type": "object",
        "properties": {
            "ip": {"type": "string", "description": "IP address"}
        },
        "required": ["ip"]
    }
)
async def dns_reverse_lookup(ip: str) -> str:
    limit_check = check_rate_limit()
    if limit_check:
        return json.dumps(limit_check, indent=2)
    try:
        hostname = socket.gethostbyaddr(ip)
        return json.dumps({"ip": ip, "hostname": hostname[0], "aliases": hostname[1]}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "isError": True}, indent=2)

def main():
    import anyio
    async def run():
        async with stdio_server() as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
    anyio.run(run)

if __name__ == "__main__":
    main()
