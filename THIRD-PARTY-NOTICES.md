# Third-Party Notices

Tribal is distributed under the MIT license (see the project `LICENSE` / README).
The Tribal container image also **redistributes** third-party open-source
components, listed here for attribution as their licenses require.

This file is a curated, human-readable snapshot of Tribal's **direct**
dependencies. The authoritative, complete (including transitive dependencies and
OS packages) machine-readable inventory is the **SBOM generated on every build**
in CI — see `.github/workflows/release.yml` (CycloneDX + SPDX artifacts).

> Regenerate the version/license snapshot below after dependency changes — see
> [Regenerating](#regenerating) at the bottom.

## Backend — Python (`requirements.txt`)

| Package | License |
|---|---|
| fastapi | MIT |
| uvicorn | BSD-3-Clause |
| sqlalchemy | MIT |
| apscheduler | MIT |
| httpx | BSD-3-Clause |
| httpx2 | BSD-3-Clause |
| cryptography | Apache-2.0 OR BSD-3-Clause |
| python-multipart | Apache-2.0 |
| bcrypt | Apache-2.0 |
| pyjwt | MIT |
| email-validator | Unlicense |
| prometheus-fastapi-instrumentator | ISC |
| PyMySQL | MIT |
| alembic | MIT |
| **fpdf2** | **LGPL-3.0-only** — see note below |
| pytest | MIT (test-only) |

### Note on fpdf2 (LGPL-3.0)

`fpdf2` is the only copyleft dependency. Tribal uses it as an **unmodified
library** imported via pip; it is not statically linked and Tribal's own source
is not a derivative work. Under the LGPL this means:

- We preserve the fpdf2 license/notice (satisfied by shipping it in the image
  and listing it here).
- A recipient may replace the fpdf2 library with a compatible version — trivially
  true for a pip-installed package.

The LGPL does **not** require Tribal's MIT-licensed source to be relicensed or
disclosed. If fpdf2 were ever modified in-tree, those modifications would need to
be offered under the LGPL — so keep fpdf2 as an unmodified dependency.

## Frontend — JavaScript (bundled into shipped static assets)

Runtime dependencies compiled into `/static` and served by the app:

| Package | License |
|---|---|
| vue | MIT |
| vue-router | MIT |
| pinia | MIT |
| @vueuse/core | MIT |
| tailwindcss (generated CSS) | MIT |

Build-time-only tooling (vite, typescript, vue-tsc, postcss, autoprefixer, etc.)
is **not** redistributed — only its compiled output ships — so it is out of scope
for redistribution notices.

## Fonts

- **DejaVu Sans** (`DejaVuSans.ttf`, `DejaVuSans-Bold.ttf`) — vendored under
  `app/fonts/` for PDF report generation. Permissive Bitstream Vera / Arev
  license; full text in [`app/fonts/LICENSE_DEJAVU.txt`](app/fonts/LICENSE_DEJAVU.txt).

## Regenerating

Backend license/version table (run in a venv with `requirements.txt` installed):

```bash
pip install pip-licenses
pip-licenses --format=markdown --order=license \
  --packages $(grep -oE '^[A-Za-z0-9_.-]+' requirements.txt | tr '\n' ' ')
```

The complete SBOM (all transitive deps + OS packages) is produced automatically
by the `sbom` job in `.github/workflows/release.yml` on each push to `main`.
