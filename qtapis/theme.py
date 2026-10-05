"""Design tokens and the application stylesheet.

Colors mirror the frontmatter of design/design.md, which is the palette the
Stitch mock (design/stitch_public_apis_qt_browser/*/code.html) actually renders.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

# --------------------------------------------------------------------------
# Color tokens
# --------------------------------------------------------------------------

SURFACE = "#131319"
SURFACE_DIM = "#131319"
SURFACE_BRIGHT = "#39383f"
CONTAINER_LOWEST = "#0d0e13"
CONTAINER_LOW = "#1b1b21"
CONTAINER = "#1f1f25"
CONTAINER_HIGH = "#2a2930"
CONTAINER_HIGHEST = "#34343b"
ON_SURFACE = "#e4e1ea"
ON_SURFACE_VARIANT = "#bcc9ce"
OUTLINE = "#869398"
OUTLINE_VARIANT = "#3d494d"

PRIMARY = "#4cd6fb"
ON_PRIMARY = "#003642"
PRIMARY_CONTAINER = "#00b4d8"
ON_PRIMARY_CONTAINER = "#00414f"

SECONDARY = "#57e163"
ON_SECONDARY = "#00390b"
SECONDARY_CONTAINER = "#00a832"
ON_SECONDARY_CONTAINER = "#003208"

TERTIARY = "#ddb7ff"
ON_TERTIARY = "#490080"

ERROR = "#ffb4ab"
ON_ERROR = "#690005"
ERROR_CONTAINER = "#93000a"
ON_ERROR_CONTAINER = "#ffdad6"

# Aliases used by the component specs in DESIGN.md sections 5-7.
SELECTION = "#003547"
AMBER = "#f59e0b"
PURPLE = "#a855f7"
RED = "#ef4444"
TEXT_PRIMARY = "#f0f0f5"
TEXT_SECONDARY = "#a0a0b0"
TEXT_TERTIARY = "#6e6e80"


def alpha(hex_color: str, a: float) -> QColor:
    """Return `hex_color` as a QColor with alpha applied (a in 0.0 - 1.0)."""
    c = QColor(hex_color)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


# --------------------------------------------------------------------------
# Typography
# --------------------------------------------------------------------------

# Preferred webfont -> local fallbacks, in order. The first two are bundled in
# assets/fonts and registered at startup; the rest cover stripped-down installs.
_SANS_STACK = ("Inter", "Segoe UI", "SF Pro Text", "Roboto", "Arial")
_MONO_STACK = ("JetBrains Mono", "Cascadia Mono", "Consolas", "SF Mono", "Menlo")


def _pick_family(stack: tuple[str, ...], fallback: str) -> str:
    available = set(QFontDatabase.families())
    for name in stack:
        if name in available:
            return name
    return fallback


def sans_family() -> str:
    return _pick_family(_SANS_STACK, "sans-serif")


def mono_family() -> str:
    return _pick_family(_MONO_STACK, "monospace")


def font(role: str) -> QFont:
    """Build a QFont for one of the design's named typography roles."""
    spec = TYPOGRAPHY[role]
    family = sans_family() if spec["family"] == "sans" else mono_family()
    f = QFont(family)
    f.setPointSizeF(spec["size"])
    f.setWeight(spec["weight"])
    f.setStyleStrategy(QFont.PreferAntialias)
    return f


# size (pt), weight, family selector ("sans" | "mono")
TYPOGRAPHY: dict[str, dict] = {
    "headline-lg": {"family": "sans", "size": 12.0, "weight": QFont.Bold, "track": -0.01},
    "headline-md": {"family": "sans", "size": 10.5, "weight": QFont.DemiBold, "track": -0.005},
    "body-md": {"family": "sans", "size": 10.0, "weight": QFont.Normal, "track": 0.0},
    "body-sm": {"family": "sans", "size": 9.5, "weight": QFont.Normal, "track": 0.0},
    "label-titlebar": {"family": "sans", "size": 9.5, "weight": QFont.DemiBold, "track": 0.02},
    "label-menubar": {"family": "sans", "size": 9.5, "weight": QFont.Normal, "track": 0.01},
    "label-header": {"family": "sans", "size": 8.5, "weight": QFont.Bold, "track": 0.06},
    "label-tree": {"family": "sans", "size": 9.5, "weight": QFont.Medium, "track": 0.0},
    "label-badge": {"family": "mono", "size": 8.0, "weight": QFont.DemiBold, "track": 0.04},
    "code-sm": {"family": "mono", "size": 8.5, "weight": QFont.Medium, "track": 0.0},
    "code-md": {"family": "mono", "size": 9.5, "weight": QFont.Medium, "track": 0.0},
    "label-statusbar": {"family": "sans", "size": 8.5, "weight": QFont.Normal, "track": 0.0},
}


