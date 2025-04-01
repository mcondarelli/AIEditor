from multiprocessing.util import debug

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
        # TODO: check also other parameters for uniqueness
        self.name = name
        self.beg = beg
        self.end = end
        self.b_tag = f'<span class="{name}">'
        self.e_tag = '</span>'
        self.desc = desc or name
        Construct._constructs[name] = self

    @classmethod
    def all(cls):
        return cls._constructs.values()

    @classmethod
    def by_name(cls, name):
        return cls._constructs.get(name)


Construct('speech', '@q{', '}q@', '‟', '”', desc='Direct speech (quotes)')
for name in SPECIAL_NAMES:
    Construct(name.lower(), f'@Q[{name}]{{', '}Q@', '«', '»', desc='Special speech (guillemots)')
Construct('italic-txt', '@e{', '}e@', desc='Enhanced text (italics)')
Construct('bold-txt', '@b{', '}b@', desc='Bold text')


class NovelDocument(QTextDocument):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUndoRedoEnabled(True)

    def setAnnotatedText(self, text):
        """Parse marked-up text using the specified algorithm"""
        log.debug('=============== setAnnotatedText() ================')
        self.clear()
        cursor = QTextCursor(self)
        cursor.beginEditBlock()

        pos = 0
        stack = []
        text_length = len(text)

        while pos < text_length:
            # Find next construct boundary (step 2)
            log.debug(f'Searching next in "{text[pos:].replace('\n', '\\n')}"')
            next_boundary = text_length
            construct = None
            begin = None
            # Check all possible construct starts
            for _cons in Construct.all():
                # Find start markers
                index = text.find(_cons.beg, pos)
                if index != -1 and index < next_boundary:
                    next_boundary = index
                    construct = _cons
                    begin = True

                # Find end markers
                index = text.find(_cons.end, pos)
                if index != -1 and index < next_boundary:
                    next_boundary = index
                    construct = _cons
                    begin = False
            # handle EOL special case: close all outstanding blocks
            index = text.find('\n', pos)
            if index != -1 and index < next_boundary:
                next_boundary = index+1
                construct = None
                begin = None

            # Handle text before boundary (step 3)
            if next_boundary > pos:
                current_text = text[pos:next_boundary]
                current_name = '+'.join(stack)
                char_format = QTextCharFormat()
                char_format.setProperty(QTextFormat.Property.UserProperty, current_name)
                for name in stack:
                    match name:
                        case 'speech':
                            char_format.setForeground(Qt.GlobalColor.darkGreen)
                        case 'italic-txt':
                            char_format.setFontItalic(True)
                        case 'bold-txt':
                            char_format.setFontWeight(QFont.Weight.Bold)
                        case  'afro' | 'isto' | 'thano' | 'posse' | 'zeo' | 'palla' | 'dionne' | 'dana' | 'festo' | 'ipno' | 'asclep' | 'opia':
                            char_format.setForeground(Qt.GlobalColor.darkMagenta)  # Add color for special quotes
                cursor.insertText(current_text, char_format)
                log.debug(f'Adding block [{current_name}]: "{current_text.replace('\n', '\\n')}"')

            # in any case move after
            pos = next_boundary

            # then handle construct found
            if construct is not None:
                if begin:
                    pos += len(construct.beg)
                    stack.append(construct.name)
                else:
                    pos += len(construct.end)
                    top = stack.pop()
                    if top != construct.name:
                        log.error(f'expecting {top}, got {construct.end}')
            elif begin is None:
                if stack:
                    log.error(f'EOL with non-empty stack: {"+".join(stack)}')
                    stack.clear()

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
            previous_fmt =  ''
            while not iterator.atEnd():
                fragment = iterator.fragment()
                txt = fragment.text()
                fmt = fragment.charFormat().property(QTextFormat.Property.UserProperty) or ''
                # see if some construct should be cleaned
                curr = fmt.split('+')
                prev = previous_fmt.split('+')
                for i in reversed(range(max(len(curr),len(prev)))):
                    prev_name = prev[i] if i < len(prev) else None
                    curr_name = curr[i] if i < len(curr) else None
                    if prev_name != curr_name:
                        if prev_name:
                            # block end, close construct
                            construct = Construct.by_name(prev_name)
                            line.append(construct.end)
                            log,debug(f'closing construct {prev_name}: {construct.end}')
                        if curr_name:
                            # new block, open construct
                            construct = Construct.by_name(curr_name)
                            line.append(construct.beg)
                            log, debug(f'opening construct {curr_name}: {construct.beg}')
                log.debug(f'Text: {txt}  construct: {fmt or "NONE"}')
                line.append(txt)
                previous_fmt = fmt
                iterator += 1
            # close remaining tags, if any
            for name in reversed(previous_fmt.split('+')):
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
