from typing import Optional, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument, QTextCursor, QTextCharFormat, QTextFormat, QFont
from PyQt6.QtWidgets import QApplication, QTextEdit

from logging_config import LoggingConfig

log = LoggingConfig.get_logger('edit', _default=4)

SPECIAL_NAMES = ['Afro', 'Isto', 'Thano', 'Posse', 'Zeo', 'Palla', 'Dionne', 'Dana', 'Fest', 'Ipno', 'Asclep', 'Opia']


class Construct:
    _constructs = {}

    def __init__(self, name, beg, end, b_glyph='', e_glyph='', desc=None):
        if name in Construct._constructs:
            raise ValueError(f'Duplicate Construct name "{name}"')
        self.name = name
        self.beg = beg
        self.end = end
        self.b_glyph = b_glyph
        self.e_glyph = e_glyph
        self.b_tag = f'<span class="{name.lower()}">'
        self.e_tag = '</span>'
        self.desc = desc or name
        Construct._constructs[name] = self

    @classmethod
    def all(cls):
        return cls._constructs.values()

    @classmethod
    def by_name(cls, name):
        return cls._constructs.get(name)


# Initialize constructs
Construct('Speech', '@q{', '}q@', '‟', '”', desc='Direct speech (quotes)')
for name in SPECIAL_NAMES:
    Construct(name, f'@Q[{name}]{{', '}Q@', '«', '»', desc=f'Special quote ({name})')
Construct('Italic', '@e{', '}e@', desc='Enhanced text (italics)')
Construct('Bold', '@b{', '}b@', desc='Bold text')


class NovelDocument(QTextDocument):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUndoRedoEnabled(True)

    def setAnnotatedText(self, text):
        """Parse marked-up text using the specified algorithm"""

        ### utility functions, they could be inlined but this improves readability
        def find_next_boundary(pos: int) -> (int, str, Construct, bool):
            """
            Utility function to find next boundary in input text which could be:
            - a Construct.beg marker
            - a Construct.end marker
            - EOL
            :param pos: where to start searching in `text` (global, RO)
            :return: a tuple containing:
                     - pos of next char to scan (i.e.: beyond marker found
                     - text between original pos and current boundary
                     - construct boundary found (Construct or None if EOL)
                     - bool indicating it's an opening or closing boundary (None if EOL)
            """
            log.debug(f'find_next_boundary({pos}): "{text[pos:].replace("\n", "\\n")}"')
            next_boundary = text_length
            const: Optional[Construct] = None
            begin = None
            # Check all possible construct starts
            for _cons in Construct.all():
                # Find start markers
                index = text.find(_cons.beg, pos)
                if index != -1 and index < next_boundary:
                    next_boundary = index
                    const = _cons
                    begin = True

                # Find end markers
                index = text.find(_cons.end, pos)
                if index != -1 and index < next_boundary:
                    next_boundary = index
                    const = _cons
                    begin = False

            # handle EOL special case: close all outstanding blocks
            index = text.find('\n', pos)
            if index != -1 and index < next_boundary:
                next_boundary = index
                const = None
                begin = None

            span_text = text[pos:next_boundary]
            next_boundary += len(const.beg) if const and begin else len(const.end) if const else 1
            return next_boundary, span_text, const, begin

        def get_format(stack: List[str]) -> QTextFormat:
            chr_fmt = QTextCharFormat()
            # Apply construct formatting
            for const in stack:
                if const == 'Speech':
                    chr_fmt.setForeground(Qt.GlobalColor.darkGreen)
                elif const == 'Italic':
                    chr_fmt.setFontItalic(True)
                elif const == 'Bold':
                    chr_fmt.setFontWeight(QFont.Weight.Bold)
                elif const in SPECIAL_NAMES:
                    chr_fmt.setForeground(Qt.GlobalColor.darkMagenta)
            return chr_fmt

        log.debug('=============== setAnnotatedText() ================')
        self.clear()
        cursor = QTextCursor(self)
        cursor.beginEditBlock()

        pos = 0
        stack = []
        text_length = len(text)

        while pos < text_length:
            # Find next construct boundary

            pos, current_text, construct, begin = find_next_boundary(pos)
            # Handle text before boundary it has to be emitted with "previous" formatting
            if current_text:
                # we have text, emit it with old visuals
                current_name = '+'.join(stack)
                char_format = get_format(stack)
                char_format.setProperty(QTextFormat.Property.UserProperty, current_name)
                cursor.insertText(current_text, char_format)
                log.debug(f'Adding block [{current_name}]: "{current_text.replace("\n", "\\n")}"')

            if construct:
                if begin:
                    # begin tag: update stack and then emit
                    stack.append(construct.name)
                    if construct.b_glyph:
                        fmt = get_format(stack)
                        # insert beg glyph
                        fmt.setProperty(QTextFormat.Property.UserProperty + 2, True)
                        cursor.insertText(construct.b_glyph, fmt)
                else:
                    # end tag, emit it and then pop stack
                    if construct.e_glyph:
                        fmt = get_format(stack)
                        # insert end glyph
                        fmt.setProperty(QTextFormat.Property.UserProperty + 2, True)
                        cursor.insertText(construct.e_glyph, fmt)
                    if stack:
                        top = stack.pop()
                        if top != construct.name:
                            log.error(f'expecting {top}, got {construct.end}')
                    else:
                        log.error(f'got unexpected {construct.end} (stack is empty)')
            else:
                # EOL, stack should be empty, if not emit all end glyphs
                if stack:
                    log.error(f'EOL with unterminated constructs')
                    while stack:
                        name = stack[-1]
                        construct = Construct.by_name(name)
                        if construct.e_glyph:
                            fmt = get_format(stack)
                            # insert end glyph
                            fmt.setProperty(QTextFormat.Property.UserProperty + 2, True)
                            cursor.insertText(construct.e_glyph, fmt)
                        stack.pop()
                cursor.insertText('\n')

        cursor.endEditBlock()
        log.debug('===================================================')

    def toAnnotatedText(self):
        """Convert QTextDocument back to marked-up text with proper nesting"""
        log.debug('================ toAnnotatedText() ================')
        text = []

        block = self.begin()

        while block.isValid():
            iterator = block.begin()
            line = []
            prev_fmt = ''

            while not iterator.atEnd():
                fragment = iterator.fragment()

                fmt = fragment.charFormat()
                # Skip glyph fragments
                if fmt.property(QTextFormat.Property.UserProperty + 2):
                    iterator += 1
                    continue

                txt = fragment.text()
                curr_fmt = fmt.property(QTextFormat.Property.UserProperty) or ''
                # see if some construct should be cleaned
                curr = curr_fmt.split('+')
                prev = prev_fmt.split('+')
                for i in reversed(range(max(len(curr),len(prev)))):
                    prev_name = prev[i] if i < len(prev) else None
                    curr_name = curr[i] if i < len(curr) else None
                    if prev_name != curr_name:
                        if prev_name:
                            # block end, close construct
                            construct = Construct.by_name(prev_name)
                            line.append(construct.end)
                            log.debug(f'Closing construct {prev_name}: {construct.end}')
                        if curr_name:
                            # new block, open construct
                            construct = Construct.by_name(curr_name)
                            line.append(construct.beg)
                            log.debug(f'Opening construct {curr_name}: {construct.beg}')
                log.debug(f'Text: {txt}  construct: {curr_fmt or "NONE"}')
                line.append(txt)
                prev_fmt = curr_fmt
                iterator += 1
            # close remaining tags, if any
            for name in reversed(prev_fmt.split('+')):
                if name:
                    # new block, open construct
                    construct = Construct.by_name(name)
                    line.append(construct.end)
            text.append(''.join(line))
            block = block.next()

        log.debug('===================================================')
        return '\n'.join(text)


class NovelEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._document = NovelDocument()
        self.setDocument(self._document)

    def setPlainText(self, text):
        self._document.setAnnotatedText(text)

    def toPlainText(self):
        return self._document.toAnnotatedText()

    def _print_all_fragments(self):
        block = self.document().begin()
        while block.isValid():
            iterator = block.begin()
            log.debug(f'*** Block {block.text()}')
            while not iterator.atEnd():
                fragment = iterator.fragment()
                fmt = fragment.charFormat()
                txt = fragment.text()
                curr_fmt = fmt.property(QTextFormat.Property.UserProperty) or ''
                curr = curr_fmt.split('+')
                log.debug(f'    Fragment {curr} {txt}')

                iterator += 1
            block = block.next()


    def _get_constructs_at_position(self, pos):
        """Get construct stack at given position"""
        block = self.document().findBlock(pos)
        # Move to the fragment containing the position
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            frag_start = fragment.position()
            frag_end = frag_start + fragment.length()
            if frag_start <= pos < frag_end:
                fmt = fragment.charFormat()
                current_stack = fmt.property(QTextFormat.Property.UserProperty) or ''
                return current_stack.split('+') if current_stack else []
            iterator += 1
        return []

    def contextMenuEvent(self, event):
        """Handle right-click with selection detection"""
        mouse_pos = event.pos()
        cursor = self.cursorForPosition(mouse_pos)
        char_pos = cursor.position()

        # Get current selection info
        selection = self.textCursor()
        has_selection = selection.hasSelection()
        in_selection = (has_selection and selection.selectionStart() <= char_pos <= selection.selectionEnd())

     # Get constructs at position
        constructs = self._get_constructs_at_position(char_pos)
        log.info(f"Constructs at position: {constructs}, "
                 f"Right-click at {char_pos}, "
                 f"Selection: {'YES' if has_selection else 'NO'}, "
                 f"In selection: {'YES' if in_selection else 'NO'}")

        super().contextMenuEvent(event)
if __name__ == "__main__":
    import sys

    LoggingConfig.configure()
    app = QApplication(sys.argv)

    editor = NovelEditor()
    test_text = """Sample text
@q{Direct speech}q@
@e{Italic text with @b{nested bold}b@}e@
@Q[Afro]{Special quote}Q@
@q{Outer speech @q{inner speech}q@ continues}q@
Unclosed @q{construct
Plain text line"""
    editor.setPlainText(test_text)
    editor.show()

    # Verify round-trip conversion
    round_trip = editor.toPlainText()
    print("Original:", repr(test_text))
    print("Round-trip:", repr(round_trip))
    print("Match:", test_text == round_trip)

    sys.exit(app.exec())
