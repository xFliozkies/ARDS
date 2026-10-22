"""Serve the website integration fixture for manual/browser checks.

Run: python3 tests/workspace_fixture.py
Use the printed URL as ARDS_UI_TEST_URL for workspace_browser.mjs.
Both databases are temporary; no learner archive is read or modified.
"""
import time
from test_website import WebsiteTests

if __name__ == '__main__':
    fixture = WebsiteTests()
    fixture.setUp()
    print(fixture.base, flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        fixture.doCleanups()
