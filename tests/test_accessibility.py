"""Static accessibility guards for the ARDS Studio stylesheets and scripts (WP2).

These read the shipped files only. They do not start the server and never touch
a database. Browser-level checks (axe-core, keyboard walk-through) belong to the
Playwright work in WP10.
"""
import re
import unittest
from pathlib import Path

PUBLIC = Path(__file__).resolve().parents[1] / "website" / "public"
STYLESHEETS = ["app.css", "typography.css", "workspace.css", "guide.css"]
# Decorative marks only (no text meaning); they must still reach 3:1 on white.
DECORATIVE = (".brand-dot", ".tag-dot", ".row-arrow", ".quote-mark")
# Darkest tinted surface that body text sits on in the app.
TINT_BACKGROUND = "#edf3e9"
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _full(hex_color):
    value = hex_color.lstrip("#").lower()
    return "".join(c * 2 for c in value) if len(value) == 3 else value


def _luminance(hex_color):
    value = _full(hex_color)
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _text_colors():
    for name in STYLESHEETS:
        css = (PUBLIC / name).read_text(encoding="utf-8")
        for match in RULE.finditer(css):
            selector, body = match.group(1).strip(), match.group(2)
            # Light text on a deliberately dark surface is checked by eye.
            if re.search(r"background(?:-color)?\s*:[^;]*?#(?:25|1f|17)[0-9a-f]{4}", body):
                continue
            for color in re.finditer(r"(?<![-\w])color\s*:\s*(#[0-9a-fA-F]{3,6})", body):
                yield name, selector, color.group(1)


class AccessibilityStaticTests(unittest.TestCase):
    def test_text_colors_meet_wcag_aa_on_tinted_surfaces(self):
        failures = []
        for name, selector, color in _text_colors():
            decorative = any(d in selector for d in DECORATIVE)
            needed, surface = (3.0, "#ffffff") if decorative else (4.5, TINT_BACKGROUND)
            ratio = contrast(color, surface)
            if ratio < needed:
                failures.append(f"{name} {selector[:50]!r} {color} = {ratio:.2f}:1 (needs {needed}:1)")
        self.assertEqual([], failures)

    def test_text_tokens_and_placeholder_are_readable(self):
        typography = (PUBLIC / "typography.css").read_text(encoding="utf-8")
        for token in ("--text-muted", "--text-subtle", "--text-body"):
            value = re.search(re.escape(token) + r"\s*:\s*(#[0-9a-fA-F]{6})", typography).group(1)
            self.assertGreaterEqual(contrast(value, "#f5f6f2"), 4.5, f"{token} {value} on the sidebar rail")
        placeholder = re.search(r"#ppc-input::placeholder\s*\{[^}]*color\s*:\s*(#[0-9a-fA-F]{6})", typography).group(1)
        self.assertGreaterEqual(contrast(placeholder, "#ffffff"), 4.5)

    def test_independent_attestation_label_is_at_least_13px(self):
        css = (PUBLIC / "workspace.css").read_text(encoding="utf-8")
        size = re.search(r"\.independent-attestation\{[^}]*font-size:\s*([\d.]+)rem", css).group(1)
        self.assertGreaterEqual(float(size) * 16, 13.0)

    def test_reduced_motion_and_focus_rules_exist(self):
        css = (PUBLIC / "workspace.css").read_text(encoding="utf-8")
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn(".problem-item:focus-visible", css)
        self.assertIn('[role="tab"]:focus-visible', css)

    def test_dialogs_trap_focus_and_restore_it(self):
        ui = (PUBLIC / "workspace-ui.js").read_text(encoding="utf-8")
        app = (PUBLIC / "app.js").read_text(encoding="utf-8")
        self.assertIn("function trapTab", ui)
        self.assertIn("previousFocus?.focus", ui)
        self.assertIn("trapTab", app)  # command overlay uses the same helper
        self.assertIn("commandOpener", app)

    def test_no_dark_theme_was_introduced(self):
        for name in STYLESHEETS:
            css = (PUBLIC / name).read_text(encoding="utf-8")
            self.assertNotIn("prefers-color-scheme: dark", css, name)


if __name__ == "__main__":
    unittest.main()
