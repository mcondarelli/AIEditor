import sys
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (QMainWindow, QHBoxLayout, QComboBox, QVBoxLayout,
                             QPushButton, QTextEdit, QWidget, QLineEdit, QGroupBox,
                             QApplication)
from io_utils import export_to_legacy_json
from ai_utils import ai_ask_commentary
from logging_config import LoggingConfig
from schema import init_db

COMPANY = 'MCondarelli'
PROGRAM = 'AIEditor'
log = LoggingConfig.get_logger('PyQt', _default=4)


class AIEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_conn = init_db()
        self.scene_combos = []
        self.current_hierarchy = []
        self.current_scene_id = None
        self.current_chapter_scenes = {}

        self.setup_ui()
        self.load_structure()
        self.current_scene_id = self.load_last_scene()
        self.load_scene_by_id(self.current_scene_id)

    def setup_ui(self):
        self.setWindowTitle("Novel Editor")
        self.setGeometry(100, 100, 800, 600)

        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Navigation comboboxes
        crumb_layout = QHBoxLayout()
        layout.addLayout(crumb_layout)

        self.book_combo = QComboBox()
        self.part_combo = QComboBox()
        self.chapter_combo = QComboBox()
        self.scene_combo = QComboBox()

        self.scene_combos = [self.book_combo, self.part_combo,
                             self.chapter_combo, self.scene_combo]

        for combo in self.scene_combos:
            crumb_layout.addWidget(combo)

        # Main content area
        body_layout = QHBoxLayout()
        layout.addLayout(body_layout)

        # Left panel (editor)
        left_layout = QVBoxLayout()
        body_layout.addLayout(left_layout)

        # Navigation buttons
        button_layout = QHBoxLayout()
        left_layout.addLayout(button_layout)

        self.prev_button = QPushButton("Prev")
        self.prev_button.clicked.connect(lambda: self.navigate_to_adjacent_scene("prev"))
        button_layout.addWidget(self.prev_button)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(lambda: self.navigate_to_adjacent_scene("next"))
        button_layout.addWidget(self.next_button)

        # Text editor
        self.editor = QTextEdit()
        left_layout.addWidget(self.editor)

        # Right panel (tools)
        right_layout = QVBoxLayout()
        body_layout.addLayout(right_layout)

        # Buttons
        self.check_button = QPushButton("Check")
        self.check_button.clicked.connect(self.on_check)
        right_layout.addWidget(self.check_button)

        # Status Combo
        self.status_combo = QComboBox()
        self.status_combo.addItems(["unreviewed", "ai_processed", "human_approved"])
        right_layout.addWidget(self.status_combo)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search in scene")
        right_layout.addWidget(self.search_field)

        # Commentary section
        self.commentary_box = QGroupBox("Commentary")
        commentary_layout = QVBoxLayout()
        self.commentary_editor = QTextEdit()
        commentary_layout.addWidget(self.commentary_editor)
        self.commentary_box.setLayout(commentary_layout)
        right_layout.addWidget(self.commentary_box)

        # Connect signals after UI setup
        self.book_combo.currentTextChanged.connect(self.update_parts)
        self.part_combo.currentTextChanged.connect(self.update_chapters)
        self.chapter_combo.currentTextChanged.connect(self.update_scenes)
        self.scene_combo.currentTextChanged.connect(self.on_scene_selected)

    def load_structure(self):
        """Initialize the navigation hierarchy."""
        cursor = self.db_conn.cursor()

        # Load books
        cursor.execute("SELECT id, title FROM books ORDER BY id")
        self.books = {title: book_id for book_id, title in cursor.fetchall()}
        self.book_combo.addItems(self.books.keys())

        # Trigger initial updates
        if self.book_combo.count() > 0:
            self.update_parts(self.book_combo.currentText())

    def update_parts(self, book_title):
        """Update parts combobox based on selected book."""
        if not book_title:
            return

        self.part_combo.blockSignals(True)
        self.part_combo.clear()

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT title FROM parts 
            WHERE book_id = ? 
            ORDER BY order_idx
        """, (self.books[book_title],))

        self.part_combo.addItems([title for (title,) in cursor.fetchall()])
        self.part_combo.blockSignals(False)

        # if self.part_combo.count() > 0:
        #     self.update_chapters(self.part_combo.currentText())

    def update_chapters(self, part_title):
        """Update chapters combobox based on selected part."""
        if not part_title:
            return

        self.chapter_combo.blockSignals(True)
        self.chapter_combo.clear()

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT c.title 
            FROM chapters c
            JOIN parts p ON c.part_id = p.id
            WHERE p.title = ?
            ORDER BY c.order_idx
        """, (part_title,))

        self.chapter_combo.addItems([title for (title,) in cursor.fetchall()])
        self.chapter_combo.blockSignals(False)

        # if self.chapter_combo.count() > 0:
        #     self.update_scenes(self.chapter_combo.currentText())

    def update_scenes(self, chapter_title):
        """Update scenes combobox based on selected chapter."""
        if not chapter_title:
            return

        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()

        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT s.id, s.title 
            FROM scenes s
            JOIN chapters c ON s.chapter_id = c.id
            WHERE c.title = ?
            ORDER BY s.order_idx
        """, (chapter_title,))

        scenes = cursor.fetchall()
        self.scene_combo.addItems([title for (id, title) in scenes])
        self.current_chapter_scenes = {title: id for (id, title) in scenes}
        self.scene_combo.blockSignals(False)

    def on_scene_selected(self, scene_title):
        """Handle scene selection change."""
        if not scene_title or not hasattr(self, 'current_chapter_scenes'):
            return

        scene_id = self.current_chapter_scenes.get(scene_title)
        if scene_id:
            self.load_scene_by_id(scene_id)

    def load_scene_by_id(self, scene_id):
        """Load scene content and update UI."""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT b.title, p.title, c.title, s.title, s.content, s.revision_status
            FROM scenes s
            JOIN chapters c ON s.chapter_id = c.id
            JOIN parts p ON c.part_id = p.id
            JOIN books b ON p.book_id = b.id
            WHERE s.id = ?
        """, (scene_id,))

        result = cursor.fetchone()
        if not result:
            return

        book, part, chapter, scene, content, status = result

        # Update comboboxes without triggering events
        for combo, text, updater in zip(self.scene_combos,
                                        [book, part, chapter, scene],
                                        [self.update_parts, self.update_chapters, self.update_scenes, None]):
            combo.blockSignals(True)
            combo.setCurrentText(text)
            if updater is not None:
                updater(text)
            combo.blockSignals(False)

        # Update editor and status
        self.editor.setPlainText(content)
        self.status_combo.setCurrentText(status)
        self.current_scene_id = scene_id
        self.current_hierarchy = (book, part, chapter, scene)
        self.update_nav_buttons()

    # def update_scene(self):
    #     """Refresh current scene display."""
    #     if not self.current_scene_id:
    #         return
    #     self.load_scene_by_id(self.current_scene_id)
    #
    #     # cursor = self.db_conn.cursor()
    #     # cursor.execute("""
    #     #     SELECT content, revision_status FROM scenes WHERE id = ?
    #     # """, (self.current_scene_id,))
    #     #
    #     # content, status = cursor.fetchone()
    #     # self.editor.setPlainText(content)
    #     # self.status_combo.setCurrentText(status)

    def navigate_to_adjacent_scene(self, direction):
        """Move to previous/next scene in sequence."""
        cursor = self.db_conn.cursor()

        cursor.execute("""
            SELECT b.id, p.order_idx, c.order_idx, s.order_idx
            FROM scenes s
            JOIN chapters c ON s.chapter_id = c.id
            JOIN parts p ON c.part_id = p.id
            JOIN books b ON p.book_id = b.id
            WHERE s.id = ?
        """, (self.current_scene_id,))

        current_pos = cursor.fetchone()
        if not current_pos:
            return

        book_id, part_order, chapter_order, scene_order = current_pos

        if direction == "prev":
            query = """
                SELECT s.id FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                JOIN parts p ON c.part_id = p.id
                JOIN books b ON p.book_id = b.id
                WHERE (b.id, p.order_idx, c.order_idx, s.order_idx) < (?, ?, ?, ?)
                ORDER BY b.id DESC, p.order_idx DESC, c.order_idx DESC, s.order_idx DESC
                LIMIT 1
            """
        else:
            query = """
                SELECT s.id FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                JOIN parts p ON c.part_id = p.id
                JOIN books b ON p.book_id = b.id
                WHERE (b.id, p.order_idx, c.order_idx, s.order_idx) > (?, ?, ?, ?)
                ORDER BY b.id, p.order_idx, c.order_idx, s.order_idx
                LIMIT 1
            """

        cursor.execute(query, current_pos)
        result = cursor.fetchone()
        if result:
            self.load_scene_by_id(result[0])

    def update_nav_buttons(self):
        """Enable/disable navigation buttons based on position."""
        if not self.current_scene_id:
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return

        cursor = self.db_conn.cursor()

        # Check if previous exists
        cursor.execute("""
            SELECT 1 FROM (
                SELECT s.id, b.id as book_id, p.order_idx as part_order, 
                       c.order_idx as chapter_order, s.order_idx as scene_order
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                JOIN parts p ON c.part_id = p.id
                JOIN books b ON p.book_id = b.id
            ) current
            WHERE EXISTS (
                SELECT 1 FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                JOIN parts p ON c.part_id = p.id
                JOIN books b ON p.book_id = b.id
                WHERE (b.id, p.order_idx, c.order_idx, s.order_idx) < 
                      (current.book_id, current.part_order, current.chapter_order, current.scene_order)
            ) AND current.id = ?
        """, (self.current_scene_id,))
        self.prev_button.setEnabled(bool(cursor.fetchone()))

        # Check if previous exists
        cursor.execute("""
            SELECT 1 FROM (
                SELECT s.id, b.id as book_id, p.order_idx as part_order, 
                       c.order_idx as chapter_order, s.order_idx as scene_order
                FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                JOIN parts p ON c.part_id = p.id
                JOIN books b ON p.book_id = b.id
            ) current
            WHERE EXISTS (
                SELECT 1 FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                JOIN parts p ON c.part_id = p.id
                JOIN books b ON p.book_id = b.id
                WHERE (b.id, p.order_idx, c.order_idx, s.order_idx) > 
                      (current.book_id, current.part_order, current.chapter_order, current.scene_order)
            ) AND current.id = ?
        """, (self.current_scene_id,))
        self.prev_button.setEnabled(bool(cursor.fetchone()))

    def load_last_scene(self):
        """Load last edited scene from settings."""
        settings = QSettings(COMPANY, PROGRAM)
        last_scene_id = settings.value('last_scene_id', type=int)

        if last_scene_id:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT 1 FROM scenes WHERE id = ?", (last_scene_id,))
            if cursor.fetchone():
                return last_scene_id

        # Fallback to first scene
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT id FROM scenes ORDER BY id LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else None

    # Function to perform a check on the scene
    def on_check(self):
        scene_text = self.editor.toPlainText()
        comment = ai_ask_commentary(scene_text)
        self.commentary_editor.setText(comment)

    def closeEvent(self, event):
        """Save state when closing."""
        settings = QSettings(COMPANY, PROGRAM)
        settings.setValue('last_scene_id', self.current_scene_id)
        event.accept()


if __name__ == "__main__":
    LoggingConfig.configure()
    app = QApplication(sys.argv)
    editor = AIEditor()
    editor.show()
    sys.exit(app.exec())
