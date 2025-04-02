from typing import Optional, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument, QTextCursor, QTextCharFormat, QTextFormat, QFont, QIcon
from PyQt6.QtWidgets import QApplication, QTextEdit, QFileDialog, QMessageBox

from logging_config import LoggingConfig

log = LoggingConfig.get_logger('edit', _default=4)

SPECIAL_NAMES = ['Afro', 'Isto', 'Thano', 'Posse', 'Zeo', 'Palla', 'Dionne', 'Dana', 'Fest', 'Ipno', 'Asclep', 'Opia']


class Construct:
    _constructs = {}

    def __init__(self, name, beg, end, b_glyph='', e_glyph='', desc=None, icon=None):
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
        self.icon = icon or 'dialog-question'
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

    def _get_fragment_at_position(self, pos):
        """Get fragment at exact position (returns None if not found)"""
        block = self.findBlock(pos)
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.position() <= pos < fragment.position() + fragment.length():
                return fragment
            iterator += 1
        return None

    def get_format_for_insertion(self, pos):
        """
        Get proper format for text insertion at position
        Handles EOL and glyph boundaries correctly
        """
        cursor = QTextCursor(self)
        cursor.setPosition(pos)

        # Case 1: At document end
        if pos >= self.characterCount() - 1:
            return QTextCharFormat()

        # Case 2: Check next character
        next_cursor = QTextCursor(cursor)
        next_cursor.movePosition(QTextCursor.MoveOperation.Right)

        # Check for EOL
        if next_cursor.block() != cursor.block():
            return self._get_parent_format(cursor)

        # Check for glyph
        next_fragment = self._get_fragment_at_position(next_cursor.position())
        if (next_fragment and
                next_fragment.charFormat().property(QTextFormat.Property.UserProperty + 2)):
            return self._get_parent_format(cursor)

        # Default case
        return next_cursor.charFormat()

    def _get_parent_format(self, cursor):
        """Get parent format when between constructs or glyphs"""
        if cursor.positionInBlock() > 0:
            prev_cursor = QTextCursor(cursor)
            prev_cursor.movePosition(QTextCursor.MoveOperation.Left)
            prev_fmt = prev_cursor.charFormat()
            stack = (prev_fmt.property(QTextFormat.Property.UserProperty) or '').split('+')
            if len(stack) > 1:
                return self._create_char_format(stack[:-1])
        return QTextCharFormat()

    def handle_boundary_deletion(self, cursor, is_backspace):
        """Handle deletion at glyph boundaries"""
        pos = cursor.position()
        direction = QTextCursor.MoveOperation.Left if is_backspace else QTextCursor.MoveOperation.Right

        # Get adjacent fragment
        check_pos = pos - 1 if is_backspace else pos
        fragment = self._get_fragment_at_position(check_pos)

        if fragment and fragment.charFormat().property(QTextFormat.Property.UserProperty + 2):
            # Skip glyph during deletion
            new_pos = fragment.position() if is_backspace else fragment.position() + fragment.length()
            cursor.setPosition(new_pos)
            return True
        return False

    def handle_boundary_editing(self, cursor, is_backspace=True):
        """Handle keyboard edits at glyph boundaries. Returns True if handled."""
        pos = cursor.position()
        fragment = self._get_fragment_at_position(pos - 1 if is_backspace else pos)

        if fragment and fragment.charFormat().property(QTextFormat.Property.UserProperty + 2):
            # Skip glyph during deletion
            new_pos = fragment.position() if is_backspace else fragment.position() + fragment.length()
            cursor.setPosition(new_pos)
            return True
        return False

    def validate_inserted_text(self, start_pos, text):
        """Ensure inserted text doesn't land in glyph fragments"""
        cursor = QTextCursor(self)
        cursor.beginEditBlock()

        try:
            for i in reversed(range(len(text))):  # Process backwards to maintain positions
                pos = start_pos + i
                fragment = self._get_fragment_at_position(pos)

                if fragment and fragment.charFormat().property(QTextFormat.Property.UserProperty + 2):
                    # Move character after glyph
                    cursor.setPosition(pos)
                    cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                    char = cursor.selectedText()
                    cursor.removeSelectedText()

                    new_pos = fragment.position() + fragment.length()
                    cursor.setPosition(new_pos)
                    fmt = self.get_format_for_insertion(new_pos)
                    cursor.insertText(char, fmt)
        finally:
            cursor.endEditBlock()

    def validate_text_insertion(self, insert_pos, text):
        """Fix text inserted into invalid positions"""
        cursor = QTextCursor(self)
        cursor.setPosition(insert_pos)

        for i in range(len(text)):
            pos = insert_pos + i
            fragment = self._get_fragment_at_position(pos)

            if fragment and fragment.charFormat().property(QTextFormat.Property.UserProperty + 2):
                # Remove from glyph fragment
                cursor.setPosition(pos)
                cursor.movePosition(QTextCursor.MoveOperation.Right,
                                    QTextCursor.MoveMode.KeepAnchor, 1)
                char = cursor.selectedText()

                cursor.beginEditBlock()
                cursor.removeSelectedText()

                # Insert after glyph with proper format
                cursor.setPosition(fragment.position() + fragment.length())
                fmt = self.get_format_for_insertion(cursor.position())
                cursor.insertText(char, fmt)
                cursor.endEditBlock()

    def setPlainText(self, text):
        """Override to force annotated text handling"""
        self.setAnnotatedText(text)

    def toPlainText(self):
        """Override to force annotated text handling"""
        return self.toAnnotatedText()


