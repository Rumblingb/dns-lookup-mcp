#!/usr/bin/env python3
"""DNS Lookup MCP — Resolve DNS records for any domain."""

import json, socket
from mcp.server import Server, stdio_server
import httpx

server = Server("dns-lookup-mcp")
GOOGLE_DNS = "https://dns.google/resolve"

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
