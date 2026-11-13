"""
Builds the Bit Science Games website into docs/, which GitHub Pages publishes.

    python3 build.py              pages, plus any images whose sources changed
    python3 build.py --images     every image, from scratch

Sources:
    content/privacy.md, content/terms.md   the policy pages
    content/apps/<slug>.md                 one per app: details at the top, page below
    products/<slug>/                       that app's icon, mark and screenshots
    brand/                                 the bit science beaker, wordmark and app marks
    assets/site.css                        the stylesheet, copied as it is

Adding an app: write content/apps/<slug>.md (copy rifle-calcs.md for the details it needs),
put its icon and screenshots in products/<slug>/, and build. The home page lists every app
in content/apps, by `order`.

Rendering images needs Google Chrome. Nothing on the published site loads from anywhere
else: no web fonts, no scripts, no analytics. The privacy policy says so; keep it true.
"""
import html
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SITE = {
    "name": "Bit Science Games",
    "tagline": "Apps and games from bit science.",
    "intro": "Small, carefully made apps for iPhone, iPad and Android. No accounts, no ads, and no tracking.",
    "owner": "Jamoke Innovations LLC",
    "email": "support@jaredjudd.com",
    # The custom domain, such as "bitsciencegames.com". Set it to write docs/CNAME and give
    # link previews absolute image addresses; empty until the domain is chosen.
    "domain": "jaredjudd.com",
}

SLATE, FIELD, GREEN, ORANGE, AMBER, BLUE = "#33383B", "#24282B", "#9ACE51", "#F97A2B", "#F8A621", "#04BAF4"


# ---- Markdown, the small part of it these pages use ------------------------------------

def inline(text):
    """Escapes, then **bold**, *italic*, `code` and [links](url)."""
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)

    def link(m):
        label, url = m.group(1), m.group(2)
        external = url.startswith("http")
        attrs = ' rel="noopener"' if external else ""
        return f'<a href="{html.escape(url)}"{attrs}>{label}</a>'

    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, out)


IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)$")


def blocks(md):
    """Splits Markdown into (kind, payload) blocks: heading, para, list, rule, images."""
    lines = md.strip("\n").split("\n")
    out, para, items, images = [], [], [], []

    def flush():
        nonlocal para, items, images
        if para:
            out.append(("para", " ".join(para)))
        if items:
            out.append(("list", items))
        if images:
            out.append(("images", images))
        para, items, images = [], [], []

    for line in lines:
        s = line.strip()
        if not s:
            flush()
        elif m := re.match(r"^(#{1,3})\s+(.*)$", s):
            flush()
            out.append((f"h{len(m.group(1))}", m.group(2)))
        elif s == "---":
            flush()
            out.append(("rule", None))
        elif m := IMAGE.match(s):
            if para or items:
                flush()
            images.append((m.group(1), m.group(2)))
        elif s.startswith("- "):
            if para or images:
                flush()
            items.append(s[2:])
        elif items and line.startswith("  "):
            items[-1] += " " + s
        else:
            if items or images:
                flush()
            para.append(s)
    flush()
    return out


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", text).lower()).strip("-")


def render_block(kind, payload, image_html):
    if kind in ("h1", "h2", "h3"):
        text = inline(payload)
        return f'<{kind} id="{slug(text)}">{text}</{kind}>'
    if kind == "para":
        return f"<p>{inline(payload)}</p>"
    if kind == "list":
        return "<ul>" + "".join(f"<li>{inline(i)}</li>" for i in payload) + "</ul>"
    if kind == "rule":
        return "<hr>"
    if kind == "images":
        return image_html(payload)
    raise ValueError(kind)


def front_matter(text):
    """Splits `---` key: value lines from the body."""
    meta = {}
    if text.startswith("---\n"):
        head, text = text[4:].split("\n---\n", 1)
        for line in head.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta, text


# ---- Images -------------------------------------------------------------------------------

def chrome(src_html, out, w, h, scale=2, transparent=False, tmp=None):
    page = Path(tmp) / f"{out.stem}-{abs(hash(str(out)))}.html"
    page.write_text(src_html)
    args = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            f"--window-size={w},{h}", f"--force-device-scale-factor={scale}", f"--screenshot={out}"]
    if transparent:
        args.append("--default-background-color=00000000")
    subprocess.run(args + [page.as_uri()], check=True, capture_output=True)


def doc(body, background="transparent"):
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;'
            f'background:{background}}}svg{{display:block}}</style></head><body>{body}</body></html>')


