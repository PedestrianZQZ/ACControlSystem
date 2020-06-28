# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Record.ui'
#
# Created by: PyQt5 UI code generator 5.14.2
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_dialog4(object):
    def setupUi(self, dialog):
        dialog.setObjectName("dialog")
        dialog.resize(1000, 500)
        self.verticalLayout = QtWidgets.QVBoxLayout(dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.pushButton = QtWidgets.QPushButton(dialog)
        self.pushButton.setObjectName("pushButton")
        self.verticalLayout.addWidget(self.pushButton)
        self.textBrowser = QtWidgets.QTextBrowser(dialog)
        self.textBrowser.setObjectName("textBrowser")
        self.verticalLayout.addWidget(self.textBrowser)

        self.retranslateUi(dialog)
        QtCore.QMetaObject.connectSlotsByName(dialog)

    def retranslateUi(self, dialog):
        _translate = QtCore.QCoreApplication.translate
        dialog.setWindowTitle(_translate("dialog", "详单"))
        self.pushButton.setText(_translate("dialog", "获取房间账单-详单"))

    def bill_create(self, feedback):
        self.textBrowser.insertPlainText("房间号" + "\t")
        self.textBrowser.insertPlainText(feedback[0] + "\n")

        self.textBrowser.insertPlainText("入店" + "\t\t" + "出店" + "\t\t" + "费用" + "\n")

        feedback[1] = feedback[1][0:].split('^')
        for i in range(len(feedback[1])):
            self.textBrowser.insertPlainText(feedback[1][i] + "\t")

        self.textBrowser.insertPlainText("\n")
        self.textBrowser.insertPlainText("开始时间" + "\t" + "结束时间" + "\t" + "持续时间" + "\t" + "风速" + "\t" + "费率" + "\t" + "花费" + "\n")

        feedback[2] = feedback[2][0:].split('|')
        for i in range(len(feedback[2])):
            feedback[2][i] = feedback[2][i][0:].split('^')
            for j in range(len(feedback[2][i])):
                self.textBrowser.insertPlainText(feedback[2][i][j] + "\t")
            self.textBrowser.insertPlainText("\n")