class NovelEditor(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._document = NovelDocument()
        self.setDocument(self._document)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._is_dirty = False
        self._document.contentsChanged.connect(self._mark_dirty)

        # Remove plaintext methods from public API
        self.setPlainText = self._hidden_set_plaintext
        self.toPlainText = self._hidden_to_plaintext

    def _hidden_set_plaintext(self, *args, **kwargs):
        """Prevent direct plaintext access"""
        raise AttributeError("Use setAnnotatedText() instead of setPlainText()")

    def _hidden_to_plaintext(self, *args, **kwargs):
        """Prevent direct plaintext access"""
        raise AttributeError("Use toAnnotatedText() instead of toPlainText()")

    def setAnnotatedText(self, text):
        """Public method for setting annotated text"""
        self._document.setAnnotatedText(text)
        self._clear_dirty()

    def toAnnotatedText(self):
        """Public method for getting annotated text"""
        return self._document.toAnnotatedText()

    def _mark_dirty(self):
        """Mark buffer as modified"""
        self._is_dirty = True

    def _clear_dirty(self):
        """Clear dirty flag"""
        self._is_dirty = False

    def maybe_save(self):
        """
        Prompt to save if buffer is dirty.
        Returns QMessageBox.StandardButton:
            Yes - saved successfully
            No - discard changes
            Cancel - abort operation
        """
        if not self._is_dirty:
            return QMessageBox.StandardButton.Yes

        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "The document has been modified. Save changes?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No |
            QMessageBox.StandardButton.Cancel
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self._document.save_file():
                self._clear_dirty()
                return QMessageBox.StandardButton.Yes
            return QMessageBox.StandardButton.Cancel

        elif reply == QMessageBox.StandardButton.No:
            self._clear_dirty()
            return QMessageBox.StandardButton.No

        return QMessageBox.StandardButton.Cancel

    def closeEvent(self, event):
        """Handle window close event"""
        if self.maybe_save() == QMessageBox.StandardButton.Cancel:
            event.ignore()
        else:
            event.accept()

    def setPlainText(self, text):
        """Override to clear dirty flag"""
        self._document.setAnnotatedText(text)
        self._clear_dirty()

    def toPlainText(self):
        return self._document.toAnnotatedText()

    def keyPressEvent(self, event):
        # Handle boundary deletions
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            cursor = self.textCursor()
            if self._document.handle_boundary_editing(
                cursor,
                event.key() == Qt.Key.Key_Backspace
            ):
                self.setTextCursor(cursor)
                return

        # Handle text insertion
        if event.text():
            cursor = self.textCursor()
            start_pos = cursor.position()
            super().keyPressEvent(event)
            self._document.validate_inserted_text(start_pos, event.text())
            return

        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        """Handle paste operations with glyph protection"""
        cursor = self.textCursor()
        start_pos = cursor.position()
        super().insertFromMimeData(source)
        if source.text():
            self._document.validate_inserted_text(start_pos, source.text())

    def deleteSelectedText(self):
        """Handle selection deletion with glyph protection"""
        cursor = self.textCursor()
        if cursor.hasSelection():
            # Check if selection contains glyphs
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            block = self._document.findBlock(start)

            while block.isValid() and block.position() <= end:
                iterator = block.begin()
                while not iterator.atEnd():
                    fragment = iterator.fragment()
                    if (fragment.position() < end and
                            fragment.position() + fragment.length() > start and
                            fragment.charFormat().property(QTextFormat.Property.UserProperty + 2)):
                        # Skip glyphs in selection
                        if fragment.position() < start:
                            cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
                            cursor.setPosition(fragment.position() + fragment.length(),
                                               QTextCursor.MoveMode.KeepAnchor)
                        if fragment.position() + fragment.length() > end:
                            cursor.setPosition(end, QTextCursor.MoveMode.MoveAnchor)
                            cursor.setPosition(fragment.position(),
                                               QTextCursor.MoveMode.KeepAnchor)
                        iterator += 1
                        continue
                    iterator += 1
                block = block.next()

        super().deleteSelectedText()

    def _validate_insertion(self, insert_pos, insert_length):
        """Fix text inserted into glyph fragments"""
        cursor = QTextCursor(self._document)
        cursor.setPosition(insert_pos)

        for i in range(insert_length):
            pos = insert_pos + i
            cursor.setPosition(pos)
            fragment = self._document._get_fragment_at_position(pos)

            if fragment and fragment.charFormat().property(QTextFormat.Property.UserProperty + 2):
                # Move this character after glyph with proper format
                char_cursor = QTextCursor(self._document)
                char_cursor.setPosition(pos)
                char_cursor.movePosition(QTextCursor.MoveOperation.Right,
                                         QTextCursor.MoveMode.KeepAnchor, 1)
                text = char_cursor.selectedText()

                char_cursor.beginEditBlock()
                char_cursor.removeSelectedText()

                # Insert after glyph with context-aware format
                char_cursor.setPosition(fragment.position() + fragment.length())
                fmt = self._document.get_format_for_insertion(char_cursor.position())
                char_cursor.insertText(text, fmt)
                char_cursor.endEditBlock()

    def _get_format_at_position(self, pos):
        """Get character format at given position"""
        cursor = QTextCursor(self._document)
        cursor.setPosition(pos)
        if pos < self._document.characterCount() - 1:
            cursor.movePosition(QTextCursor.MoveOperation.Right,
                                QTextCursor.MoveMode.KeepAnchor, 1)
            return cursor.charFormat()
        return QTextCharFormat()  # Default format at end

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

    def _wrap_selection(self, construct_name):
        """Wrap selection with construct formatting and glyphs"""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return

        construct = Construct.by_name(construct_name)
        if not construct:
            log.error(f"Unknown construct: {construct_name}")
            return

        # Validate selection nesting
        start_constructs = self._get_constructs_at_position(cursor.selectionStart())
        end_constructs = self._get_constructs_at_position(cursor.selectionEnd())
        if start_constructs != end_constructs:
            log.error("Cannot wrap selection across construct boundaries")
            return

        # Save positions before modifications
        sel_start = cursor.selectionStart()
        sel_end = cursor.selectionEnd()
        new_stack = start_constructs + [construct.name]

        cursor.beginEditBlock()

        # 1. Apply construct formatting to selection
        char_format = self._create_char_format(new_stack)
        cursor.mergeCharFormat(char_format)

        # 2. Insert glyphs if needed (in reverse order to avoid position shifting)
        if construct.b_glyph:
            glyph_format = self._create_char_format(new_stack)
            glyph_format.setProperty(QTextFormat.Property.UserProperty + 2, True)

            # Insert end glyph first
            cursor.setPosition(sel_end)
            cursor.insertText(construct.e_glyph, glyph_format)

            # Then insert begin glyph
            cursor.setPosition(sel_start)
            cursor.insertText(construct.b_glyph, glyph_format)

        cursor.endEditBlock()

    def _create_char_format(self, construct_stack):
        """Create QTextCharFormat for given construct stack"""
        char_format = QTextCharFormat()
        for const in construct_stack:
            if const == 'Speech':
                char_format.setForeground(Qt.GlobalColor.darkGreen)
            elif const == 'Italic':
                char_format.setFontItalic(True)
            elif const == 'Bold':
                char_format.setFontWeight(QFont.Weight.Bold)
            elif const in SPECIAL_NAMES:
                char_format.setForeground(Qt.GlobalColor.darkMagenta)
        char_format.setProperty(QTextFormat.Property.UserProperty, '+'.join(construct_stack))
        return char_format

    def _unwrap_construct(self, construct_name, pos):
        block = self.document().findBlock(pos)
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.position() <= pos < fragment.position() + fragment.length():
                fmt = fragment.charFormat()
                current_stack = (fmt.property(QTextFormat.Property.UserProperty) or '').split('+')
                # Fast path - construct_name is guaranteed to be last in stack
                if current_stack and current_stack[-1] == construct_name:
                    text = fragment.text()
                    cursor = QTextCursor(self.document())
                    cursor.beginEditBlock()
                    cursor.setPosition(fragment.position())
                    cursor.setPosition(fragment.position() + fragment.length(),
                                       QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()

                    # Only apply format if nested (parent exists)
                    if len(current_stack) > 1:
                        parent_fmt = self._create_char_format(current_stack[:-1])
                        cursor.insertText(text, parent_fmt)
                    else:
                        cursor.insertText(text)
                    cursor.endEditBlock()
                return
            iterator += 1

    def _find_construct_boundaries(self, pos, construct_name):
        """Return (start, end) positions of construct excluding markers"""
        cursor = QTextCursor(self.document())
        cursor.setPosition(pos)

        # Search backward for construct start
        start_pos = -1
        while cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter):
            if self._get_constructs_at_position(cursor.position()) == [construct_name]:
                start_pos = cursor.position()
                break

        # Search forward for construct end
        end_pos = -1
        cursor.setPosition(pos)
        while cursor.movePosition(QTextCursor.MoveOperation.NextCharacter):
            if construct_name not in self._get_constructs_at_position(cursor.position()):
                end_pos = cursor.position()
                break

        return start_pos, end_pos

    def contextMenuEvent(self, event):
        """Handle right-click with file and construct-aware context menu"""
        mouse_pos = event.pos()
        cursor = self.cursorForPosition(mouse_pos)
        char_pos = cursor.position()

        # Get current selection info
        selection = self.textCursor()
        has_selection = selection.hasSelection()
        in_selection = (has_selection and
                        selection.selectionStart() <= char_pos <= selection.selectionEnd())

        # Get constructs at position
        constructs = self._get_constructs_at_position(char_pos)

        # Create context menu
        menu = super().createStandardContextMenu()

        # Add File submenu at the top
        file_menu = menu.addMenu("File")
        file_menu.addSeparator()
        file_menu.addAction(QIcon.fromTheme("document-open"), "Open...", self._handle_open)
        file_menu.addAction(QIcon.fromTheme("document-save"), "Save", self._handle_save)
        file_menu.addAction(QIcon.fromTheme("document-save-as"), "Save As...", self._handle_save_as)
        menu.insertMenu(menu.actions()[0], file_menu)  # Insert at top

        # Add separator before our custom items
        menu.addSeparator()

        # Create Constructs submenu
        constructs_menu = menu.addMenu("Constructs")
        constructs_menu.setEnabled(False)  # Default to disabled

        # Check if we should enable the menu item
        if has_selection and in_selection:
            # Check if selection is properly nested
            start_constructs = self._get_constructs_at_position(selection.selectionStart())
            end_constructs = self._get_constructs_at_position(selection.selectionEnd())
            if start_constructs == end_constructs:
                constructs_menu.setEnabled(True)

                # Add wrapping options
                wrap_menu = constructs_menu.addMenu("Wrap selection")
                for construct in Construct.all():
                    wrap_menu.addAction(
                        QIcon.fromTheme(construct.icon),
                        construct.desc,
                        lambda c=construct.name: self._wrap_selection(c)
                    )
                constructs_menu.addSeparator()

        if constructs:  # Inside existing construct(s)
            constructs_menu.setEnabled(True)

            # Add removal option for innermost construct
            innermost = constructs[-1]
            remove_action = constructs_menu.addAction(
                QIcon.fromTheme("edit-clear"),
                f"Remove {innermost}",
                lambda: self._unwrap_construct(innermost, char_pos)
            )
            remove_action.setData(innermost)  # Store construct name for handler

            if has_selection and in_selection:
                constructs_menu.addSeparator()

        menu.exec(event.globalPos())

    def _handle_open(self):
        """Handle file open operation"""
        if self.maybe_save() == QMessageBox.StandardButton.Cancel:
            return

        filename, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Text Files (*.txt)")
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.setAnnotatedText(f.read())
                    self._current_file = filename
            except Exception as e:
                log.error(f"Error opening file: {e}")

    def _handle_save(self):
        """Handle file save operation"""
        if not hasattr(self, '_current_file'):
            self._handle_save_as()
        else:
            try:
                with open(self._current_file, 'w', encoding='utf-8') as f:
                    f.write(self.toPlainText())
            except Exception as e:
                log.error(f"Error saving file: {e}")

    def _handle_save_as(self):
        """Handle save as operation"""
        filename, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Text Files (*.txt)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.toPlainText())
                self._current_file = filename
            except Exception as e:
                log.error(f"Error saving file: {e}")


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
    editor.setAnnotatedText(test_text)
    editor.show()

    # Verify round-trip conversion
    round_trip = editor.toAnnotatedText()
    print("Original:", repr(test_text))
    print("Round-trip:", repr(round_trip))
    print("Match:", test_text == round_trip)

    sys.exit(app.exec())
