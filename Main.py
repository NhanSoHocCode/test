import cv2
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsPixmapItem
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QTimer
from frmMain import Ui_MainWindow  # Import giao diện từ PyQt Designer
import sys
import mysql.connector
import datetime
import easyocr

class MainApp(QMainWindow):
    def __init__(self):
        super(MainApp, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Khởi tạo QGraphicsScene cho graphicsView
        self.scene = QGraphicsScene(self)
        self.ui.graphicsView.setScene(self.scene)

        # Khởi tạo camera
        self.cap = cv2.VideoCapture(0)  # Mở camera mặc định

        if not self.cap.isOpened():
            print("Không thể mở camera!")
            return

        # Khởi tạo QTimer để cập nhật video
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # 30ms mỗi lần (~33 FPS)

        # Khởi tạo mô-đun nhận diện biển số xe
        self.n_plate_detector = cv2.CascadeClassifier('./assets/xml/haarcascade_russian_plate_number.xml')

        # Kết nối nút bấm
        self.ui.btnQuetPlate.clicked.connect(self.readnumberplate)
        self.ui.btnExit.clicked.connect(self.close)

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            detections = self.n_plate_detector.detectMultiScale(frame_rgb, scaleFactor=1.1, minNeighbors=3)

            for (x, y, w, h) in detections:
                cv2.rectangle(frame_rgb, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame_rgb, "Bien so xe", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                # Cắt vùng chứa biển số (nếu cần)
                plate_roi = frame[y:y + h, x:x + w]
                cv2.imwrite('./assets/images/numberplate.jpg', plate_roi)

            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            q_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)
            self.scene.clear()
            self.scene.addItem(QGraphicsPixmapItem(pixmap))

    @staticmethod
    def connectDB():
        con = mysql.connector.connect(
            host = 'localhost',
            user = 'root',
            password = '',
            database = 'data_number_plate'
        )
        return con

    # Check tên biển số đọc từ hình ảnh lưu vào thư mục "images" đã tồn tại trong database chưa 
    def checkNp(self, number_plate):
        con = self.connectDB()
        cursor = con.cursor()
        sql = "SELECT * FROM Numberplate WHERE number_plate = %s"
        cursor.execute(sql,(number_plate,))
        cursor.fetchall()
        result = cursor._rowcount
        # print("So ban ghi tim dc : " + str(result))
        con.close()
        cursor.close()
        return result

    # Check tên biển số và trạng thái của bản ghi gần nhất đọc từ hình ảnh lưu vào thư mục "images" 
    def checkNpStatus(self, number_plate):
        con = self.connectDB()
        cursor = con.cursor()
        sql = "SELECT * FROM Numberplate WHERE number_plate = %s ORDER BY date_in DESC LIMIT 1"
        cursor.execute(sql,(number_plate,))
        result = cursor.fetchone()
        # print("Ngay vao  : " + str(result[2]) + datetime.datetime.strftime(result[3],"%Y/%m/%d %H:%M:%S"))
        con.close()
        cursor.close()
        return result
    # Tạo bản ghi dành cho xe vào bãi gửi xe (Cho xe vào bãi)
    # Trường hợp 1 : Tên biển số xe đọc từ ảnh chưa tồn tại trong database 
    # Trường hợp 2 : Tên biển số xe đọc từ ảnh đã tồn tại trong database nhưng trạng thái của bản ghi gần nhất là 0 (đã từng gửi nhưng lấy ra khỏi bãi xe rồi) 
    def insertNp(self, number_plate):
        con = self.connectDB()
        cursor = con.cursor()
        sql = "INSERT INTO Numberplate(number_plate,status,date_in) VALUES(%s,%s,%s)"
        now = datetime.datetime.now()
        date_in = now.strftime("%Y/%m/%d %H:%M:%S")
        cursor.execute(sql,(number_plate,'0',date_in))
        con.commit()
        cursor.close()
        con.close()
        string1 = "VAO BAI GUI XE"
        stringday1 = datetime.datetime.strftime(datetime.datetime.now(),"%Y/%m/%d %H:%M:%S")
        self.ui.textEdit_2.setText(string1)
        self.ui.textEdit_3.setText(stringday1)
        image_path = "./assets/images/numberplate.jpg"
        pixmap = QPixmap(image_path)
        self.ui.label.setPixmap(pixmap)

    # Cập nhật bản ghi (Cho xe ra khỏi bãi)
    def updateNp(self, Id):
        con = self.connectDB()
        cursor = con.cursor()
        sql = "UPDATE Numberplate SET status = 0, date_out = %s WHERE Id = %s"
        now = datetime.datetime.now()
        date_out = now.strftime("%Y/%m/%d %H:%M:%S")
        cursor.execute(sql,(date_out,Id))
        con.commit()
        cursor.close()
        con.close()
        string2 ="RA KHOI BAI GUI XE"
        stringday2 = datetime.datetime.strftime(datetime.datetime.now(),"%Y/%m/%d %H:%M:%S")
        self.ui.textEdit_2.setText(string2)
        self.ui.textEdit_3.setText(stringday2)
        image_path = "./assets/images/numberplate.jpg"
        pixmap = QPixmap(image_path)
        self.ui.label.setPixmap(pixmap)
    def readnumberplate(self):
        reader = easyocr.Reader(['en'], gpu=False)
        image_path = './assets/images/numberplate.jpg'
        try:
            image = cv2.imread(image_path)
            if image is None:
                print("Error: Không tìm thấy file ảnh biển số!")
                return
            results = reader.readtext(image, detail=0)
            number_plate = ''.join(results).replace(" ", "")

            self.ui.textEdit.setText(number_plate)  # Hiển thị biển số trong TextEdit

            if number_plate:
                check = self.checkNp(number_plate)
                if check == 0:
                    self.insertNp(number_plate)
                else:
                    check2 = self.checkNpStatus(number_plate)
                    if check2[2] == 1:  # Trạng thái 1 -> xe đang ở bãi
                        self.updateNp(check2[0])
                    else:  # Trạng thái 0 -> xe đã ra bãi, tạo bản ghi mới
                        self.insertNp(number_plate)
            else:
                print("Biển số không xác định!")
        except Exception as e:
            print(f"Error khi xử lý biển số: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_app = MainApp()
    main_app.show()
    sys.exit(app.exec())
