#!/usr/bin/env python3
# Tested with PyQt6.4.0, Python 3.10.6, Ubuntu 22.04
import sys, os
import pypdfium2 as pdfium

from itertools import count
from pathlib import Path

from PIL.ImageQt import ImageQt
from PIL import Image

from PyQt6.QtGui import QPainter 
from PyQt6.QtPrintSupport import (
    QPrinter, 
    QPrintDialog
)    
from PyQt6.QtCore import (
    Qt, 
    QRect,
    QObject, 
    QThread, 
    pyqtSignal
)    
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMessageBox
)

# Step 1: Create a worker class
class printPdfWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def __init__(self, pdf=None, parent=None):
        super().__init__(parent)
        if pdf == None:
            raise AttributeError('pdf (Type:str, Path or pyFPDF-Object) needs to be passed to printWorker')
        
        if isinstance(pdf, str) or isinstance(pdf, Path) or not os.path.exists(pdf):
            self.pdf_file = Path(pdf)            
        else:
            raise TypeError('pdf not of Type str, Path or file does not exist')    
        
        self._printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self.dialog = QPrintDialog(self._printer)
                                    
    def run(self):
        """Long-running print task."""             
        if self.dialog.exec():          
            painter = QPainter(self._printer)
            rect = painter.viewport()

            pdf = pdfium.PdfDocument(self.pdf_file)
            n_pages = len(pdf)  
            printRange=[]
           
            fromPage = self._printer.fromPage()
            toPage = self._printer.toPage()  
            printRange = range(n_pages) if fromPage == 0 else range(fromPage-1, toPage)  
            
            page_indices = [i for i in printRange]  
            
            renderer = pdf.render(
                pdfium.PdfBitmap.to_pil,
                page_indices = page_indices,
                scale = 300/72,  # 300dpi resolution
            )
            
            for i, pil_image, pageNumber in zip(page_indices, renderer, count(1)):

                if pageNumber > 1:
                    self._printer.newPage()

                pilWidth, pilHeight = pil_image.size
                imageRatio = pilHeight/pilWidth
                
                viewportRatio= rect.height()/rect.width()   
                
                # Rotate image if orientation is not the same as print format orientation
                if (viewportRatio < 1 and imageRatio > 1) or (viewportRatio > 1 and imageRatio < 1): 
                    pil_image = pil_image.transpose(Image.ROTATE_90)
                    pilWidth, pilHeight = pil_image.size                  

                # Adjust drawing area to available viewport 
                if viewportRatio > imageRatio:
                    y=int(rect.width()/(pilWidth/pilHeight))                   
                    printArea=QRect(0,0,rect.width(),y)
                else:
                    x = int(pilWidth/pilHeight*rect.height())
                    printArea=QRect(0,0,x,rect.height())
                
                image = ImageQt(pil_image)    

                # Print image                   
                painter.drawImage(printArea, image)
                firstPage=False
                self.progress.emit(int(pageNumber*100/len(page_indices)))
            
            # Cleanup        
            pdf.close()
            painter.end()
           
        del self._printer
        self.finished.emit()
                
        
class Window(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clicksCount = 0
        self.setupUi()

    def setupUi(self):
        self.setWindowTitle("Print existing PDF with PyQt")
        self.resize(300, 150)
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        # Create and connect widgets
        self.clicksLabel = QLabel("Counting: 0 clicks", self)
        self.clicksLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.stepLabel = QLabel("Print progress in %: 0")
        self.stepLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.countBtn = QPushButton("Click me!", self)
        self.countBtn.clicked.connect(self.countClicks)
        self.longRunningBtn = QPushButton("Print existing PDF", self)
        self.longRunningBtn.clicked.connect(self.runPrintTask)
        # Set the layout
        layout = QVBoxLayout()
        layout.addWidget(self.clicksLabel)
        layout.addWidget(self.countBtn)
        layout.addStretch()
        layout.addWidget(self.stepLabel)
        layout.addWidget(self.longRunningBtn)
        self.centralWidget.setLayout(layout)
    
    def getFile(self):
        response = QFileDialog.getOpenFileName(
            parent=self,
            caption='Select a file',
            directory=os.getcwd(),
            filter='PDF File (*.pdf *.PDF)' 
        )
        return response[0]
        
    def countClicks(self):
        self.clicksCount += 1
        self.clicksLabel.setText(f"Counting: {self.clicksCount} clicks")

    def reportProgress(self, n):
        self.stepLabel.setText(f"Print progress in %: {n}")

    def printFinished(self):
        self.longRunningBtn.setEnabled(True)
        self.stepLabel.setText("Print progress in %: 0")     
        msgBox = QMessageBox()
        msgBox.setText("Printing completed")
        msgBox.exec() 
    
    def runPrintTask(self):
        pdf_file=self.getFile()
        # Step 2: Create a QThread object
        self.thread = QThread()
        # Step 3: Create a worker object
        self.worker = printPdfWorker(pdf_file)
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.progress.connect(self.reportProgress)
        # Step 6: Start the thread
        self.thread.start()

        # Final resets
        self.longRunningBtn.setEnabled(False)
        self.thread.finished.connect(self.printFinished)

app = QApplication(sys.argv)
win = Window()
win.show()
sys.exit(app.exec())
