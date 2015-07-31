# Copyright 2015, Brown University, Providence, RI.
#
#                         All Rights Reserved
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose other than its incorporation into a
# commercial product is hereby granted without fee, provided that the
# above copyright notice appear in all copies and that both that
# copyright notice and this permission notice appear in supporting
# documentation, and that the name of Brown University not be used in
# advertising or publicity pertaining to distribution of the software
# without specific, written prior permission.
#
# BROWN UNIVERSITY DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
# INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR ANY
# PARTICULAR PURPOSE.  IN NO EVENT SHALL BROWN UNIVERSITY BE LIABLE FOR
# ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

__author__ = 'Alex Kalinin <akalinin@brown.edu>'

# Use Qt5 in case both Qt5 and Qt4 are installed
import matplotlib
matplotlib.use("Qt5Agg")

from PyQt5 import QtWidgets, QtCore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

class MplCanvas(FigureCanvas):
    def __init__(self):
        self.figure = Figure()
        self.figure.add_subplot(111)
        super(MplCanvas, self).__init__(self.figure)

    def plot_waveform(self, data):
        ax = self.figure.add_subplot(111)
        ax.hold(False)
        ax.plot(data)

class MplWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MplWidget, self).__init__(parent)

        self.canvas = MplCanvas()
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.canvas)
        layout.addWidget(self.toolbar)

    @QtCore.pyqtSlot(list)
    def plot_waveform(self, data):
        self.canvas.plot_waveform(data)
        self.canvas.draw()
