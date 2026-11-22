# Third-Party Dependencies and Licenses

This project uses the following third-party libraries and services:

## Python Dependencies

| Package | License | Purpose |
|---------|---------|---------|
| FastAPI | MIT | Web framework |
| pymatgen | MIT | Materials analysis |
| uvicorn | BSD-3-Clause | ASGI server |
| jinja2 | BSD-3-Clause | Template engine |
| python-multipart | Apache-2.0 | Form data parsing |
| plotly | MIT | Phase diagram figures; also ships the plotly.js bundle |

## JavaScript Dependencies

| Library | License | Purpose |
|---------|---------|---------|
| Plotly.js | MIT | Interactive plotting (bundled with the plotly Python package and served locally from `/vendor/plotly.min.js`; no CDN) |

## Static Edition (browser calculation)

| Component | License | Purpose |
|-----------|---------|---------|
| Pyodide | MPL-2.0 | Python in the browser, loaded from the jsDelivr CDN (pinned version, integrity-checked loader) |
| NumPy / SciPy (Pyodide builds) | BSD-3-Clause | Numerics and the convex hull (qhull) |
| `phasecore/data/*.json` | MIT (copied from pymatgen) | Elemental Gibbs energies, NIST-JANAF gas data and atomic masses; regenerate with `python -m scripts.export_reference_tables` |

The finite-temperature model is the descriptor of Bartel et al., Nature Communications 9, 4168 (2018).

## External Services

| Service | Terms | Purpose |
|---------|-------|---------|
| Materials Project API | Data: CC BY 4.0. GNoME-derived entries: CC BY-NC 4.0 (non-commercial only) | Materials data |

## License Compatibility

All dependencies are compatible with the MIT license of this project.

## Materials Project Data Usage

Data from the Materials Project is subject to the Materials Project Terms of Use
(checked against the published terms and the "How to Cite" page):
- The data is licensed under CC BY 4.0: give appropriate credit, provide a link to the license, and indicate
  if changes were made (the footer of the app does this)
- GNoME-derived data (Graph Networks for Materials Exploration Database) is licensed under CC BY-NC 4.0 and is
  "only licensed for non-commercial use"; users of that data are asked to cite Merchant et al., Nature, 2023.
  The app excludes entries whose Materials Project license is `BY-NC` (or whose batch is GNoME) by default and
  includes them only when the user enables "Include non-commercial data"
- Cite Horton et al., Nature Materials (2025) and Jain et al., APL Materials 1, 011002 (2013); tool-specific
  papers are listed on the Materials Project "How to Cite" page
- Do not scrape the website, be mindful of API usage, and do not share an API key among multiple users or in public
- The Terms of Use list, among the things users agree to, to "contact us for guidance about appropriate
  acknowledgements before re-packaging and publicly re-distributing Materials Project data". The same terms
  state that the content "may be copied, distributed, transmitted, and adapted without obtaining specific
  permission from the Materials Project, provided that proper attribution is given ... and changes (if any)
  are indicated". The contact request therefore concerns acknowledgements and applies to public
  redistribution; it is not a permission gate. This is our reading of the terms, not legal advice
- Data on the Materials Project AWS Open Data buckets is subject to the same terms

## Compliance Notes

- The repository does not contain Materials Project data. The server edition accesses data through the
  official API only, with no caching
- The static edition needs data files that you download yourself with `scripts/build_static_data.py` (CC BY 4.0
  materials only; unknown licenses are excluded). They are git-ignored. Serving the site to a limited group
  (for example inside a LAN) needs attribution and a statement of changes, which the page footer provides.
  Before putting a site that contains them on the public internet, contact the Materials Project about
  acknowledgements, as noted above
- Users are responsible for complying with all applicable terms of service