import sqlite3
import sys
from pathlib import Path

from PyQt6.QtCore import QSettings, QThread, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (QMainWindow, QHBoxLayout, QComboBox, QVBoxLayout,
                             QPushButton, QTextEdit, QWidget, QLineEdit, QGroupBox,
                             QApplication, QProgressBar)
from PyQt6.uic import loadUi, loadUiType
from qt6_tools.entrypoints import qt_tools

from scene_edit.scene_edit import NovelEditor
from utils.io import export_to_legacy_json
from ai.core import analyze_style
from utils.logging_config import LoggingConfig
from schema import init_db

COMPANY = 'MCondarelli'
PROGRAM = 'AIEditor'
pq_log = LoggingConfig.get_logger('PyQt', _default=4)
ai_log = LoggingConfig.get_logger('_AI_', _default=4)

# Ensure src is in Python path
SRC_DIR = Path(__file__).parent.parent  # Goes from app/ to src/
if str(SRC_DIR) not in sys.path:
    print(f'Directory "{SRC_DIR}" was added to sys.path')
    sys.path.insert(0, str(SRC_DIR))
else:
    print(f'Directory "{SRC_DIR}" was already in sys.path')


# Load UI after path configuration
# Ui_MainWindow, QtBaseClass = loadUiType(str(Path(__file__).parent / "main.ui"))
# print(f'Ui_MainWindow: {Ui_MainWindow} -- QtBaseClass: {QtBaseClass}')



class AIWorkerSignals(QObject):
    progress = pyqtSignal(int, int, str)  # current, total, scene_title
    result = pyqtSignal(int, str)  # scene_id, commentary
    finished = pyqtSignal()
    error = pyqtSignal(str)


class SceneAnalyzer(QObject):
    finished = pyqtSignal(int, str)  # scene_id, commentary
    error = pyqtSignal(str)

    def __init__(self, scene_id, scene_text, mode="quick"):
        super().__init__()
        self.scene_id = scene_id
        self.scene_text = scene_text
        self.mode = mode

    def process(self):
        try:
            commentary = analyze_style(self.scene_text, self.mode)
            self.finished.emit(self.scene_id, commentary)
        except Exception as e:
            self.error.emit(str(e))


class AIWorker(QThread):
    def __init__(self, start_scene_id, force_reprocess=False, mode="thorough"):
        super().__init__()
        self.start_scene_id = start_scene_id
        self.force_reprocess = force_reprocess
        self.mode = mode
        self.db_conn = None
        self._is_running = True
        self.signals = AIWorkerSignals()

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()

    def run(self):
        scene_id = -1
        try:
            self.db_conn = init_db()
            cursor = self.db_conn.cursor()

            # Get count of already processed scenes
            cursor.execute("SELECT COUNT(*) FROM scenes WHERE revision_status = 'ai_processed'")
            base_processed = cursor.fetchone()[0]
            total_scenes = cursor.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]

            # Get all scenes in order
            cursor.execute("""
                SELECT s.id, s.title FROM scenes s
                JOIN chapters c ON s.chapter_id = c.id
                JOIN parts p ON c.part_id = p.id
                JOIN books b ON p.book_id = b.id
                ORDER BY b.id, p.order_idx, c.order_idx, s.order_idx
            """)
            all_scenes = cursor.fetchall()
            total = len(all_scenes)
            ai_log.debug(f'Total scene count: {total}')

            # Find starting point
            start_idx = next((i for i, (id, _) in enumerate(all_scenes)
                              if id == self.start_scene_id), 0)

            for i in range(start_idx, start_idx + total):
                if not self._is_running:
                    break

                scene_id, scene_title = all_scenes[i % total]
                ai_log.debug(f'Processing scene {i%total} ({scene_id}) - {scene_title}')
                self.signals.progress.emit(i % total + 1, total, scene_title)

                # Skip already processed scenes unless forced
                cursor.execute("SELECT revision_status FROM scenes WHERE id = ?", (scene_id,))
                if cursor.fetchone()[0] == 'unreviewed' or self.force_reprocess:
                    # Get scene content
                    cursor.execute("SELECT content FROM scenes WHERE id = ?", (scene_id,))
                    scene_text = cursor.fetchone()[0]

                    ai_log.info(f'Scene {i%total} ({scene_id}) - {scene_title} - needs review')
                    # Process and save
                    commentary = analyze_style(scene_text, self.mode)
                    cursor.execute("""
                        INSERT OR REPLACE INTO ai_feedback
                        (scene_id, feedback_type, feedback_text)
                        VALUES (?, 'style', ?)
                    """, (scene_id, commentary))
                    self.db_conn.commit()

                    # Update scene status
                    cursor.execute("""
                        UPDATE scenes SET revision_status = 'ai_processed'
                        WHERE id = ?
                    """, (scene_id,))
                    self.db_conn.commit()

                    # Calculate true progress including previously processed scenes
                    processed = base_processed + (i - start_idx + 1)
                    self.signals.progress.emit(processed, total_scenes, scene_title)
                    self.signals.result.emit(scene_id, commentary)
        except Exception as e:
            self.signals.error.emit(f"Scene {scene_id} failed: {str(e)}")
            if scene_id < 0:
                ai_log.error(f'AIWorker encountered error before starting loop: {str(e)}')
            else:
                ai_log.error(f'Request for scene {i%total} ({scene_id}) - {scene_title} - failed: {str(e)}')
        finally:
             if self.db_conn:
                self.db_conn.close()

        self.signals.finished.emit()


class AIEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_conn = init_db()
        self.scene_combos = []
        self.current_hierarchy = ['NONE']
        self.current_scene_id = None
        self.current_chapter_scenes = {}
        self.ai_worker = None
        self.worker = None

        # --- AUTO-GENERATED from UI file - DO NOT EDIT ---
        from typing import Optional
        from PyQt6.QtWidgets import QComboBox, QLineEdit, QMainWindow, QMenu, QMenuBar, QPushButton, QStatusBar, QTextEdit, QWidget
        from scene_edit.scene_edit import NovelEditor
        
        self.MainWindow: Optional[QMainWindow] = None
        self.analyze_all_btn: Optional[QPushButton] = None
        self.analyze_this_btn: Optional[QPushButton] = None
        self.book_combo: Optional[QComboBox] = None
        self.centralwidget: Optional[QWidget] = None
        self.chapter_combo: Optional[QComboBox] = None
        self.commentary_editor: Optional[QTextEdit] = None
        self.deepseek_btn: Optional[QPushButton] = None
        self.editor: Optional[NovelEditor] = None
        self.menu_File: Optional[QMenu] = None
        self.menubar: Optional[QMenuBar] = None
        self.next_button: Optional[QPushButton] = None
        self.part_combo: Optional[QComboBox] = None
        self.prev_button: Optional[QPushButton] = None
        self.scene_combo: Optional[QComboBox] = None
        self.search_field: Optional[QLineEdit] = None
        self.status_combo: Optional[QComboBox] = None
        self.statusbar: Optional[QStatusBar] = None
        # --- END AUTO-GENERATED ---
        loadUi(str(Path(__file__).with_suffix('.ui')), self)
        self.scene_combos = [self.book_combo, self.part_combo,
                             self.chapter_combo, self.scene_combo]

        # Populate Status bar
        self.statusBar().showMessage("Ready")
        self.progress_bar = QProgressBar()
        self.statusBar().addPermanentWidget(self.progress_bar)

        # Connect signals after UI setup
        self.prev_button.clicked.connect(lambda: self.navigate_to_adjacent_scene("prev"))
        self.next_button.clicked.connect(lambda: self.navigate_to_adjacent_scene("next"))
        self.analyze_all_btn.clicked.connect(self.toggle_ai_processing)
        self.analyze_this_btn.clicked.connect(self.analyze_current_scene)

        self.book_combo.currentTextChanged.connect(self.update_parts)
        self.part_combo.currentTextChanged.connect(self.update_chapters)
        self.chapter_combo.currentTextChanged.connect(self.update_scenes)
        self.scene_combo.currentTextChanged.connect(self.on_scene_selected)

        # Initialize menubar AFTER all UI elements exist
        self._setup_menubar()

        self.setWindowTitle(" AI Novel Editor")
        self.load_structure()
        self.current_scene_id = self.load_last_scene()
        if self.current_scene_id:
            self.current_hierarchy = ['Loading...']
            self._update_window_title()
            QTimer.singleShot(100, lambda: self.load_scene_by_id(self.current_scene_id))

        # Clean up any existing worker
        self.dispose_ai_worker()

    def _setup_menubar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        self.revert_action = QAction("&Revert", self)
        self.revert_action.triggered.connect(lambda: self.load_scene_by_id(self.current_scene_id))
        file_menu.addAction(self.revert_action)
        file_menu.addSeparator()
        file_menu.addAction("&Exit", self.close)

        self.editor.document().modificationChanged.connect(
            lambda changed: self._update_window_title(changed))

    def _save_scene_maybe(self):
        """Silent auto-save on navigation"""
        if self.editor.document().isModified():
            cursor = self.db_conn.cursor()
            cursor.execute("""
                UPDATE scenes
                SET content = ?,
                    revision_status = 'unprocessed'
                WHERE id = ?
            """, (self.editor.toAnnotatedText(), self.current_scene_id))
            self.db_conn.commit()
            # Modified flag cleared during load_scene_by_id()

    def load_structure(self):
        """Initialize the navigation hierarchy."""
        self.current_hierarchy = ['NONE']  # Reset if reloading
        try:
            cursor = self.db_conn.cursor()

            # Load books
            cursor.execute("SELECT id, title FROM books ORDER BY id")
            self.books = {title: book_id for book_id, title in cursor.fetchall()}
            self.book_combo.addItems(self.books.keys())

            # Trigger initial updates
            if self.book_combo.count() > 0:
                self.update_parts(self.book_combo.currentText())
        except Exception as e:
            pq_log.error(f"Structure loading failed: {e}")
            self.current_hierarchy = ['Error']
            self._update_window_title()

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
        self.editor.setAnnotatedText(content)
        self.editor.document().setModified(False)
        self.status_combo.setCurrentText(status)
        self.current_scene_id = scene_id
        self.current_hierarchy = (book, part, chapter, scene)
        self.update_commentary_display()  # Load saved commentary
        self.update_nav_buttons()
        self._update_window_title()

    def _update_window_title(self, modified=False):
        base_title = "AI Novel Editor"
        scene_title = self.current_hierarchy[-1]
        if scene_title == 'NONE':
            scene_title = "Untitled"
        self.setWindowTitle(f"{'*' if modified else ' '}{base_title} - {scene_title}")

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

    def toggle_ai_processing(self):
        """Start/stop batch processing."""
        if self.ai_worker and self.ai_worker.isRunning():
            self.stop_ai_processing()
        else:
            self.start_ai_processing()

    def start_ai_processing(self):
        """Start processing all scenes."""
        self.analyze_all_btn.setText("Stop Analysis")
        self.statusBar().showMessage("Starting thorough analysis...")

        self.ai_worker = AIWorker(
            start_scene_id=self.current_scene_id,
            force_reprocess=True,
            mode="thorough"  # Explicit thorough mode
        )
        self.analyze_all_btn.setText("Stop Analysis")
        self.progress_bar.setRange(0, 100)
        self.statusBar().showMessage("Starting analysis...")

        self.ai_worker = AIWorker(self.current_scene_id)
        self.ai_worker.signals.progress.connect(self.update_progress)
        self.ai_worker.signals.result.connect(self.handle_ai_result)
        self.ai_worker.signals.finished.connect(self.ai_processing_finished)
        self.ai_worker.signals.error.connect(self.handle_ai_error)
        self.ai_worker.start()

    def stop_ai_processing(self):
        """Gracefully stop processing."""
        if self.ai_worker:
            self.ai_worker.stop()
        self.analyze_all_btn.setText("Analyze All")
        self.statusBar().showMessage("Analysis stopped")

    def update_progress(self, processed, total, scene_title):
        """Update progress display with accurate percentage."""
        percent = int((processed / total) * 100)
        self.progress_bar.setValue(percent)
        self.statusBar().showMessage(
            f"Processed {processed}/{total} ({percent}%): {scene_title}")

    def handle_ai_result(self, scene_id, commentary):
        """Handle completed scene analysis."""
        if scene_id == self.current_scene_id:
            self.update_commentary_display()

    def handle_ai_error(self, error_msg):
        """Show errors without interrupting processing."""
        self.statusBar().showMessage(error_msg, 5000)  # 5 sec timeout

    def update_commentary_display(self):
        """Only show commentary for current scene."""
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT feedback_text FROM ai_feedback
            WHERE scene_id = ? AND feedback_type = 'style'
            ORDER BY timestamp DESC
            LIMIT 1
        """, (self.current_scene_id,))
        result = cursor.fetchone()
        self.commentary_editor.setText(result[0] if result else "")

    def ai_processing_finished(self):
        """Handle completion of all scene processing."""
        self.analyze_all_btn.setText("Analyze All")
        self.statusBar().showMessage("Analysis completed", 3000)

    def dispose_ai_worker(self):
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.quit()

    def analyze_current_scene(self):
        """Handle single scene analysis"""
        # Stop any running batch processing
        self.stop_ai_processing()

        if not self.current_scene_id:
            self.statusBar().showMessage("No scene selected", 3000)
            return

        # UI feedback
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.statusBar().showMessage("Quick analyzing scene...")

        # Setup worker with quick mode
        self.scene_worker = QThread()
        self.worker = SceneAnalyzer(
            scene_id=self.current_scene_id,
            scene_text=self.editor.toPlainText(),
            mode="quick"  # Explicit quick mode
        )

        # Store current scene ID to verify later
        original_scene_id = self.current_scene_id
        scene_title = self.current_hierarchy[-1] if self.current_hierarchy else "Untitled"

        # Get scene text (using existing method)
        scene_text = self.editor.toPlainText()

        # Show processing message
        self.statusBar().showMessage(f"Analyzing scene: {scene_title}...")

        # Create and configure worker thread
        self.scene_worker = QThread()
        self.worker = SceneAnalyzer(original_scene_id, scene_text)
        self.worker.moveToThread(self.scene_worker)

        # Connect signals
        self.worker.finished.connect(self.handle_scene_analysis_complete)
        self.worker.error.connect(self.handle_scene_analysis_error)
        self.scene_worker.started.connect(self.worker.process)
        self.scene_worker.start()

        # Add progress indicator
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        self.statusBar().showMessage(f"Analyzing scene (this may take several minutes)...")

        # Disable buttons during processing
        self.analyze_this_btn.setEnabled(False)
        self.analyze_all_btn.setEnabled(False)

    def handle_scene_analysis_complete(self, scene_id, commentary):
        """Handle successful scene analysis with proper DB saving"""
        try:
            # Save to database using main connection
            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ai_feedback
                (scene_id, feedback_type, feedback_text)
                VALUES (?, 'style', ?)
            """, (scene_id, commentary))
            cursor.execute("""
                UPDATE scenes SET revision_status = 'ai_processed'
                WHERE id = ?
            """, (scene_id,))
            self.db_conn.commit()

            # Update UI if still on same scene
            if scene_id == self.current_scene_id:
                self.commentary_editor.setText(commentary)
                self.statusBar().showMessage("✓ Analysis saved", 3000)
            else:
                self.statusBar().showMessage("✓ Analysis saved for scene", 3000)

        except sqlite3.Error as e:
            self.statusBar().showMessage(f"⚠️ Failed to save: {str(e)}", 5000)
            # Optionally retry or queue for later saving
        finally:
            # Restore UI state
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.analyze_this_btn.setEnabled(True)
            self.analyze_all_btn.setEnabled(True)
            if hasattr(self, 'scene_worker'):
                self.scene_worker.quit()
                self.scene_worker.wait()

    def handle_scene_analysis_error(self, error):
        """Handle analysis errors"""
        self.scene_worker.quit()
        self.scene_worker.wait()
        self.statusBar().showMessage(f"Analysis error: {error}", 5000)

    def closeEvent(self, event):
        """Save state when closing."""
        settings = QSettings(COMPANY, PROGRAM)
        settings.setValue('last_scene_id', self.current_scene_id)
        self.stop_ai_processing()
        event.accept()


if __name__ == "__main__":
    LoggingConfig.configure()
    app = QApplication(sys.argv)
    editor = AIEditor()
    editor.show()
    sys.exit(app.exec())