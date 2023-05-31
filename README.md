# Print existing PDF files with PyQT6 - Qt6
Code-snippet / Demo application that shows how to render and print existing PDF files with PyQt without blocking the event loop.

The code-snippet shows you how to:
* Create a separate worker thread for printing in order to avoid an event loop timeout (hanging application) for long running print jobs 
* Open a print dialog
* Support a print range
* Render the PDF's pages to bitmap images
* Adjust the images to fit into the available print area
* "Paint" them on a QPainter
* Report print progess back to your main application     

It does not:
* Rely on "print" command / installed PDF Reader in Windows nor "lp" command on Linux
* Describe how to adjust the print dialog to hide unsupported options
* Show how to configure a printer in Qt to print without a print dialog
* Support PageSelection, CurrentPage
* Catch cancel actions, etc.
* Generate vector output if you print to PDF (all bitmap) 
* Does not necessarily work with frozen applications (pyinstaller, cxfreeze, etc.) due to problems of "freezers" when it comes to freezing applications with multiple threads 
* No distinction is made between large and small pages - the content is enlarged or reduced until it fills the print area.

It uses code(-snippets) from:
* https://realpython.com/python-pyqt-qthread/
* https://github.com/pypdfium2-team/pypdfium2

Things to try:
* Adjust the dpi-settings to a lower quality e.g. 200/72 if your print jobs take too long  

## Using pypdfium2 and a separate thread
```
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
            raise AttributeError('pdf (Type:str, Path) needs to be passed to printWorker')
        
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
                scale = 150/72,  # 150dpi resolution
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
                    imageRatio = pilHeight/pilWidth

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
```

## Using PyMuPDF and a separate thread
```
#!/usr/bin/env python3
# Tested with PyQt6.4.0, Python 3.10.6, Ubuntu 22.04
import sys, os
import fitz

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
            raise AttributeError('pdf (Type:str or Path) needs to be passed to printWorker')
        
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

            pdf = fitz.open(self.pdf_file)
            n_pages = len(pdf)  
            printRange=[]
           
            fromPage = self._printer.fromPage()
            toPage = self._printer.toPage()  
            printRange = range(n_pages) if fromPage == 0 else range(fromPage-1, toPage)  
            
            page_indices = [i for i in printRange]  
                     
            for i, pageNumber in zip(page_indices, count(1)):

                if pageNumber > 1:
                    self._printer.newPage()
                
                pixmap = pdf[i].get_pixmap(dpi=150) 
                pil_image=Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            
                pilWidth, pilHeight = pil_image.size
                imageRatio = pilHeight/pilWidth
                
                viewportRatio= rect.height()/rect.width()   
                
                # Rotate image if orientation is not the same as print format orientation
                if (viewportRatio < 1 and imageRatio > 1) or (viewportRatio > 1 and imageRatio < 1): 
                    pil_image = pil_image.transpose(Image.ROTATE_90)
                    pilWidth, pilHeight = pil_image.size 
                    imageRatio = pilHeight/pilWidth

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
```
