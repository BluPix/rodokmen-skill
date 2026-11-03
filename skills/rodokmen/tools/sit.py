#!/usr/bin/env python3
"""
sit.py – efektivní, šetrná a robustní HTTP knihovna pro rodokmenové nástroje.

Vlastnosti:
  - Používá standardní knihovnu Pythonu (funguje i v `python3 -I` bez externích závislostí).
  - Recyklace spojení (Connection pooling / Keep-Alive) a opětovné využití TLS handshake.
  - Šetrné pauzy mezi požadavky (rate limiting s nastavitelným jitterem).
  - Automatické opakování požadavků (retry s exponenciálním backoffem) při výpadcích (502, 503, 504, timeout).
  - Podpora automatické dekomprese gzip a deflate.
"""

import gzip
import http.client
import json
import os
import random
import socket
import ssl
import sys
import time
import urllib.parse
import zlib
from typing import Any, Dict, Optional, Tuple, Union

# Výchozí hlavička User-Agent
DEFAULT_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


class HttpResponse:
    """Obal nad HTTP odpovědí."""

    def __init__(self, status: int, headers: Dict[str, str], body: bytes, url: str):
        self.status = status
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.body = body
        self.url = url

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def text(self, encoding: Optional[str] = None) -> str:
        """Dekóduje tělo jako text."""
        if encoding:
            return self.body.decode(encoding, errors="replace")

        # Zkusíme detekovat z Content-Type
        ctype = self.headers.get("content-type", "")
        if "charset=" in ctype:
            enc = ctype.split("charset=")[-1].split(";")[0].strip(" '\"")
            try:
                return self.body.decode(enc, errors="replace")
            except LookupError:
                pass

        # Výchozí UTF-8, fallback na cp1250 / latin1
        try:
            return self.body.decode("utf-8")
        except UnicodeDecodeError:
            return self.body.decode("windows-1250", errors="replace")

    def json(self) -> Any:
        """Parsuje tělo jako JSON."""
        return json.loads(self.text())


