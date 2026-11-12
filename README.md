# Bit Science Games website

The website for the apps published by Jamoke Innovations LLC as Bit Science Games. It is a
static site, built by `build.py` into `docs/`, which GitHub Pages publishes.

## Layout

| Path | What |
|---|---|
| `content/privacy.md` | Privacy Policy: general rules, then a section per app |
| `content/terms.md` | Terms of Use: general terms, then app-specific terms |
| `content/apps/<slug>.md` | One per app: its details at the top, its page below |
| `products/<slug>/` | That app's icon and screenshots (`screens/`, 1320 x 2868) |
| `brand/` | The bit science beaker, the wordmark, and app marks, as SVG |
| `assets/site.css` | The stylesheet |
| `build.py` | Builds everything into `docs/` |
| `docs/` | The built site. Generated; do not edit by hand |

## Building

    python3 build.py              pages, plus images whose sources changed
    python3 build.py --images     every image, from scratch

Images are rendered with Google Chrome. To preview, serve `docs/` and open it in a browser:

    cd docs && python3 -m http.server 8765

The links are written for a site at the root of its domain, so open the preview through
that server, not as files.

## Adding an app

1. Copy `content/apps/rifle-calcs.md` to `content/apps/<slug>.md` and change its details
   and text. The slug becomes the page's address, such as `/rifle-calcs/`.
2. Put the app's icon (1024 px PNG) and screenshots in `products/<slug>/`, and its mark in
   `brand/`.
3. Add a section for the app under "App details" in `content/privacy.md`, and under
   "App-specific terms" in `content/terms.md` if it needs any.
4. Build. The home page lists every app, by its `order`.

Each `## heading` on an app page becomes a section. A section with screenshots is laid out
beside them, in phone frames; a `## Support` section is the page's support area.

When an app goes live, set its `app_store_url` to show a download link in place of
"Coming soon".

## Keeping the policies true

The privacy policy says the site uses no cookies, analytics, web fonts or scripts, and loads
nothing from other sites, and that each app sends only what its section describes. Update the
policy in the same change as anything that would make it untrue, and change its effective
date.

## Publishing on GitHub Pages

1. Create a **public** repository on GitHub, such as `BitScience`. Pages is free for public
   repositories.
2. Push this folder to it:

       git remote add origin git@github.com:Jamoke/BitScience.git
       git push -u origin main

3. In the repository on GitHub: **Settings > Pages > Build and deployment**. Choose
   **Deploy from a branch**, branch `main`, folder `/docs`.
4. Set `"domain"` in `SITE` at the top of `build.py`, build, and push. That writes
   `docs/CNAME`, which tells GitHub Pages the domain.
5. At your domain's DNS provider:
   - For a subdomain, such as `games.example.com`: a `CNAME` record pointing to
     `jamoke.github.io`.
   - For the bare domain, such as `example.com`: `A` records for `185.199.108.153`,
     `185.199.109.153`, `185.199.110.153` and `185.199.111.153`, and `AAAA` records for
     `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153` and
     `2606:50c0:8003::153`. Add a `www` CNAME to `jamoke.github.io` if you want `www` too.
6. Back in **Settings > Pages**, once the DNS check passes, tick **Enforce HTTPS**. The
   certificate can take a while to be issued.

Check GitHub's current documentation for custom domains before relying on these addresses.

## For App Store Connect

- Privacy Policy URL: `https://<domain>/privacy/`
- Support URL: `https://<domain>/rifle-calcs/` (its Support section has the contact address)
- Marketing URL (optional): `https://<domain>/rifle-calcs/`
