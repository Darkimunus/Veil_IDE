import json
import sys
from pathlib import Path
from PySide6.QtGui import QFontDatabase, QCloseEvent, QIcon  # pyright: ignore[reportMissingImports]
from PySide6.QtCore import Qt  # pyright: ignore[reportMissingImports]
from PySide6.QtWidgets import (  # pyright: ignore[reportMissingImports]
    QApplication, QMainWindow, QWidget, QPlainTextEdit,
    QTextEdit, QPushButton, QLabel, QFileDialog,
    QVBoxLayout, QHBoxLayout, QMessageBox, QInputDialog,
    QDialog, QDialogButtonBox, QStyle
)
import veil_lang
import veil_paths
import subprocess

SAMPLE = """-
"""


class VeilIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Veil IDE 0.3")
        self.resize(950, 900)
        self.path = None
        self._lock = False
        # Last known "saved" state of both panes (what discard would lose)
        self.saved_blank = ""
        self.saved_readable = ""

        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)

        self.readable = QPlainTextEdit()
        self.readable.setFont(mono)
        self.readable.setPlainText(SAMPLE)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Blank Veil source lives here (or open a .veil file)..."
        )

        self.glyphs = QPlainTextEdit()
        self.glyphs.setFont(mono)
        self.glyphs.setReadOnly(True)
        self.glyphs.setPlaceholderText("Glyph view (·░▒█) — void, but visible")

        self.status = QLabel()

        self.output = QTextEdit()
        self.output.setReadOnly(True)

        new_btn = QPushButton("New")
        open_btn = QPushButton("Open")
        save_btn = QPushButton("Save")
        run_btn = QPushButton("Run ▶")
        enc_btn = QPushButton("Encode ▼ (readable → blank)")
        dec_btn = QPushButton("Decode ▲ (blank → readable)")
        hide_btn = QPushButton("Hide in…")
        diff_btn = QPushButton("Blank diff…")
        shot_btn = QPushButton("Screenshot")
        qr_btn = QPushButton("QR of blanks")
        md_btn = QPushButton("Import .md → (md …)")

        new_btn.clicked.connect(self.new_file)
        open_btn.clicked.connect(self.open_file)
        save_btn.clicked.connect(self.save_file)
        run_btn.clicked.connect(self.run_demo)
        enc_btn.clicked.connect(self.to_blank)
        dec_btn.clicked.connect(self.to_readable)
        hide_btn.clicked.connect(self.hide_in)
        diff_btn.clicked.connect(self.blank_diff_dialog)
        shot_btn.clicked.connect(self.share_screenshot)
        qr_btn.clicked.connect(self.share_qr)
        md_btn.clicked.connect(self.import_markdown)

        bar = QHBoxLayout()
        for button in (new_btn, open_btn, save_btn, run_btn):
            bar.addWidget(button)

        bar2 = QHBoxLayout()
        for button in (enc_btn, dec_btn, md_btn, hide_btn, diff_btn, shot_btn, qr_btn):
            bar2.addWidget(button)

        layout = QVBoxLayout()
        layout.addLayout(bar)
        layout.addWidget(QLabel("Readable view (a lens for humans - not stored in the file)"))
        layout.addWidget(self.readable, 3)
        layout.addLayout(bar2)
        layout.addWidget(QLabel("Veil source (blank characters - this is the program)"))
        layout.addWidget(self.editor, 2)
        layout.addWidget(QLabel("Glyph view (still not source — just a lens)"))
        layout.addWidget(self.glyphs, 1)
        layout.addWidget(self.status)
        layout.addWidget(QLabel("Output / diagnostics"))
        layout.addWidget(self.output, 2)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.editor.textChanged.connect(self.on_editor_changed)
        self.readable.textChanged.connect(self.on_readable_changed)
        self.output.setPlainText("Ready. Press Encode, then Run ▶.")
        self.refresh_status()
        self.refresh_glyphs()
        # Startup SAMPLE counts as the clean baseline (no file yet)
        self.mark_clean()

    
    def launch_terminal(self):
        if self.path is None or not self.path.exists() or self.is_dirty():
            if not self.save_file():
                return

        if sys.platform == "win32":
            if getattr(sys, "frozen", False):
                runner = Path(sys.executable).parent / "VeilTerminal.exe"

                if not runner.exists():
                    QMessageBox.critical(
                        self,
                        "Terminal error",
                        f"Terminal runner not found:\n{runner}"
                    )
                    return

                subprocess.Popen(
                    [str(runner), str(self.path)],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                runner = Path(__file__).parent / "terminal_runner.py"

                subprocess.Popen(
                    [sys.executable, str(runner), str(self.path)],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
        else:
            QMessageBox.information(
                self,
                "Terminal",
                "The external terminal launcher needs a platform-specific "
                "terminal command on this operating system."
            )
    
    # ---- sync between the panes
    def refresh_status(self):
        text = self.editor.toPlainText()
        info = veil_lang.analyze_emptiness(text)
        d = info["by_digit"]
        msg = (
            f"{info['chars']} chars  ·  {info['blanks']} blanks "
            f"(A{d['A']} B{d['B']} C{d['C']} D{d['D']})"
        )
        if info["appears_blank"] and info["blanks"]:
            msg += "  ·  LOOKS EMPTY"
        elif info["decoy"]:
            msg += f"  ·  {info['decoy']} decoy"
        if self.is_dirty():
            msg += "  ·  unsaved"
        self.status.setText(msg)
        self.status.setToolTip("\n".join(info["warnings"]) or "No warnings.")

    def on_editor_changed(self):
        self.refresh_status()
        self._update_title()
        if not self._lock:
            self.to_readable(quiet=True)
            self.refresh_glyphs()

    def on_readable_changed(self):
        if not self._lock:
            self.refresh_status()
            self._update_title()

    def refresh_glyphs(self):
        self.glyphs.setPlainText(veil_lang.to_glyphs(self.editor.toPlainText()))

    def to_blank(self):
        try:
            blank = veil_lang.compile_text(self.readable.toPlainText())
        except veil_lang.VeilError as exc:
            self.output.setPlainText(f"Encode error: {exc}")
            return
        self._lock = True
        self.editor.setPlainText(blank)
        self._lock = False
        self.refresh_status()
        self.refresh_glyphs()
        self._update_title()
        info = veil_lang.analyze_emptiness(blank)
        extra = "\n".join(info["warnings"])
        self.output.setPlainText("Encoded.\n" + extra if extra else "Encoded.")

    def to_readable(self, quiet=False):
        try:
            text = veil_lang.disassemble(self.editor.toPlainText())
        except veil_lang.VeilError as exc:
            if not quiet:
                self.output.setPlainText(f"Decode error: {exc}")
            return
        # Programmatic update — don't treat as a separate "user edit" beyond blank
        self._lock = True
        self.readable.setPlainText(text)
        self._lock = False
        # If blank still matches the saved file, keep readable baseline in sync
        # so auto-decode after Open doesn't look dirty.
        if self.editor.toPlainText() == self.saved_blank:
            self.saved_readable = text
        self._update_title()

    # ---- dirty / save prompts (compare BOTH panes to last save/open)
    def is_dirty(self):
        return (
            self.editor.toPlainText() != self.saved_blank
            or self.readable.toPlainText() != self.saved_readable
        )

    def _update_title(self):
        name = self.path.name if self.path else "untitled.veil"
        mark = " *" if self.is_dirty() else ""
        self.setWindowTitle(f"Veil IDE 0.3 — {name}{mark}")

    def mark_clean(self):
        """Remember current panes as the saved baseline."""
        self.saved_blank = self.editor.toPlainText()
        self.saved_readable = self.readable.toPlainText()
        self._update_title()
        self.refresh_status()

    def confirm_discard_or_save(self, action="close"):
        if not self.is_dirty():
            return True

        dlg = QDialog(self)
        dlg.setWindowTitle("Unsaved changes")
        layout = QVBoxLayout(dlg)

        title = QLabel(
            f"\n This Veil source has unsaved changes.\n"
            f"Do you want to save before you {action}? \n"
            f""
        )
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title.setWordWrap(True)

        sub = QLabel(
            "𝐼 𝓂𝒶𝓎 𝒷𝑒 𝒶 𝓂𝑜𝓃𝓈𝓉𝑒𝓇, 𝒷𝓊𝓉 𝐼'𝓂 𝓃𝑜𝓉 𝒶 𝓋𝒾𝓁𝓁𝒶𝒾𝓃 — "
            "𝓎𝑜𝓊𝓇 𝒷𝓁𝒶𝓃𝓀𝓈 𝒹𝑒𝓈𝑒𝓇𝓋𝑒 𝒶 𝒸𝒽𝒶𝓃𝒸𝑒. \n"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Discard
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setDefault(True)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        icon.setPixmap(
            dlg.style().standardIcon(
                QStyle.StandardPixmap.SP_MessageBoxWarning
            ).pixmap(32, 32)
        )
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addWidget(buttons)

        result = {"choice": None}

        def on_clicked(button):
            result["choice"] = buttons.standardButton(button)
            dlg.accept()

        buttons.clicked.connect(on_clicked)
        dlg.exec()

        choice = result["choice"]
        if choice == QDialogButtonBox.StandardButton.Save:
            return self.save_file()
        if choice == QDialogButtonBox.StandardButton.Discard:
            return True
        return False

    def closeEvent(self, event: QCloseEvent):
        if self.confirm_discard_or_save("close"):
            event.accept()
        else:
            event.ignore()

    # ---- files
    def new_file(self):
        if not self.confirm_discard_or_save("start a new file"):
            return
        self.path = None
        self._lock = True
        self.editor.clear()
        self.readable.clear()
        self.glyphs.clear()
        self._lock = False
        self.output.clear()
        self.refresh_status()
        self.mark_clean()

    def open_file(self):
        if not self.confirm_discard_or_save("open another file"):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Veil source", "",
            "Veil files (*.veil);;All files (*.*)"
        )
        if not path:
            return
        try:
            self._lock = True
            self.editor.setPlainText(
                Path(path).read_text(encoding="utf-8")
            )
            self._lock = False
            self.path = Path(path)
            # Fill readable from blanks, then snapshot both as clean
            self.to_readable(quiet=True)
            self.refresh_glyphs()
            self.mark_clean()
        except Exception as exc:
            self._lock = False
            QMessageBox.critical(self, "Open error", str(exc))

    def save_file(self):
        # Sync readable edits into blank source before writing the file
        try:
            blank = veil_lang.compile_text(self.readable.toPlainText())
        except veil_lang.VeilError as exc:
            QMessageBox.critical(
                self, "Save error",
                f"Readable view doesn't encode cleanly:\n{exc}\n\n"
                "Fix it (or Encode manually) before saving."
            )
            return False

        self._lock = True
        self.editor.setPlainText(blank)
        self._lock = False
        self.refresh_glyphs()
        self.to_readable(quiet=True)

        if self.path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Veil source", "untitled.veil",
                "Veil files (*.veil);;All files (*.*)"
            )
            if not path:
                return False
            self.path = Path(path)

        try:
            self.path.write_text(
                self.editor.toPlainText(),
                encoding="utf-8",
                newline=""
            )
            self.mark_clean()
            self.output.setPlainText("Saved " + self.path.name)
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Save error", str(exc))
            return False

    # ---- joke tools
    def hide_in(self):
        names = list(veil_lang.CAMOUFLAGE.keys())
        name, ok = QInputDialog.getItem(
            self, "Hide in…", "Camouflage template:", names, 0, False
        )
        if not ok:
            return
        try:
            wrapped = veil_lang.hide_in(self.editor.toPlainText(), name)
        except veil_lang.VeilError as exc:
            self.output.setPlainText(f"Hide error: {exc}")
            return
        self._lock = True
        self.editor.setPlainText(wrapped)
        self._lock = False
        self.refresh_status()
        self.refresh_glyphs()
        self.to_readable(quiet=True)
        self._update_title()
        self.output.setPlainText(f"Hidden inside template {name!r}. Save when ready.")

    def blank_diff_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Diff against file", "",
            "Veil files (*.veil);;All files (*.*)"
        )
        if not path:
            return
        try:
            other = Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Diff", str(exc))
            return
        self.output.setPlainText(
            veil_lang.blank_diff(self.editor.toPlainText(), other)
        )

    def share_screenshot(self):
        pix = self.grab()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save screenshot", "veil.png", "PNG (*.png)"
        )
        if not path:
            return
        if not pix.save(path):
            QMessageBox.critical(self, "Screenshot", "Failed to save.")
            return
        self.output.setPlainText(f"Screenshot saved: {path}")

    def share_qr(self):
        blank = veil_lang.blank_only(self.editor.toPlainText())
        if not blank:
            self.output.setPlainText("QR: nothing to encode (no blanks).")
            return
        try:
            import qrcode  # pyright: ignore[reportMissingModuleSource]
        except ImportError:
            QMessageBox.information(
                self, "QR",
                'Install qrcode first:\n  pip install "qrcode[pil]"'
            )
            return
        try:
            img = qrcode.make(blank)
        except Exception as exc:
            self.output.setPlainText(f"QR failed (payload too long?): {exc}")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save QR", "veil-qr.png", "PNG (*.png)"
        )
        if not path:
            return
        img.save(path)
        self.output.setPlainText(
            f"QR saved ({len(blank)} blank chars). "
            "Scanning yields invisible text — perfect."
        )

    def import_markdown(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Markdown", "",
            "Markdown (*.md *.markdown *.txt);;All files (*.*)"
        )
        if not path:
            return
        try:
            doc = Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, "Import error", str(exc))
            return

        # Same escaping Veil's tokenizer expects (JSON string literal)
        form = "(md " + json.dumps(doc, ensure_ascii=False) + ")"
        self.readable.setPlainText(form)
        self.output.setPlainText(
            f"Imported {Path(path).name} as (md …). "
            "Press Encode ▼ then Save / Run."
        )
        # readable change marks dirty via on_readable_changed

    # ---- running
    def ask_input(self):
        text, _ = QInputDialog.getText(
            self, "Veil input", "The program asks for input:"
        )
        return text

    def run_demo(self):
        self.launch_terminal()


def main():
    # Windows: without this, the taskbar keeps using python.exe's icon
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "VeilIDE.App.0.3"
            )
        except Exception:
            pass

    veil_paths.ensure_user_config()
    app = QApplication(sys.argv)

    icon_path = (veil_paths.project_root() / "favicon.ico").resolve()
    icon = QIcon(str(icon_path))
    if icon_path.exists() and not icon.isNull():
        app.setWindowIcon(icon)
    else:
        print(f"Icon not loaded: {icon_path} exists={icon_path.exists()}")

    window = VeilIDE()
    if not icon.isNull():
        window.setWindowIcon(icon)

    if getattr(sys, "frozen", False):
        window.showMaximized()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())