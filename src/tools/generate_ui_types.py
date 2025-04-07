#!/usr/bin/env python3
"""
Improved UI type generator with:
- Proper Qt class filtering
- Correct indentation
- Path handling fixes
"""
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Dict

# Match Qt Designer's default widget naming pattern
DEFAULT_WIDGET_PATTERN = re.compile(r'^[a-z]+(?:_\d+)?$')
QT_WIDGET_CLASSES = {
    'QAbstractButton', 'QComboBox', 'QFrame', 'QGroupBox', 'QLabel',
    'QLineEdit', 'QMainWindow', 'QMenu', 'QMenuBar', 'QPushButton',
    'QStatusBar', 'QTextEdit', 'QVBoxLayout', 'QHBoxLayout', 'QWidget'
    # Add other Qt classes you use
}
HEADER = "# --- AUTO-GENERATED from UI file - DO NOT EDIT ---"
FOOTER = "# --- END AUTO-GENERATED ---"


def extract_custom_widgets(ui_file: Path) -> Dict[str, str]:
    """Extracts custom widget classes with proper headers"""
    try:
        tree = ET.parse(ui_file)
        return {w.find('class').text: w.find('header').text for w in tree.findall('.//customwidget')}
    except (AttributeError, ET.ParseError):
        return {}


def extract_named_widgets(ui_file: Path) -> (Dict[str, str], Dict[str, str]):
    """Extracts only properly named widgets with correct types"""
    tree = ET.parse(ui_file)
    custom_widgets = extract_custom_widgets(ui_file)
    widgets = {}

    allowed_classes = QT_WIDGET_CLASSES.union(custom_widgets.keys())

    for widget in tree.findall('.//widget'):  # iterate only on widgets
        if not (name := widget.get('name')):  # we need a name
            continue
        if name in custom_widgets:            # handled separately
            continue

        if not (clazz := widget.get('class')):  # and we need a class name
            continue

        default_name = re.sub(r'^Q', '', clazz)
        default_name = default_name[0].lower() + default_name[1:]
        default_designer_name_pattern = rf'^({default_name})?(_\d+)?$'
        if re.match(default_designer_name_pattern, name):  # if name was explicitly set by user
            continue

        # Filter valid Qt widgets
        elif f"{clazz}" in allowed_classes:
            widgets[name] = f"{clazz}"

    return widgets, custom_widgets


def generate_code_block(widgets: Dict[str, str], custom_widgets: Dict[str, str]) -> str:
    """Generates properly formatted Python code"""
    qt_imports = sorted(list(QT_WIDGET_CLASSES.intersection(widgets.values())))

    lines = [
        "from typing import Optional",
        f"from PyQt6.QtWidgets import {', '.join(qt_imports)}",
        *[f"from {mod} import {cls}"
          for cls, mod in custom_widgets.items()],
        ""
    ]

    # Add widget declarations with proper indentation
    for name, qtype in sorted(widgets.items()):
        lines.append(f"self.{name}: Optional[{qtype}] = None")

    return '\n'.join(lines)


def update_py_file(ui_file: Path, code_block: str):
    """Updates Python file with proper indentation"""
    py_file = ui_file.with_suffix('.py')
    if not py_file.exists():
        print(f"Warning: {py_file} not found")
        return

    def insert_block():
        new_content.append(indent + HEADER)
        for l in code_block.splitlines():
            new_content.append(indent + l)
        new_content.append(indent + FOOTER)

    new_content = []
    indent = None
    with open(py_file, 'r') as f:
        skipping = False
        for line in f:
            line = line.rstrip()                   # make sure no trailing whitespace
            if skipping:
                if m := re.match(rf'(\s*){FOOTER}', line):
                    if indent != m[1]:
                        print(f"Warning: mismatched indent on code guards: '{indent}' != '{m[1]}'")
                        return
                    insert_block()
                    skipping = False
            else:
                if m := re.match(rf'(\s*){HEADER}', line):
                    indent = m[1]
                    skipping = True
                else:
                    if indent is None and (m := re.match(r'(\s*)(uic.)?loadUi\(.*?, self\)', line)):
                        indent = m[1]
                        insert_block()
                    new_content.append(line)       # just copy
        if skipping:
            print('Warning: unterminated code block')
            return
        if indent is None:
            print('Warning: insertion point not found')
            return

    # create backup
    bkp = py_file.with_stem(py_file.stem+'~')
    py_file.replace(bkp)

    # overwrite py file
    with open(py_file, 'w') as f:
        f.write('\n'.join(new_content))


def main():
    ui_files = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else list(Path('.').rglob('*.ui'))

    for ui_file in ui_files:
        try:
            print(f"Processing {ui_file}...")
            widgets, custom_widgets = extract_named_widgets(ui_file)
            if not widgets and not custom_widgets:
                print("No named widgets found")
                continue

            code_block = generate_code_block(widgets, custom_widgets)
            update_py_file(ui_file, code_block)
            print(f"Updated {ui_file.with_suffix('.py')}")

        except Exception as e:
            print(f"Error processing {ui_file}: {str(e)}")


if __name__ == '__main__':
    main()