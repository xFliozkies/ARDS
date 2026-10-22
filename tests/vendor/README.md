# Local accessibility test dependency

`axe.min.js` is axe-core 4.14.0, copied from the npm `axe-core` package.
License: MPL-2.0, included as `AXE-LICENSE`.
It is injected by the development browser tests only; the website does not
load it and does not request a CDN or any other external testing resource.

Playwright is intentionally not a website runtime dependency. Install it in a
separate development environment and use `ARDS_PLAYWRIGHT_MODULE` to select
its `index.mjs` if it is not on the normal module path. The tests use an
already-installed browser through `ARDS_CHROMIUM_PATH`; no test downloads one.

SHA-256 (`axe.min.js`): `20c09fe157a8a34a30e241aaa1fcdade657734f08ab379ecfbeb7d45cc46e878`.