def phone(src_uri, width):
    """A screenshot in a phone frame. The rim is lighter than the bezel, so the phone holds its
    edge against the dark page."""
    bezel, radius = width * 0.032, width * 0.135
    return (f'<div style="box-sizing:border-box;width:{width}px;padding:{bezel:.1f}px;border-radius:{radius:.1f}px;'
            f'background:#0F1112;box-shadow:0 {width * .05:.0f}px {width * .12:.0f}px rgba(0,0,0,.55),'
            f'inset 0 0 0 {max(1.5, width * .006):.1f}px #4A5257"><img src="{src_uri}" style="display:block;'
            f'width:{width - bezel * 2:.1f}px;border-radius:{radius - bezel:.1f}px"></div>')


def svg_file(path, height):
    """An SVG from brand/, resized to a height, ready to inline."""
    text = (ROOT / "brand" / path).read_text()
    w, h = (float(x) for x in re.search(r'width="([\d.]+)" height="([\d.]+)"', text).groups())
    return re.sub(r'width="[\d.]+" height="[\d.]+"', f'width="{height * w / h:.1f}" height="{height}"', text, count=1)


def stale(out, *sources):
    return not out.exists() or any(s.stat().st_mtime > out.stat().st_mtime for s in sources)


def build_images(apps, force):
    out = DOCS / "images"
    out.mkdir(parents=True, exist_ok=True)
    slate = f"radial-gradient(ellipse at 30% 40%, #3E4447 0%, {SLATE} 50%, {FIELD} 100%)"
    made = []

    with tempfile.TemporaryDirectory() as tmp:
        # Site icon: the beaker on the slate, square, for browsers and home screens.
        icon = out / "icon.png"
        beaker_svg = ROOT / "brand" / "bit-science-beaker.svg"
        if force or stale(icon, beaker_svg):
            body = (f'<div style="width:512px;height:512px;background:{SLATE};display:flex;'
                    f'align-items:center;justify-content:center">{svg_file("bit-science-beaker.svg", 400)}</div>')
            chrome(doc(body), icon, 512, 512, scale=1, tmp=tmp)
            subprocess.run(["sips", "-z", "180", "180", str(icon), "--out", str(out / "apple-touch-icon.png")],
                           check=True, capture_output=True)
            made += [icon, out / "apple-touch-icon.png"]

        # Link preview for the site.
        social = out / "social.png"
        if force or stale(social, beaker_svg):
            body = (f'<div style="width:1200px;height:630px;background:{slate};display:flex;align-items:center;'
                    f'justify-content:center;gap:56px">{svg_file("bit-science-beaker.svg", 330)}'
                    f'<div>{svg_file("bit-science-wordmark.svg", 92)}<div style="font:600 46px \'Avenir Next\';'
                    f'letter-spacing:.32em;color:#C9D0D3;margin:22px 0 0 6px">GAMES</div></div></div>')
            chrome(doc(body), social, 1200, 630, scale=1, tmp=tmp)
            made.append(social)

        for app in apps:
            src = ROOT / "products" / app["slug"]
            dest = out / app["slug"]
            (dest / "phones").mkdir(parents=True, exist_ok=True)

            for shot in app["screens"]:
                shot_src = src / "screens" / shot
                framed = dest / "phones" / shot
                if force or stale(framed, shot_src):
                    pad, w = 40, 300
                    h = round(w * 2868 / 1320 * 0.936 + w * 0.064)
                    chrome(doc(f'<div style="padding:{pad}px">{phone(shot_src.as_uri(), w)}</div>'),
                           framed, w + pad * 2, h + pad * 2, scale=2, transparent=True, tmp=tmp)
                    made.append(framed)

            app_icon = dest / "icon.png"
            if force or stale(app_icon, src / app["icon"]):
                subprocess.run(["sips", "-z", "256", "256", str(src / app["icon"]), "--out", str(app_icon)],
                               check=True, capture_output=True)
                made.append(app_icon)

            preview = dest / "social.png"
            hero = src / "screens" / app["hero"]
            if force or stale(preview, hero, ROOT / "brand" / app["mark"]):
                body = (f'<div style="width:1200px;height:630px;background:{slate};position:relative;overflow:hidden;'
                        f'display:flex;align-items:center"><div style="margin-left:90px;display:flex;flex-direction:column;'
                        f'gap:24px">{svg_file(app["mark"], 150)}<div style="font:600 84px/1 \'Avenir Next\';color:#fff">'
                        f'{html.escape(app["title"])}</div><div style="font:500 34px \'Avenir Next\';color:#C9D0D3">'
                        f'{html.escape(app["tagline"])}</div>{svg_file("bit-science-wordmark.svg", 26)}</div>'
                        f'<div style="position:absolute;right:110px;top:70px">{phone(hero.as_uri(), 330)}</div></div>')
                chrome(doc(body), preview, 1200, 630, scale=1, tmp=tmp)
                made.append(preview)

    return made


