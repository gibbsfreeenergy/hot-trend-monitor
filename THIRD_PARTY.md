# Third-party references

This project is an independent implementation. It does not copy source code
from the projects below; it uses their public documentation, observable API
shapes, and high-level architecture as references.

- [TrendRadar](https://github.com/sansan0/TrendRadar) — multi-source trend
  collection, retry, caching, and keyword-monitoring ideas. GPL-3.0. The
  project is not bundled here.
- [NewsNow](https://github.com/ourongxing/newsnow) — optional upstream JSON
  endpoint for public hot-list data. MIT. The default endpoint is configurable
  and can be replaced with a self-hosted instance.
- [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) — adapter
  boundaries and platform-specific collection considerations. Its
  non-commercial learning license means its code is intentionally not bundled
  or copied into this project.

## Collection and platform terms

Use only sources and request rates that you are permitted to use. The built-in
collectors are deliberately rate-limited, keep credentials out of source code,
and allow platform adapters to be disabled or replaced. You are responsible
for complying with each platform's terms, robots rules, privacy requirements,
and applicable law.

