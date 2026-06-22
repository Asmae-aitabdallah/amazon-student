# Assets Log - Amazon Student prototype

This project deliberately uses **no third-party binary assets** (no stock
images, icon packs, or web-font files). Everything is built from system fonts
and CSS, which keeps the prototype licence-clean and fully self-contained.

The table below logs every external source: code dependencies and the factual
sources used for the T-Level content.

| Asset | Source | Purpose | Date retrieved |
|-------|--------|---------|----------------|
| Flask 3.0.3 (web framework) | https://pypi.org/project/Flask/ (BSD-3-Clause licence) | Back-end routing, sessions, templating | 2026-06-22 |
| Werkzeug 3.0.3 | https://pypi.org/project/Werkzeug/ (BSD-3-Clause licence) | Password hashing (PBKDF2) and WSGI utilities | 2026-06-22 |
| Jinja2 (bundled with Flask) | https://palletsprojects.com/p/jinja/ (BSD-3-Clause licence) | HTML templating | 2026-06-22 |
| System UI fonts (Segoe UI / system-ui stack) | Operating system default; no file bundled | Body and heading typography | 2026-06-22 |
| Colour palette (Squid Ink #232F3E, Orange #FF9900) | Reproduced from Amazon's public brand colours for academic likeness only | Visual identity of the prototype | 2026-06-22 |
| T-Level facts: 21 courses, 2-year duration, ~1,800 study hours | GOV.UK, Introduction of T Levels — https://www.gov.uk/government/publications/introduction-of-t-levels/introduction-of-t-levels | Accurate content on information pages | 2026-06-22 |
| T-Level facts: 315-hour / ~45-day industry placement, ~20% of time | UCAS — https://www.ucas.com/further-education/post-16-qualifications/qualifications-you-can-take/t-levels | Accurate content on information pages | 2026-06-22 |
| T-Level facts: UCAS tariff (Distinction* = 168 points) | UCAS tariff guidance (via ukcalculator.com summary) — https://ukcalculator.com/ucas-points-calculator.html | Accurate progression content | 2026-06-22 |
| T-Level facts: core/specialism component hours, ETF professional development | GOV.UK, Supporting HE providers to understand T Levels — https://www.gov.uk/government/publications/t-level-resources-for-universities/supporting-higher-education-providers-to-understand-t-levels | Accurate educator-page content | 2026-06-22 |

## Notes
- **Trademark:** The "Amazon" name and brand colours are used only to mimic the
  look of the brief for an academic exercise. This prototype is not affiliated
  with, authorised by, or endorsed by Amazon.com, Inc. Do not deploy publicly
  or present as a real Amazon product.
- **T-Level content** is illustrative and was accurate as of the retrieval date.
  Always confirm current figures at gov.uk before relying on them.