# ---- Pages --------------------------------------------------------------------------------

def site_url(path):
    return f"https://{SITE['domain']}{path}" if SITE["domain"] else path


def page(title, description, body, path, social="/images/social.png", page_class=""):
    full_title = SITE["name"] if title == SITE["name"] else f"{title} · {SITE['name']}"
    year = date.today().year
    nav = "".join(f'<a href="{href}">{label}</a>' for label, href in
                  (("Apps", "/#apps"), ("Privacy", "/privacy/"), ("Terms", "/terms/")))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{html.escape(description)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE['name']}">
<meta property="og:title" content="{html.escape(full_title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:image" content="{site_url(social)}">
<meta name="twitter:card" content="summary_large_image">
{f'<link rel="canonical" href="{site_url(path)}">' if SITE["domain"] else ""}
<link rel="icon" href="/images/icon.png">
<link rel="apple-touch-icon" href="/images/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body class="{page_class}">
<header class="top"><div class="wrap">
<a class="brand" href="/" aria-label="{SITE['name']} home">{svg_file("bit-science-beaker.svg", 38)}
<span class="brand-name">{svg_file("bit-science-wordmark.svg", 21)}<span class="games">GAMES</span></span></a>
<nav>{nav}</nav>
</div></header>
<main>
{body}
</main>
<footer class="bottom"><div class="wrap">
<div>{svg_file("bit-science-wordmark.svg", 18)}</div>
<nav><a href="/#apps">Apps</a><a href="/privacy/">Privacy</a><a href="/terms/">Terms</a>
<a href="mailto:{SITE['email']}">{SITE['email']}</a></nav>
<p class="fine">&copy; {year} {SITE['owner']}. Apple, the Apple logo, iPhone and iPad are trademarks of Apple Inc., registered in the U.S. and other countries. App Store is a service mark of Apple Inc. Google Play, the Google Play logo and Android are trademarks of Google LLC.</p>
</div></footer>
</body>
</html>
"""


# The stores' own badges, as Apple and Google supply them (assets/badges/, unaltered).
STORES = (("app_store_url", "app-store", "/assets/badges/app-store.svg", "Download on the App Store"),
          ("play_store_url", "google-play", "/assets/badges/google-play.png", "Get it on Google Play"))


def store_buttons(app, links=True):
    """A badge for each store the app is in, and `status` (such as "Coming soon to the App Store")
    while it is not yet in the App Store. On the home page the whole card is already a link, so
    the badges there are pictures, not links (`links=False`)."""
    out = []
    for key, name, src, label in STORES:
        url = app.get(key)
        badge = f'<img src="{src}" alt="{label}">'
        if url and links:
            out.append(f'<a class="badge {name}" href="{html.escape(url)}" rel="noopener">{badge}</a>')
        elif url:
            out.append(f'<span class="badge {name}">{badge}</span>')
        elif key == "app_store_url":
            out.append(f'<span class="store soon">{html.escape(app.get("status") or "Coming soon")}</span>')
    return f'<div class="stores">{"".join(out)}</div>'


def load_apps():
    apps = []
    for md in sorted((ROOT / "content" / "apps").glob("*.md")):
        meta, body = front_matter(md.read_text())
        meta["slug"] = md.stem
        meta["body"] = body
        meta["order"] = int(meta.get("order") or 99)
        meta["screens"] = sorted({m.group(2) for m in re.finditer(r"!\[([^\]]*)\]\(([^)\s]+)\)", body)}
                                 | {meta["hero"]})
        apps.append(meta)
    return sorted(apps, key=lambda a: (a["order"], a["title"]))


def home(apps):
    cards = "".join(f"""
<a class="card" href="/{a['slug']}/">
<img src="/images/{a['slug']}/icon.png" alt="" width="96" height="96">
<div><h3>{html.escape(a['title'])}</h3><p class="tag">{html.escape(a['tagline'])}</p>
<p>{html.escape(a['summary'])}</p>{store_buttons(a, links=False)}</div></a>""" for a in apps)

    body = f"""
