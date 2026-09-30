#!/usr/bin/env python3
"""Pump Tracker local server + CORS proxy for pump.fun public APIs."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
PORT = 8765
PUMP = "https://frontend-api-v3.pump.fun"
DEX = "https://api.dexscreener.com"
JUP = "https://quote-api.jup.ag"
UA = "Mozilla/5.0 (compatible; PumpTracker/1.0)"


def fetch(url: str, timeout: int = 12) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read(), res.headers.get("Content-Type", "application/json")
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b"{}", "application/json"
    except Exception as e:
        return 502, json.dumps({"error": str(e)}).encode(), "application/json"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[pump-tracker] {self.address_string()} {fmt % args}")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/api/coins":
            offset = qs.get("offset", ["0"])[0]
            limit = qs.get("limit", ["50"])[0]
            sort = qs.get("sort", ["last_trade_timestamp"])[0]
            order = qs.get("order", ["DESC"])[0]
            include = qs.get("includeNsfw", ["false"])[0]
            url = (
                f"{PUMP}/coins?offset={offset}&limit={limit}"
                f"&sort={sort}&order={order}&includeNsfw={include}"
            )
            self._proxy(url)
            return
        if parsed.path == "/api/sol-price":
            self._proxy(f"{PUMP}/sol-price")
            return
        if parsed.path == "/api/coin":
            mint = qs.get("mint", [""])[0]
            if not mint:
                self._json(400, {"error": "mint required"})
                return
            self._proxy(f"{PUMP}/coins/{urllib.parse.quote(mint)}")
            return
        if parsed.path == "/api/dex":
            q = qs.get("q", ["pump"])[0]
            self._proxy(f"{DEX}/latest/dex/search?q={urllib.parse.quote(q)}")
            return
        if parsed.path == "/api/quote":
            out_mint = qs.get("mint", [""])[0]
            amount = qs.get("amount", ["100000000"])[0]
            if not out_mint:
                self._json(400, {"error": "mint required"})
                return
            url = (
                f"{JUP}/v6/quote?inputMint=So11111111111111111111111111111111111111112"
                f"&outputMint={urllib.parse.quote(out_mint)}&amount={amount}&slippageBps=1500"
            )
            self._proxy(url)
            return
        if parsed.path == "/api/health":
            self._json(200, {"ok": True})
            return
        if parsed.path in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()

    def _proxy(self, url: str):
        status, body, ctype = fetch(url)
        self.send_response(status)
        self.send_header("Content-Type", ctype.split(";")[0])
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


def main():
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Pump Tracker running at http://127.0.0.1:{PORT}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
