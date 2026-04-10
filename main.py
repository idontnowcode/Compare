import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Compare")
    app.setOrganizationName("CompareApp")

    # CLI 인자 파싱: compare file1 file2 [file3]
    args = sys.argv[1:]
    cli_files = [a for a in args if not a.startswith("-")]

    window = MainWindow(cli_files=cli_files if cli_files else None)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