<section class="hero home-hero"><div class="wrap">
<div class="lockup">{svg_file("bit-science-beaker.svg", 190)}
<div><h1 class="sr">{SITE['name']}</h1>{svg_file("bit-science-wordmark.svg", 64)}<div class="games big">GAMES</div></div></div>
<p class="lead">{html.escape(SITE['tagline'])} {html.escape(SITE['intro'])}</p>
</div></section>
<section class="wrap apps" id="apps">
<h2>Apps</h2>
<div class="cards">{cards}</div>
</section>"""
    return page(SITE["name"], SITE["intro"], body, "/", page_class="home")


def app_page(app):
    slug_ = app["slug"]

    def phones(images):
        figs = "".join(f'<img src="/images/{slug_}/phones/{html.escape(src)}" alt="{html.escape(alt)}" '
                       f'loading="lazy">' for alt, src in images)
        return f'<div class="phones n{len(images)}">{figs}</div>'

    # The text before the first heading is the hero's lead; each ## heading starts a section,
    # laid out beside its screenshots when it has any.
    parts = re.split(r"(?m)^(?=## )", app["body"].strip())
    lead = "" if parts[0].startswith("## ") else parts.pop(0)
    sections = []
    for i, part in enumerate(parts):
        bl = blocks(part)
        shots = [b for b in bl if b[0] == "images"]
        text = "".join(render_block(k, p, phones) for k, p in bl if k != "images")
        title = bl[0][1] if bl and bl[0][0] == "h2" else ""
        cls = "support" if title.lower() == "support" else ("feature" if shots else "plain")
        if title.lower().startswith("private"):
            cls += " lcd"
        if shots:
            art = "".join(phones(p) for _, p in shots)
            side = " flip" if i % 2 else ""
            sections.append(f'<section class="{cls}{side}"><div class="wrap grid"><div class="text">{text}</div>'
                            f'<div class="art">{art}</div></div></section>')
        else:
            sections.append(f'<section class="{cls}"><div class="wrap narrow">{text}</div></section>')

    credit = f'<p class="credit wrap narrow">{inline(app["credit"])}</p>' if app.get("credit") else ""
    body = f"""
<section class="hero app-hero"><div class="wrap grid">
<div class="text">
<div class="app-lockup">{svg_file(app['mark'], 96)}<div><h1>{html.escape(app['title'])}</h1>
<p class="tag">{html.escape(app['tagline'])}</p></div></div>
{''.join(render_block(k, p, phones) for k, p in blocks(lead))}
{store_buttons(app)}
<p class="jump"><a href="#support">Support</a> · <a href="/privacy/#{slug(app['title'])}">Privacy</a></p>
</div>
<div class="art"><img src="/images/{slug_}/phones/{html.escape(app['hero'])}" alt="{html.escape(app['title'])} on iPhone"></div>
</div></section>
{''.join(sections)}
{credit}"""
    return page(app["title"], app["summary"], body, f"/{slug_}/",
                social=f"/images/{slug_}/social.png", page_class="app")


def prose(name):
    meta, body = front_matter((ROOT / "content" / f"{name}.md").read_text())
    text = "".join(render_block(k, p, lambda _: "") for k, p in blocks(body))
    return page(meta["title"], meta["description"], f'<article class="wrap narrow prose">{text}</article>',
                f"/{name}/", page_class="legal")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def main():
    force = "--images" in sys.argv
    apps = load_apps()
    for app in apps:
        for f in [app["icon"], app["mark"] and f"../../brand/{app['mark']}"] + [f"screens/{s}" for s in app["screens"]]:
            if f and not (ROOT / "products" / app["slug"] / f).exists():
                sys.exit(f"{app['slug']}: missing {f}")

    made = build_images(apps, force)
    shutil.copytree(ROOT / "assets", DOCS / "assets", dirs_exist_ok=True)

    pages = [write(DOCS / "index.html", home(apps)),
             write(DOCS / "privacy" / "index.html", prose("privacy")),
             write(DOCS / "terms" / "index.html", prose("terms"))]
    pages += [write(DOCS / a["slug"] / "index.html", app_page(a)) for a in apps]
    pages.append(write(DOCS / "404.html", page("Not found", "That page does not exist.",
        '<article class="wrap narrow prose"><h1>Not found</h1><p>That page does not exist. '
        '<a href="/">Back to the home page</a>.</p></article>', "/404.html", page_class="legal")))

    write(DOCS / ".nojekyll", "")
    cname = DOCS / "CNAME"
    if SITE["domain"]:
        write(cname, SITE["domain"] + "\n")
    elif cname.exists():
        cname.unlink()

    for p in made + pages:
        print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()
