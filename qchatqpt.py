# -*- coding: utf-8 -*-
"""
/***************************************************************************
 qchatgpt
                                 A QGIS plugin
 A plugin integration between QGIS and openai API.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-02-12
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Marios S. Kyriakou
        email                : mariosmsk@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import time

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon, QFont, QKeySequence
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QShortcut, QFileDialog
from qgis.core import QgsTask, QgsApplication, QgsMessageLog

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .qchatqpt_dialog import qchatgptDialog
import os
import base64

API_EXIST = False
try:
    import openai

    API_EXIST = True
except:
    try:
        os.system('"' + os.path.join(sys.prefix, 'scripts', 'pip.exe') + '" install openai')
    finally:
        import openai

        API_EXIST = True


class qchatgpt:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.dlg = None
        self.response = None
        self.token = None
        self.questions = []
        self.answers = []
        self.question = None
        self.task = None
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'qchatgpt_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&QChatGPT')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('qchatgpt', message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/qchatqpt/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'QChatGPT'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&QChatGPT'),
                action)
            self.iface.removeToolBarIcon(action)

    def showMessage(self, title, msg, button, icon, fontsize=9):
        msgBox = QMessageBox()
        if icon == 'Warning':
            msgBox.setIcon(QMessageBox.Warning)
        if icon == 'Info':
            msgBox.setIcon(QMessageBox.Information)
        msgBox.setWindowTitle(title)
        msgBox.setText(msg)
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.setStyleSheet("background-color: rgb(83, 83, 83);color: rgb(255, 255, 255);")
        font = QFont()
        font.setPointSize(fontsize)
        msgBox.setFont(font)
        msgBox.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        buttonY = msgBox.button(QMessageBox.Ok)
        buttonY.setText(button)
        buttonY.setFont(font)
        msgBox.exec_()

    def send_message(self):
        if not API_EXIST:
            self.showMessage("QChatGPT", f"Please install the python package `pip`.", "OK",
                             "Warning")
            self.dlg.send_chat.setEnabled(True)
            return
        self.dlg.send_chat.setEnabled(False)

        try:
            self.question = self.dlg.question.text()
            cursor = self.dlg.chatgpt_ans.textCursor()
            self.dlg.chatgpt_ans.insertPlainText("\n\n")
            cursor.insertHtml('''<p><span style="background: white;">{} </span>'''.format(
                '............................................'))
            self.answers.append('\n............................................')
            quens = "\nHuman: " + self.question
            self.answers.append(quens)
            self.dlg.chatgpt_ans.insertPlainText(quens)
            loading = "\n\nLoading the answer...\n"
            self.dlg.chatgpt_ans.insertPlainText(loading)
            self.answers.append(loading)
            newlinesp = '\n............................................\n\n'
            self.dlg.chatgpt_ans.insertPlainText(newlinesp)
            self.answers.append(newlinesp)
            self.dlg.chatgpt_ans.repaint()
        finally:
            self.response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=self.question,
                temperature=0.9,
                max_tokens=150,
                top_p=1,
                frequency_penalty=0.0,
                presence_penalty=0.6,
            )

            last_ans = "AI: " + self.response['choices'][0]['text']
            self.answers.append(last_ans)
            cursor = self.dlg.chatgpt_ans.textCursor()
            cursor.insertHtml('''<p><span style="background: #F7F7F8;">{} </span>'''.format(last_ans))
            self.dlg.chatgpt_ans.repaint()
            self.dlg.question.setText('')
            self.dlg.chatgpt_ans.verticalScrollBar().setValue(
                self.dlg.chatgpt_ans.verticalScrollBar().maximum())
            self.dlg.send_chat.setEnabled(True)

    def export_messages(self):
        FILENAME = QFileDialog.getSaveFileName(None, 'Export ChatGPT answers', os.path.join(
            os.path.join(os.path.expanduser('~')), 'Desktop'), 'text (*.txt *.TXT)')
        FILENAME = FILENAME[0]
        if not os.path.isabs(FILENAME):
            return
        try:
            with open(FILENAME, "w") as f:
                f.writelines(self.answers)

        except IOError:
            self.iface.messageBar().pushWarning("Warning", f'Please, first close the file: "{FILENAME}"!')
            return

    def clear_ans_fun(self):
        self.questions = []
        self.answers = ['Welcome to the QChatGPT.']
        self.dlg.chatgpt_ans.clear()
        cursor = self.dlg.chatgpt_ans.textCursor()
        cursor.insertHtml('''<p><span style="background: white;">{} </span>'''.format(self.answers[0]))

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start:
            self.first_start = False
            self.dlg = qchatgptDialog()

        self.questions = []
        self.answers = ['Welcome to the QChatGPT.']
        p = base64.b64decode("c2stUnlBVnl5OWtuVHpEU3NIWHIxNkZUM0JsYmtGSjNqbTJjVGdOUEdxWFZ6VE9UMUJO").\
            decode("utf-8")
        openai.api_key = p
        self.dlg.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.WindowMinMaxButtonsHint |
                                Qt.WindowCloseButtonHint)
        # show the dialog
        self.dlg.show()

        self.dlg.question.setFocus(True)

        self.dlg.send_chat.clicked.connect(self.send_message)
        self.dlg.export_ans.clicked.connect(self.export_messages)
        self.dlg.chatgpt_ans.clear()
        self.dlg.chatgpt_ans.insertPlainText(self.answers[0])
        self.dlg.clear_ans.clicked.connect(self.clear_ans_fun)