class Sit:
    """Správce spojení a HTTP relací s recyklací TLS a rate limitingem."""

    def __init__(
        self,
        pauza: Tuple[float, float] = (0.4, 0.9),
        user_agent: str = DEFAULT_UA,
        timeout: float = 25.0,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ):
        self.pauza_min, self.pauza_max = pauza
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        # Pool otevřených spojení: klíč je (scheme, host, port) -> http.client.HTTPConnection / HTTPSConnection
        self._pool: Dict[Tuple[str, str, int], Union[http.client.HTTPConnection, http.client.HTTPSConnection]] = {}
        self._posledni_volani: Dict[str, float] = {}  # host -> timestamp

        # Sdílený SSL kontext pro recyklaci TLS cache
        self._ssl_context = ssl.create_default_context()

    def _cekej_pred_volanim(self, host: str):
        """Uplatní rate-limiting pro daného hostitele."""
        ted = time.time()
        posledni = self._posledni_volani.get(host, 0.0)
        uplynulo = ted - posledni

        potrebna_pauza = random.uniform(self.pauza_min, self.pauza_max)
        if uplynulo < potrebna_pauza:
            time.sleep(potrebna_pauza - uplynulo)

        self._posledni_volani[host] = time.time()

    def _ziskej_spojeni(self, scheme: str, host: str, port: int):
        """Získá recyklované nebo nové spojení z poolu."""
        klic = (scheme, host, port)
        conn = self._pool.get(klic)

        if conn is not None:
            # Ověříme, zda spojení není uzavřené
            if getattr(conn, "sock", None) is None:
                conn = None

        if conn is None:
            if scheme == "https":
                conn = http.client.HTTPSConnection(
                    host,
                    port=port,
                    timeout=self.timeout,
                    context=self._ssl_context,
                )
            else:
                conn = http.client.HTTPConnection(
                    host,
                    port=port,
                    timeout=self.timeout,
                )
            self._pool[klic] = conn

        return conn

    def _uzavri_spojeni(self, scheme: str, host: str, port: int):
        klic = (scheme, host, port)
        conn = self._pool.pop(klic, None)
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Union[bytes, str]] = None,
        json_data: Optional[Any] = None,
        timeout: Optional[float] = None,
    ) -> HttpResponse:
        """Provede HTTP dotaz s retry logikou, keep-alive a dekompresí."""
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise ValueError(f"Nepodporované schéma URL: {scheme}")

        host = parsed.hostname or ""
        port = parsed.port or (443 if scheme == "https" else 80)

        # Doplnění query parametrů
        query = urllib.parse.parse_qsl(parsed.query)
        if params:
            for k, v in params.items():
                if v is not None:
                    query.append((str(k), str(v)))
        path = parsed.path or "/"
        if query:
            path += "?" + urllib.parse.urlencode(query)

        # Příprava hlaviček
        vsechny_hlavicky: Dict[str, str] = {
            "Host": host,
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
        if headers:
            vsechny_hlavicky.update(headers)

        # Příprava těla
        telo: Optional[bytes] = None
        if json_data is not None:
            telo = json.dumps(json_data).encode("utf-8")
            if "Content-Type" not in vsechny_hlavicky and "content-type" not in vsechny_hlavicky:
                vsechny_hlavicky["Content-Type"] = "application/json; charset=utf-8"
        elif data is not None:
            if isinstance(data, str):
                telo = data.encode("utf-8")
            else:
                telo = data

        if telo is not None:
            vsechny_hlavicky["Content-Length"] = str(len(telo))

        # Samotné volání s opakováním při chybách
        pokus = 0
        posledni_vyjimka = None
        aktualni_timeout = timeout or self.timeout

        while pokus < self.max_retries:
            pokus += 1
            self._cekej_pred_volanim(host)

            conn = self._ziskej_spojeni(scheme, host, port)
            try:
                conn.request(method.upper(), path, body=telo, headers=vsechny_hlavicky)
                resp = conn.getresponse()

                raw_body = resp.read()
                resp_headers = {k.lower(): v for k, v in resp.getheaders()}

                # Dekomprese
                content_encoding = resp_headers.get("content-encoding", "").lower()
                if "gzip" in content_encoding or raw_body.startswith(b"\x1f\x8b"):
                    try:
                        raw_body = gzip.decompress(raw_body)
                    except Exception:
                        pass
                elif "deflate" in content_encoding:
                    try:
                        raw_body = zlib.decompress(raw_body)
                    except Exception:
                        try:
                            raw_body = zlib.decompress(raw_body, -zlib.MAX_WBITS)
                        except Exception:
                            pass

                # Kontrola, zda server žádá uzavření spojení
                if resp_headers.get("connection", "").lower() == "close":
                    self._uzavri_spojeni(scheme, host, port)

                http_resp = HttpResponse(resp.status, resp_headers, raw_body, url)

                # Retry při dočasných chybách serveru (502, 503, 504, 429)
                if http_resp.status in (429, 502, 503, 504) and pokus < self.max_retries:
                    wait_time = self.backoff_factor ** pokus + random.uniform(0.5, 1.5)
                    time.sleep(wait_time)
                    self._uzavri_spojeni(scheme, host, port)
                    continue

                return http_resp

            except (http.client.RemoteDisconnected, http.client.CannotSendRequest,
                    http.client.BadStatusLine, socket.error, TimeoutError, ssl.SSLError) as e:
                posledni_vyjimka = e
                self._uzavri_spojeni(scheme, host, port)
                if pokus < self.max_retries:
                    wait_time = self.backoff_factor ** pokus + random.uniform(0.2, 0.8)
                    time.sleep(wait_time)
                else:
                    raise

        if posledni_vyjimka:
            raise posledni_vyjimka
        raise RuntimeError(f"Požadavek na {url} selhal po {self.max_retries} pokusech.")

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> HttpResponse:
        return self.request("GET", url, params=params, **kwargs)

    def post(self, url: str, data: Optional[Any] = None, json_data: Optional[Any] = None, **kwargs) -> HttpResponse:
        return self.request("POST", url, data=data, json_data=json_data, **kwargs)

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        resp = self.get(url, params=params, **kwargs)
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status} při GET {url}: {resp.text()[:200]}")
        return resp.json()

    def post_json(self, url: str, json_data: Any, **kwargs) -> Any:
        resp = self.post(url, json_data=json_data, **kwargs)
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status} při POST {url}: {resp.text()[:200]}")
        return resp.json()

    def stahni_soubor(self, url: str, cil_cesta: str, **kwargs) -> bool:
        """Stáhne soubor přímo do cílového umístění."""
        resp = self.get(url, **kwargs)
        if not resp.ok:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(cil_cesta)), exist_ok=True)
        with open(cil_cesta, "wb") as f:
            f.write(resp.body)
        return True

    def zavri(self):
        """Uzavře všechna otevřená spojení v poolu."""
        for conn in list(self._pool.values()):
            try:
                conn.close()
            except Exception:
                pass
        self._pool.clear()


# Výchozí globální instance pro rychlé použití
_vychozi_klient: Optional[Sit] = None


def ziskej_klienta() -> Sit:
    global _vychozi_klient
    if _vychozi_klient is None:
        _vychozi_klient = Sit()
    return _vychozi_klient


def get(url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> HttpResponse:
    return ziskej_klienta().get(url, params=params, **kwargs)


def post(url: str, data: Optional[Any] = None, json_data: Optional[Any] = None, **kwargs) -> HttpResponse:
    return ziskej_klienta().post(url, data=data, json_data=json_data, **kwargs)


def get_json(url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
    return ziskej_klienta().get_json(url, params=params, **kwargs)


def post_json(url: str, json_data: Any, **kwargs) -> Any:
    return ziskej_klienta().post_json(url, json_data=json_data, **kwargs)


def stahni_soubor(url: str, cil_cesta: str, **kwargs) -> bool:
    return ziskej_klienta().stahni_soubor(url, cil_cesta, **kwargs)

