#!/usr/bin/env python3
"""Simple charting engine."""

from pathlib import Path
import datetime
import functools
import io
import logging
import re
import sys
import tempfile

from PySide2.QtCore import QUrl
from PySide2.QtWidgets import (
    QApplication, QLineEdit, QMainWindow, QVBoxLayout, QWidget)
from PySide2.QtWebEngineWidgets import QWebEnginePage, QWebEngineView

import ameritrade


this_dir = Path(__file__).resolve().parent
template_filename = this_dir / 'chart.html'


def get_pricing_data(td: ameritrade.AmeritradeAPI, symbol: str):
    """Fetch and format the pricing data."""
    hist = td.GetPriceHistory(symbol=symbol,
                              frequency=1, frequencyType='daily',
                              period=2, periodType='year')
    if not isinstance(hist, dict) or hist['empty']:
        return
    buf = io.StringIO()
    pr = functools.partial(print, file=buf)
    pr("var data = [")
    for candle in hist['candles']:
        time = datetime.datetime.fromtimestamp(candle['datetime']/1000)
        year = time.year
        month = time.month
        day = time.day
        open = candle['open']
        close = candle['close']
        high = candle['high']
        low = candle['low']
        pr(f"{{ time: {{year: {year}, month: {month}, day: {day} }}, "
           f"open: {open}, high: {high}, low: {low}, close: {close} }},")
    pr("];")
    return buf.getvalue()


class MainWindow(QMainWindow):

    def __init__(self, td: ameritrade.AmeritradeAPI):
        super(MainWindow, self).__init__()
        self.td = td
        self.setWindowTitle('Charting widget')

        # A web view for the chart.
        # TODO(blais): Replace this by a custom view, not web.
        self.webEngineView = QWebEngineView()

        # A text input for selection an expression to render.
        self.instrumentEdit = QLineEdit()
        self.instrumentEdit.returnPressed.connect(self.update_query)

        # Layout for main portion of the screen.
        layout = QVBoxLayout()
        layout.addWidget(self.webEngineView)
        layout.addWidget(self.instrumentEdit)
        widget = QWidget(self)
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def update_query(self):
        query = self.instrumentEdit.text()

        # Handle the case of an empty input.
        if not query:
            self.webEngineView.setHtml('')
            return


        # Open the template and make all src references absolute to this
        # directory.
        with open(template_filename) as template_file:
            template = template_file.read()
        template = re.sub('src="', f'src="file://{this_dir}/', template)

        # Fetch the data.
        data = get_pricing_data(self.td, query)
        if data is None:
            logging.error(f'Failed to retrieve data for "{query}"')
            return

        template = template.replace("DATA", data)

        # Note that the setHtml() method or setContent() do not work as
        # expected; loading jQuery or other libraries from within will fail,
        # even with the baseUrl provided. I'm resorting to a temporary file for
        # this reason.
        self.htmlfile = tempfile.NamedTemporaryFile(suffix='.html', mode='w')
        self.htmlfile.write(template)
        url = "file://{}".format(self.htmlfile.name)
        self.webEngineView.load(url)


def main():
    td = ameritrade.open(ameritrade.config_from_dir())
    app = QApplication(sys.argv)
    main_window = MainWindow(td)
    geometry = app.desktop().availableGeometry(main_window)
    main_window.resize(geometry.width() * 2 / 3, geometry.height() * 2 / 3)
    main_window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
