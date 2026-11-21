"""Static asset checks for the redesigned travel simulator web UI."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[3] / "travel_sim" / "web_static"
STATIC_FILES = ("index.html", "app.js", "style.css")


class _StaticHtmlInspector(HTMLParser):
    """Collects form controls, labels, scripts, styles, and details elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.controls: list[dict[str, str | bool | None]] = []
        self.label_fors: set[str] = set()
        self.inline_style_tags: int = 0
        self.style_attrs: list[str] = []
        self.inline_event_attrs: list[str] = []
        self.scripts: list[dict[str, object]] = []
        self.details_open: dict[str, bool] = {}
        self._label_depth = 0
        self._current_script: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr_map = {k.lower(): v for k, v in attrs}

        if "style" in attr_map:
            self.style_attrs.append(tag_lower)
        for attr_name in attr_map:
            if attr_name.startswith("on"):
                self.inline_event_attrs.append(f"{tag_lower}.{attr_name}")

        if tag_lower == "style":
            self.inline_style_tags += 1

        if tag_lower == "script":
            self._current_script = {
                "has_src": "src" in attr_map and bool(attr_map["src"]),
                "body": "",
            }
            self.scripts.append(self._current_script)

        if tag_lower == "label":
            self._label_depth += 1
            for_id = attr_map.get("for")
            if for_id:
                self.label_fors.add(for_id)

        if tag_lower in ("input", "select", "textarea"):
            input_type = (attr_map.get("type") or "").lower()
            if input_type not in ("hidden", "submit", "button", "reset"):
                self.controls.append(
                    {
                        "tag": tag_lower,
                        "id": attr_map.get("id"),
                        "name": attr_map.get("name"),
                        "wrapped_in_label": self._label_depth > 0,
                    }
                )

        if tag_lower == "details":
            details_id = attr_map.get("id") or f"details-{len(self.details_open)}"
            self.details_open[details_id] = "open" in attr_map

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower == "label" and self._label_depth > 0:
            self._label_depth -= 1
        if tag_lower == "script":
            self._current_script = None

    def handle_data(self, data: str) -> None:
        if self._current_script is not None:
            self._current_script["body"] = str(self._current_script["body"]) + data


def _read_static(filename: str) -> str:
    return (STATIC_DIR / filename).read_text(encoding="utf-8")


def test_static_files_exist_and_are_non_empty() -> None:
    for filename in STATIC_FILES:
        path = STATIC_DIR / filename
        assert path.is_file(), f"Missing static asset: {path}"
        assert path.stat().st_size > 0, f"Empty static asset: {path}"


def test_static_files_have_no_external_urls_or_unsafe_dom_apis() -> None:
    forbidden_tokens = (
        "http://",
        "https://",
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "eval(",
    )
    for filename in STATIC_FILES:
        content = _read_static(filename)
        for token in forbidden_tokens:
            assert token not in content, f"Forbidden token {token!r} found in {filename}"


def test_index_html_complies_with_strict_csp_and_accessible_labels() -> None:
    html_text = _read_static("index.html")
    inspector = _StaticHtmlInspector()
    inspector.feed(html_text)
    inspector.close()

    assert inspector.inline_style_tags == 0, "Inline <style> tags violate strict CSP"
    assert not inspector.style_attrs, f"Inline style= attributes found: {inspector.style_attrs}"
    assert not inspector.inline_event_attrs, (
        f"Inline event handlers found: {inspector.inline_event_attrs}"
    )

    assert len(inspector.scripts) >= 1
    for script in inspector.scripts:
        assert script["has_src"] is True, "Every <script> must reference an external local src"
        assert str(script["body"]).strip() == "", "Inline <script> body violates strict CSP"

    assert len(inspector.controls) >= 12
    for control in inspector.controls:
        ctrl_id = control["id"]
        assert isinstance(ctrl_id, str) and ctrl_id, f"Form control missing id: {control}"
        has_label = bool(control["wrapped_in_label"]) or (ctrl_id in inspector.label_fors)
        assert has_label, f"Form control {ctrl_id!r} has no associated <label>"

    assert inspector.details_open.get("manual-data-details") is False
    assert inspector.details_open.get("rejected-details") is False


def test_trip_description_form_sections_and_plain_choices_present() -> None:
    html_text = _read_static("index.html")
    expected_phrases = (
        "Describe tu viaje",
        "Tu viaje",
        "Quién viaja",
        "Tu teléfono y datos",
        "Tengo RUT o cédula chilena",
        "Prefiero lo simple",
        "Equilibrio",
        "Me da igual el esfuerzo",
        "Solo eSIM",
        "Solo SIM física",
        "Ambas",
        "Ligero (mapas y mensajes)",
        "Normal (redes y mapas)",
        "Intenso (video y hotspot)",
        "Ajustar a mano",
    )
    for phrase in expected_phrases:
        assert phrase in html_text, f"Missing expected form text {phrase!r} in index.html"


def test_category_headings_and_required_result_labels_present_in_order() -> None:
    html_text = _read_static("index.html")
    app_js = _read_static("app.js")
    combined = html_text + "\n" + app_js

    required_headings = (
        "Conectividad",
        "Transporte",
        "Escapadas",
        "Comida",
        "Pagos",
    )
    for heading in required_headings:
        assert heading in combined, f"Missing category heading {heading!r}"

    ordered_titles = (
        'title: "Conectividad"',
        'title: "Transporte"',
        'title: "Escapadas"',
        'title: "Comida"',
        'title: "Pagos y divisas"',
    )
    positions = [app_js.index(title) for title in ordered_titles]
    assert positions == sorted(positions), "Category sections are not ordered as specified"

    assert "Sin datos todavía" in app_js
    assert "estimado / sin verificar" in app_js


def test_gb_presets_defined_once_in_app_js() -> None:
    app_js = _read_static("app.js")
    preset_decls = re.findall(r"const\s+DATA_USAGE_PRESETS\s*=", app_js)
    assert len(preset_decls) == 1, "DATA_USAGE_PRESETS must be defined exactly once in app.js"

    match = re.search(
        r"const\s+DATA_USAGE_PRESETS\s*=\s*Object\.freeze\(\s*\{(.*?)\}\s*\)",
        app_js,
        flags=re.DOTALL,
    )
    assert match is not None, "DATA_USAGE_PRESETS definition not found"
    body = match.group(1)

    assert len(re.findall(r"\bLIGHT\s*:\s*3\b", body)) == 1
    assert len(re.findall(r"\bNORMAL\s*:\s*10\b", body)) == 1
    assert len(re.findall(r"\bINTENSE\s*:\s*30\b", body)) == 1
    assert len(re.findall(r"\bLIGHT\s*:\s*3\b", app_js)) == 1
    assert len(re.findall(r"\bNORMAL\s*:\s*10\b", app_js)) == 1
    assert len(re.findall(r"\bINTENSE\s*:\s*30\b", app_js)) == 1
