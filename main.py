from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
import sys

from myBlindPathMonitor import MyBlindPathMonitorForm


if __name__ == '__main__':
    app = QApplication(sys.argv)
    my_window = MyBlindPathMonitorForm()
    my_window.setWindowTitle("盲路监控系统")
    my_window.resize(1024, 768)
    my_window.show()
    sys.exit(app.exec_())