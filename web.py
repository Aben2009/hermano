# Mata internet Hermano: cari web, cari berita, baca isi halaman.
# Gratis tanpa API key. Semua hasil dianggap DATA luar (bukan perintah).
import base64
import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import requests

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}
TIMEOUT = 12


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _get(url, **kw):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r


def _format(results, max_results):
    lines = []
    for i, res in enumerate(results[:max_results], 1):
        lines.append(f"{i}. {res['title']}")
        if res.get("meta"):
            lines.append(f"   ({res['meta']})")
        if res.get("snippet"):
            lines.append(f"   {res['snippet'][:300]}")
        lines.append(f"   URL: {res['url']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- relevance
STOPWORDS = {"yang", "dan", "atau", "untuk", "dengan", "dari", "pada", "info", "tentang",
             "the", "and", "for", "with", "terkini", "terbaru", "sekarang", "hari", "ini",
             "acara", "tanggal", "jadwal", "kapan", "saja", "informasi", "detail", "details",
             "event", "events", "official", "website", "resmi", "cari", "carikan", "tolong",
             "sampai", "hingga", "antara", "tahun", "bulan", "awal", "akhir", "date", "dates"}


def _query_variants(query):
    # Versi kata kunci yang makin sederhana: asli -> kata penting + tahun -> kata penting utama
    variants = [query]
    words = _keywords(query)
    years = re.findall(r"\b(?:19|20)\d{2}\b", query)
    simple = " ".join(words + years)
    if simple:
        variants.append(simple)
    if words:
        variants.append(" ".join(words[:2]))
    out = []
    for v in variants:
        if v.strip() and v.strip().lower() not in [o.lower() for o in out]:
            out.append(v.strip())
    return out


def _keywords(query):
    words = re.findall(r"\w+", query.lower())
    return [w for w in words if len(w) > 3 and not w.isdigit() and w not in STOPWORDS]


def _relevant(results, query):
    # Buang hasil yang tidak mengandung SATU PUN kata kunci penting dari query.
    words = _keywords(query)
    if not words:
        return results
    keep = []
    for r in results:
        hay = (r.get("title", "") + " " + r.get("snippet", "") + " " + r.get("url", "")).lower()
        if any(w in hay for w in words):
            keep.append(r)
    return keep


# ---------------------------------------------------------------- web search
def _ddgs_lib(query):
    # Library ddgs (pip install ddgs) - paling tahan blokir
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    rows = DDGS().text(query, region="id-id", max_results=10) or []
    return [{"title": _clean(r.get("title")), "url": r.get("href", ""),
             "snippet": _clean(r.get("body"))} for r in rows]


def _ddg(query):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query, "kl": "id-id"})
    page = _get(url).text
    results = []
    blocks = re.split(r'<div[^>]+class="[^"]*\bresult\b', page)[1:]
    for block in blocks:
        a = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        href = html.unescape(a.group(1))
        if "uddg=" in href:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            href = q.get("uddg", [href])[0]
        if href.startswith("//"):
            href = "https:" + href
        if "duckduckgo.com/y.js" in href:  # iklan
            continue
        snip = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.S)
        results.append({"title": _clean(a.group(2)), "url": href,
                        "snippet": _clean(snip.group(1)) if snip else ""})
    return results


def _bing_real_url(href):
    href = html.unescape(href)
    if "bing.com/ck/a" in href:
        u = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("u", [""])[0]
        if u.startswith("a1"):
            data = u[2:] + "=" * (-len(u[2:]) % 4)
            try:
                return base64.urlsafe_b64decode(data).decode("utf-8", "ignore")
            except Exception:
                pass
    return href


def _bing(query):
    url = "https://www.bing.com/search?" + urllib.parse.urlencode(
        {"q": query, "setlang": "id", "cc": "ID"})
    page = _get(url).text
    results = []
    for block in re.findall(r'<li class="b_algo"(.*?)</li>', page, re.S):
        a = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        snip = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
        results.append({"title": _clean(a.group(2)), "url": _bing_real_url(a.group(1)),
                        "snippet": _clean(snip.group(1)) if snip else ""})
    return results


def web_search(query, max_results=6):
    errors, irrelevant = [], 0
    for q in _query_variants(query):
        for engine in (_ddgs_lib, _ddg, _bing):
            try:
                results = [r for r in engine(q) if r["url"].startswith("http")]
                good = _relevant(results, query)
                irrelevant += len(results) - len(good)
                if good:
                    note = "" if q == query else f"(dicari ulang dengan kata kunci: {q})\n"
                    return note + _format(good, max_results)
            except Exception as e:
                errors.append(f"{engine.__name__}: {type(e).__name__}")
    msg = "Tidak ada hasil yang relevan."
    if irrelevant:
        msg += f" ({irrelevant} hasil dibuang karena tidak nyambung dengan kata kunci.)"
    if errors:
        msg += f" (error: {'; '.join(sorted(set(errors)))})"
    return msg + " Sampaikan ke user apa adanya; jangan mengarang."


# ---------------------------------------------------------------- news search
def _rss_items(xml_text):
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        data = {"source": ""}
        for child in item:
            tag = child.tag.split("}")[-1].lower()
            data[tag if tag != "source" else "source"] = (child.text or "").strip()
        yield data


def _bing_news(query):
    url = "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": query, "format": "rss", "setlang": "id-ID", "cc": "ID"})
    results = []
    for it in _rss_items(_get(url).text):
        link = it.get("link", "")
        real = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url", [link])[0]
        meta = ", ".join(x for x in (it.get("source"), it.get("pubdate")) if x)
        results.append({"title": _clean(it.get("title")), "url": real, "meta": meta,
                        "snippet": _clean(it.get("description"))})
    return results


def _google_news(query):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "id", "gl": "ID", "ceid": "ID:id"})
    results = []
    for it in _rss_items(_get(url).text):
        meta = ", ".join(x for x in (it.get("source"), it.get("pubdate")) if x)
        results.append({"title": _clean(it.get("title")), "url": it.get("link", ""),
                        "meta": meta, "snippet": ""})
    return results


def news_search(query, max_results=8):
    errors = []
    for engine in (_bing_news, _google_news):
        try:
            results = _relevant(list(engine(query)), query)
            if results:
                return _format(results, max_results)
        except Exception as e:
            errors.append(f"{engine.__name__}: {e}")
    return "Tidak ada berita ditemukan." + (f" (error: {'; '.join(errors)})" if errors else "")


# ---------------------------------------------------------------- read page
class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside",
            "form", "svg", "iframe", "button", "select"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "article", "section"}

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.parts = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip_depth:
            self.parts.append(data)


def read_webpage(url, max_chars=3500):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        r = _get(url)
    except Exception as e:
        return f"Gagal membuka halaman: {e}"
    if "html" not in r.headers.get("Content-Type", "html"):
        return "Halaman ini bukan teks/HTML, tidak bisa dibaca."
    parser = _TextExtractor()
    try:
        parser.feed(r.text)
    except Exception:
        pass
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in "".join(parser.parts).split("\n")]
    lines = [ln for ln in lines if len(ln) > 40]  # buang menu & tombol pendek
    text = "\n".join(lines)
    if not text:
        return "Isi halaman tidak terbaca (mungkin butuh JavaScript atau diblokir)."
    head = f"Judul: {parser.title.strip()}\nURL: {r.url}\n\n"
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(dipotong)"
    return head + text
