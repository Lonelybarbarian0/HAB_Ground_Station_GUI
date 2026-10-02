import sys

from PySide6.QtWidgets import QApplication
from map_widget import MapWidget


app = QApplication(sys.argv)

window = MapWidget()
window.resize(800, 500)
window.show()

sys.exit(app.exec())