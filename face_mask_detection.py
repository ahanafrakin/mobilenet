# Standard Library imports
import os, sys, threading, time, cv2, torch
# PyQt5 imports
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QObject, pyqtSignal
SIM_FOLDER = os.path.dirname(__file__)
from PyQt5.QtGui import QImage, QPixmap
# import face_recognition
import torchvision
import torchvision.transforms as transforms
import torchvision.models
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from threading import Condition

import numpy as np
import tensorflow as tf

from matplotlib import pyplot as plt
import cv2
import pathlib

def load_model(model_name):
  print('wondering if it gts here 1')
  base_url = 'http://download.tensorflow.org/models/object_detection/'
  model_file = model_name + '.tar.gz'
  model_dir = tf.keras.utils.get_file(
    fname=model_name, 
    origin=base_url + model_file,
    untar=True)
  print('wondering if it gts here 2')
  model_dir = pathlib.Path(model_dir)/"saved_model"

  model = tf.saved_model.load(str(model_dir))
  model = model.signatures['serving_default']
  print('wondering if it gts here 3')

  return model

class CNN_VGG_Soft_Classifier(nn.Module):
  def __init__(self):
      super(CNN_VGG_Soft_Classifier, self).__init__()
      self.conv1 = nn.Conv2d(512,1024,3)
      self.pool = nn.MaxPool2d(2,2)
      self.fc1 = nn.Linear(1024*2*2, 256)
      self.fc2 = nn.Linear(256, 1)

  def forward(self, x):
      x = self.pool(F.relu(self.conv1(x)))
      x = x.view(-1, 1024*2*2) #flatten feature data
      x = F.relu(self.fc1(x))
      x = self.fc2(x)
      x = x.squeeze(1)
      return x

class SignalsToGui(QObject):
    trigger = pyqtSignal(QImage)

    def __init__(self):
        super().__init__()

    def connect_to_slot(self, slot):
        self.trigger.connect(slot)

class SignalsFromGui:
    trigger = Condition()
    run_webcam = False
    username = None
    password = None
    timer = 0


class Backend():
    def __init__(self, sigs_to_gui, sigs_from_gui):
        self.sigs_to_gui = sigs_to_gui
        self.sigs_from_gui = sigs_from_gui

        self.capture = None
        self.image = None
        self.model_name = 'ssd_mobilenet_v1_coco_2017_11_17'
        self.detection_model = load_model(self.model_name)
        # self.model = torch.hub.load('pytorch/vision:v0.6.0', 'mobilenet_v2', pretrained=True)
        # self.model.eval()
        # self.model.to('cpu')
        
        self.transform = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])])

        # Process and load the haar cascade
        self.face_cascades = cv2.CascadeClassifier(r"./opencv_face_detection_algorithm/haarcascade_frontalface_default.xml")

    def startVideo(self, camera_name=0):
        """
        :param camera_name: link of camera or usb camera
        """
        try:
            self.capture = cv2.VideoCapture(int(camera_name))
        except Exception:
            sys.exit('Could not start the video')

        no_mask = 0
        # last_time_email = time.time_ns()/(10**9)


        while(self.sigs_from_gui.run_webcam == True):
            ret, image = self.capture.read()
            image = cv2.resize(image, (640, 480))

            # OpenCV uses grayscale so we convert the frame
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Detect the faces in the cascade, returns a list of rectangles where faces are supposedly found
            faces = self.face_cascades.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)

            test_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            test_img = Image.fromarray(test_img)
            transform = transforms.Compose(
                    [transforms.Resize((224,224)), transforms.ToTensor(), transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                             std=[0.229, 0.224, 0.225])])
            test_img = transform(test_img)

            # test_img = self.vgg16.features(test_img.unsqueeze(0))
            test_img = test_img.unsqueeze(0)

            preds = self.detection_model(test_img)
            print("new one")
            print(len(preds))
            # The output has unnormalized scores. To get probabilities, you can run a softmax on it.
            probabilities = torch.nn.functional.softmax(preds[0], dim=0)
            # print(probabilities)

            # Draw a rectangle around a face, (x,y) top left, w : width, h : height
            for (x, y, w, h) in faces:
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(image, 'test', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (36,255,12), 2)

            qformat = QImage.Format_Indexed8
            if len(image.shape) == 3:
                if image.shape[2] == 4:
                    qformat = QImage.Format_RGBA8888
                else:
                    qformat = QImage.Format_RGB888
            outImage = QImage(image, image.shape[1], image.shape[0], image.strides[0], qformat)
            outImage = outImage.rgbSwapped()

            self.sigs_to_gui.trigger.emit(outImage)
        self.capture.release()

def main():
    """ 
    The main function that initiates the backend server, and creates the GUI,
    which runs on the main server. Signals between GUI and the backend are created
    and passed to both. 
    """
    sigs_to_gui = SignalsToGui()
    sigs_from_gui = SignalsFromGui()

    backend = Backend(sigs_to_gui, sigs_from_gui)
    os.environ["QT_STYLE_OVERRIDE"] = ""
    app = QtWidgets.QApplication(sys.argv)
    facemask_ui = FaceMaskUI(sigs_to_gui, sigs_from_gui, backend)
    sigs_to_gui.trigger.connect(facemask_ui.updateImage)
    
    facemask_ui.show()
    sys.exit(app.exec_())

class FaceMaskUI(QtWidgets.QMainWindow):
    """ 
    This class inherits from QMainWindow and loads the file found in mask_detection.ui.
    It has functions defined in the slots in Main_Window.ui. The backend script starts
    when this class is initialized. Images are loaded when the class is initialized
    and sizing features which cannot be done through QtDesigner are completed here.

    Args:
        to_gui (SigsToGui): Signals sent from other threads to the GUI thread.
    Attributes:
        sigs_to_gui: Signals sent from other threads to the GUI thread.
    """
    def __init__(self, sigs_to_gui, sigs_from_gui, backend):
        super().__init__()

        uic.loadUi(r"./mask_detection.ui",self)
        self.backend = backend
        self.sigs_to_gui = sigs_to_gui
        self.sigs_from_gui = sigs_from_gui
        self.sigs_from_gui.run_webcam = True
        try:
            self.sigs_from_gui.timer = int(self.lineEdit_timer.text())
        except Exception:
            print("Error setting the timer, setting the default as 60")
            self.sigs_from_gui.timer = 60
        self.backend_thread = threading.Thread(target=self.backend.startVideo)
        self.backend_thread.start()
        self.backend = backend

    def closeEvent(self, event):
        """
        This function gracefully closes stops the backend when the GUI
        closes. 
        """
        self.sigs_from_gui.run_webcam = False

    def clickedStop(self, event):
        if(self.pushButton_stop.text() == "Stop"):
            self.sigs_from_gui.run_webcam = False
            self.pushButton_stop.setText("Start")
        else:
            self.sigs_from_gui.run_webcam = True
            self.backend_thread = threading.Thread(target=self.backend.startVideo)
            self.backend_thread.start()
            self.pushButton_stop.setText("Stop")

    def clickedSetEmail(self, event):
        self.sigs_from_gui.username = self.lineEdit_email.text()

    def clickedSetPassword(self, event):
        self.sigs_from_gui.password = self.lineEdit_password.text()

    def clickedSetTimer(self, event):
        try:
            self.sigs_from_gui.timer = int(self.lineEdit_timer.text())
        except Exception:
            print("Please ensure the timer is an integet number")

    def updateImage(self, outImage):
        self.cameraOutput.setPixmap(QPixmap.fromImage(outImage))
        self.cameraOutput.setScaledContents(True)


if __name__ == "__main__":
    main()