# --------------------------------------------------------------------------
# Layout metrics (DESIGN.md "Layout Model")
# --------------------------------------------------------------------------

TITLEBAR_H = 32
MENUBAR_H = 28
TOOLBAR_H = 44
SIDEBAR_W = 240
SIDEBAR_MIN_W = 44
INSPECTOR_W = 380
STATUSBAR_H = 24
TABLE_ROW_H = 30
HEADER_H = 28

RAD_DEFAULT = 2
RAD_INPUT = 4

# Spacing rhythm from DESIGN.md "Component Spacing Rhythm".
SPACING_PX = {
    "space-xs": 2,
    "space-sm": 4,
    "space-md": 8,
    "space-lg": 12,
    "space-xl": 16,
}


def space_px(token: str) -> int:
    """Resolve a design spacing token to pixels."""
    return SPACING_PX[token]


def stylesheet() -> str:
    """Global QSS built from the tokens above."""
    return f"""
* {{
    outline: 0;
    font-family: "{sans_family()}";
}}

QWidget {{
    background: {SURFACE};
    color: {ON_SURFACE};
    font-size: 10pt;
}}

QToolTip {{
    background: {CONTAINER_HIGH};
    color: {ON_SURFACE};
    border: 1px solid {OUTLINE_VARIANT};
    padding: 4px 6px;
}}

/* ---------------- Title bar ---------------- */
#titleBar {{
    background: {CONTAINER_LOW};
    border-bottom: 1px solid {OUTLINE_VARIANT};
}}
#titleBarLabel {{
    font-family: "{sans_family()}";
    font-size: 9.5pt;
    font-weight: 600;
    color: {ON_SURFACE};
    background: transparent;
}}
#titleBarVersion {{
    font-family: "{mono_family()}";
    font-size: 8.5pt;
    color: {OUTLINE_VARIANT};
    background: transparent;
}}
#avatar {{
    background: {PRIMARY};
    border-radius: 14px;
    color: {ON_PRIMARY};
    font-size: 10pt;
    font-weight: 600;
}}
#winMin, #winMax {{
    background: transparent;
    border: none;
    color: {ON_SURFACE_VARIANT};
    font-size: 13pt;
}}
#winMin:hover, #winMax:hover {{
    background: {SURFACE_BRIGHT};
    color: {ON_SURFACE};
}}
#winClose {{
    background: transparent;
    border: none;
    color: {ON_SURFACE_VARIANT};
    font-size: 12pt;
}}
#winClose:hover {{
    background: {ERROR_CONTAINER};
    color: {ON_ERROR_CONTAINER};
}}

/* ---------------- Menu bar ---------------- */
#menuBar {{
    background: {CONTAINER};
    border-bottom: 1px solid {OUTLINE_VARIANT};
}}
#menuBar QMenuBar::item {{
    background: transparent;
    padding: 3px 8px;
    margin: 0 2px;
    border-radius: {RAD_DEFAULT}px;
    color: {ON_SURFACE_VARIANT};
    font-size: 9.5pt;
}}
#menuBar QMenuBar::item:selected {{
    background: {SURFACE_BRIGHT};
    color: {ON_SURFACE};
}}
#menuBar QMenuBar::item:pressed {{
    background: {PRIMARY_CONTAINER};
    color: {ON_PRIMARY_CONTAINER};
}}
QMenu {{
    background: {CONTAINER};
    border: 1px solid {OUTLINE_VARIANT};
    border-radius: {RAD_DEFAULT}px;
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 26px 5px 22px;
    border-radius: {RAD_DEFAULT}px;
    color: {ON_SURFACE};
    font-size: 9.5pt;
}}
QMenu::item:selected {{
    background: {SURFACE_BRIGHT};
}}
QMenu::item:disabled {{
    color: {TEXT_TERTIARY};
}}
QMenu::separator {{
    height: 1px;
    background: {OUTLINE_VARIANT};
    margin: 4px 8px;
}}
QMenu::icon {{ padding-left: 8px; }}

/* ---------------- Toolbar ---------------- */
#toolbar {{
    background: {CONTAINER_HIGH};
    border-bottom: 1px solid {OUTLINE_VARIANT};
}}
#searchWell {{
    background: {CONTAINER_LOWEST};
    border: 1px solid {OUTLINE_VARIANT};
    border-radius: {RAD_DEFAULT}px;
}}
#searchWell:focus {{
    border-color: {PRIMARY};
}}
#searchInput {{
    background: transparent;
    border: none;
    color: {ON_SURFACE};
    font-size: 9.5pt;
    selection-background-color: {PRIMARY_CONTAINER};
    selection-color: {ON_PRIMARY_CONTAINER};
}}
#searchClear {{
    background: transparent;
    border: none;
    color: {OUTLINE};
    font-size: 10pt;
    padding: 0 4px;
}}
#searchClear:hover {{ color: {ON_SURFACE}; }}
#searchHint {{
    background: {CONTAINER};
    color: {OUTLINE};
    border-radius: {RAD_DEFAULT}px;
    font-family: "{mono_family()}";
    font-size: 8pt;
    font-weight: 600;
    padding: 1px 4px;
}}
#toolButton {{
    background: {CONTAINER};
    border: 1px solid {OUTLINE_VARIANT};
    border-radius: {RAD_DEFAULT}px;
    color: {ON_SURFACE_VARIANT};
    font-size: 9.5pt;
    padding: 4px 8px;
}}
#toolButton:hover {{
    background: {SURFACE_BRIGHT};
    color: {ON_SURFACE};
}}
#toolButton:checked {{
    background: {PRIMARY_CONTAINER};
    color: {ON_PRIMARY_CONTAINER};
    border-color: {PRIMARY_CONTAINER};
}}
#toolButtonAccent:checked {{
    background: {CONTAINER};
    color: {SECONDARY};
    border-color: {SECONDARY_CONTAINER};
}}
#toolButtonAccent:hover {{ color: {SECONDARY}; }}
#segmented {{
    background: {CONTAINER_LOWEST};
    border-radius: {RAD_DEFAULT}px;
    padding: 2px;
}}
#segmented QToolButton {{
    background: transparent;
    border: none;
    border-radius: {RAD_DEFAULT}px;
    color: {OUTLINE};
    font-size: 11pt;
    padding: 3px 6px;
}}
#segmented QToolButton:hover {{ color: {ON_SURFACE}; }}
#segmented QToolButton:checked {{
    background: {CONTAINER};
    color: {PRIMARY};
}}

QComboBox {{
    background: {CONTAINER};
    border: 1px solid {OUTLINE_VARIANT};
    border-radius: {RAD_DEFAULT}px;
    color: {ON_SURFACE_VARIANT};
    font-size: 9.5pt;
    padding: 4px 8px;
    min-height: 18px;
}}
QComboBox:hover {{
    background: {SURFACE_BRIGHT};
    color: {ON_SURFACE};
}}
QComboBox::drop-down {{
    border: none;
    width: 16px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {OUTLINE};
    width: 0; height: 0;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {CONTAINER};
    border: 1px solid {OUTLINE_VARIANT};
    border-radius: {RAD_DEFAULT}px;
    padding: 2px;
    outline: none;
    selection-background-color: {PRIMARY_CONTAINER};
    selection-color: {ON_PRIMARY_CONTAINER};
}}
QComboBox QAbstractItemView::item {{
    padding: 4px 8px;
    border-radius: {RAD_DEFAULT}px;
    color: {ON_SURFACE};
    min-height: 20px;
}}

/* ---------------- Sidebar ---------------- */
#sidebar {{
    background: {CONTAINER_LOW};
    border-right: 1px solid {OUTLINE_VARIANT};
}}
#sidebarHeader {{
    background: {CONTAINER};
    border-bottom: 1px solid {OUTLINE_VARIANT};
}}
#sidebarHeaderLabel, #subheaderLabel {{
    color: {OUTLINE};
    font-size: 8.5pt;
    font-weight: 700;
    letter-spacing: 1.1px;
    background: transparent;
}}
#sidebarCollapse {{
    background: transparent;
    border: none;
    color: {OUTLINE};
    font-size: 12pt;
}}
#sidebarCollapse:hover {{ color: {ON_SURFACE}; }}

QTreeWidget {{
    background: {CONTAINER_LOW};
    border: none;
    color: {ON_SURFACE_VARIANT};
    font-size: 9.5pt;
    outline: none;
}}
QTreeWidget::item {{
    height: 26px;
    padding-left: 2px;
    border: none;
}}
QTreeWidget::item:hover {{
    background: {SURFACE_BRIGHT};
    color: {ON_SURFACE};
}}
QTreeWidget::item:selected {{
    background: {CONTAINER_HIGH};
    color: {PRIMARY};
    font-weight: 700;
}}
QTreeWidget::branch {{ background: transparent; }}

#sidebarFooter {{
    background: {CONTAINER_LOWEST};
    border-top: 1px solid {OUTLINE_VARIANT};
}}
#syncText {{
    color: {SECONDARY};
    font-family: "{mono_family()}";
    font-size: 8pt;
    font-weight: 600;
    background: transparent;
}}
#syncMeta {{
    color: {OUTLINE};
    font-family: "{mono_family()}";
    font-size: 8pt;
    background: transparent;
}}
QProgressBar {{
    background: {CONTAINER};
    border: none;
    border-radius: 2px;
    height: 4px;
    max-height: 4px;
}}
QProgressBar::chunk {{
    background: {SECONDARY};
    border-radius: 2px;
}}

/* ---------------- Splitters ---------------- */
QSplitter::handle {{
    background: {OUTLINE_VARIANT};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QSplitter::handle:hover {{ background: {PRIMARY}; }}

/* ---------------- Table workspace ---------------- */
#subheader {{
    background: {CONTAINER_LOW};
    border-bottom: 1px solid {OUTLINE_VARIANT};
}}
#subheaderText {{
    color: {ON_SURFACE_VARIANT};
    font-size: 9.5pt;
    background: transparent;
}}
#subheaderMeta {{
    color: {OUTLINE_VARIANT};
    font-family: "{mono_family()}";
    font-size: 8.5pt;
    background: transparent;
}}
#miniButton {{
    background: {CONTAINER};
    border: none;
    border-radius: {RAD_DEFAULT}px;
    color: {ON_SURFACE_VARIANT};
    font-family: "{mono_family()}";
    font-size: 8pt;
    font-weight: 600;
    padding: 3px 6px;
}}
#miniButton:hover {{
    background: {SURFACE_BRIGHT};
    color: {ON_SURFACE};
}}

QTableView {{
    background: {SURFACE};
    alternate-background-color: {CONTAINER_LOW};
    border: none;
    gridline-color: transparent;
    color: {ON_SURFACE_VARIANT};
    font-size: 9.5pt;
    selection-background-color: {SELECTION};
    selection-color: {ON_SURFACE};
    outline: none;
}}
QTableView::item {{
    border: none;
    padding-left: 8px;
    padding-right: 8px;
}}
QTableView::item:hover {{ background: {alpha(SURFACE_BRIGHT, 0.55).name(QColor.HexArgb)}; }}
QTableView::item:selected {{ background: {SELECTION}; }}

QHeaderView {{ background: {CONTAINER}; }}
QHeaderView::section {{
    background: {CONTAINER};
    color: {ON_SURFACE_VARIANT};
    border: none;
    border-bottom: 1px solid {OUTLINE_VARIANT};
    border-right: 1px solid {alpha(OUTLINE_VARIANT, 0.5).name(QColor.HexArgb)};
    padding: 0 8px;
    font-size: 8.5pt;
    font-weight: 700;
    letter-spacing: 1.1px;
}}
QHeaderView::section:hover {{ background: {SURFACE_BRIGHT}; color: {ON_SURFACE}; }}
QHeaderView::section:checked {{
    background: {CONTAINER_HIGH};
    color: {PRIMARY};
    border-bottom: 2px solid {PRIMARY};
}}
QHeaderView::up-arrow, QHeaderView::down-arrow {{ width: 0; height: 0; }}

QTableCornerButton::section {{
    background: {CONTAINER};
    border: none;
    border-bottom: 1px solid {OUTLINE_VARIANT};
}}

/* ---------------- Inspector ---------------- */
#inspector {{
    background: {CONTAINER_LOW};
    border-left: 1px solid {OUTLINE_VARIANT};
}}
#inspectorHeader {{
    background: {CONTAINER_LOW};
    border-bottom: 1px solid {OUTLINE_VARIANT};
}}
#inspectorTitle {{
    color: {ON_SURFACE};
    font-size: 12pt;
    font-weight: 700;
    background: transparent;
}}
#inspectorClose {{
    background: transparent;
    border: none;
    color: {OUTLINE};
    font-size: 11pt;
}}
#inspectorClose:hover {{ color: {ON_SURFACE}; }}
#sectionLabel {{
    color: {OUTLINE};
    font-size: 8.5pt;
    font-weight: 700;
    letter-spacing: 1.1px;
    background: transparent;
}}
#fieldKey {{
    color: {OUTLINE};
    font-family: "{mono_family()}";
    font-size: 8pt;
    background: transparent;
}}
#fieldValue {{
    color: {ON_SURFACE};
    font-family: "{mono_family()}";
    font-size: 8.5pt;
    background: transparent;
}}
#descText {{
    color: {ON_SURFACE_VARIANT};
    font-size: 9.5pt;
    background: transparent;
}}
#curlWell {{
    background: {CONTAINER_LOWEST};
    border: 1px solid {OUTLINE_VARIANT};
    border-radius: {RAD_DEFAULT}px;
}}
#endpointInput {{
    background: {CONTAINER};
    border: 1px solid {OUTLINE_VARIANT};
    border-radius: {RAD_DEFAULT}px;
    color: {ON_SURFACE};
    font-family: "{mono_family()}";
    font-size: 8.5pt;
    padding: 3px 6px;
    min-height: 16px;
}}
#endpointInput:focus {{ border-color: {PRIMARY}; }}
#endpointInput::placeholder {{ color: {OUTLINE}; }}
#curlText {{
    background: transparent;
    border: none;
    color: {PRIMARY};
    font-family: "{mono_family()}";
    font-size: 8.5pt;
    padding: 6px;
    selection-background-color: {PRIMARY_CONTAINER};
    selection-color: {ON_PRIMARY_CONTAINER};
}}
#primaryCta {{
    background: {PRIMARY_CONTAINER};
    border: 1px solid {PRIMARY_CONTAINER};
    border-radius: {RAD_INPUT}px;
    color: #081720;
    font-size: 9.5pt;
    font-weight: 700;
    padding: 7px 10px;
}}
#primaryCta:hover {{ background: {PRIMARY}; border-color: {PRIMARY}; }}
#primaryCta:disabled {{
    background: {CONTAINER_HIGH};
    border-color: {OUTLINE_VARIANT};
    color: {TEXT_TERTIARY};
}}
#secondaryCta {{
    background: #2b2e38;
    border: 1px solid {OUTLINE_VARIANT};
    border-radius: {RAD_INPUT}px;
    color: {TEXT_PRIMARY};
    font-size: 9.5pt;
    padding: 7px 10px;
}}
#secondaryCta:hover {{ background: {SURFACE_BRIGHT}; }}
#secondaryCta:disabled {{ color: {TEXT_TERTIARY}; }}
#emptyState {{
    color: {TEXT_TERTIARY};
    font-size: 9.5pt;
    background: transparent;
}}

/* ---------------- Status bar ---------------- */
#statusBar {{
    background: {CONTAINER_LOWEST};
    border-top: 1px solid {OUTLINE_VARIANT};
}}
#statusLeft, #statusRight {{
    color: {OUTLINE};
    font-size: 8.5pt;
    background: transparent;
}}
#statusDot {{
    border-radius: 4px;
    background: {SECONDARY};
}}

/* ---------------- Scrollbars ---------------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {CONTAINER_HIGHEST};
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {SURFACE_BRIGHT}; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {CONTAINER_HIGHEST};
    border-radius: 4px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: {SURFACE_BRIGHT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0; height: 0; border: none; background: none;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QScrollBar:horizontal {{ background: {CONTAINER_LOWEST}; }}
"""