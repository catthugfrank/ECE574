import cv2
import time
from picamera2 import Picamera2, MappedArray
import datetime
from picamera2.encoders import H264Encoder
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pyotp
import time

# Variables to store the rectangle coordinates
drawing = False
start_point = (0, 0)
end_point = (0, 0)  # Initialize end_point
rectangles = []  # List to store rectangles
window_name = 'Flash Rectangle'
mx, my = 0, 0
recording = False  # Flag to check if recording is in progress
recording_start_time = None
video_writer = None
motion_start_time = None
encoder = H264Encoder(10000000)

smtp_server = 'smtp.gmail.com'
smtp_port = 587
username = 'frankvu25@gmail.com'
password = '' #your smtp password here

sender_email = 'frankvu25@gmail.com'
receiver_email = 'eabrego@umich.edu'
#these will have to change depending on who the user is


# Mouse callback function to draw a rectangle
def draw_rectangle(event, x, y, flags, param):
    global start_point, end_point, drawing, mx, my
    if len(rectangles) > 1:
        rectangles.pop(0)
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_point = (x, y)
        end_point = (x, y)  # Initialize end_point when drawing starts

    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            end_point = (x, y)
        else:
            mx, my = x, y

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        end_point = (x, y)
        # Store the rectangle coordinates
        rectangles.append((start_point, end_point))

def is_motion_in_rectangle(motion_rect, roi_start, roi_end):
    # Unpack coordinates
    (mx1, my1), (mx2, my2) = motion_rect
    (rx1, ry1), (rx2, ry2) = roi_start, roi_end
    # Check if the motion rectangle overlaps the ROI
    return not (mx2 < rx1 or mx1 > rx2 or my2 < ry1 or my1 > ry2)

#draw rectangles on video, pre callback
def apply_rectangles(request):
  with MappedArray(request, "main") as m:
    #draw tracking rectangle then user created rectangle
    cv2.rectangle(m.array, (x, y), (x + w, y + h), (0, 0, 255), 2)    
    cv2.rectangle(m.array, roi_start, roi_end, (0, 255, 0), 2)

def send_email(subject, body):
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = subject
    message.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(sender_email, receiver_email, message.as_string())
    except Exception as e:
        print(f"Failed to send email: {e}")


def auth_setup():
    secret_key = pyotp.random_base32()
    totp = pyotp.TOTP(secret_key, interval=300)
    otp = totp.now()
    timeout = time.time() + 60*5

    send_email('Camera 2FA','Your 2FA code is ' + otp)

    timeout = 300   # [seconds]

    timeout_start = time.time()

    while time.time() < timeout_start + timeout:

        user_input = input("Enter the OTP or enter exit to leave: ")
        
        if user_input=='exit':
            break
        elif totp.verify(user_input):
            print("OTP is valid.")
            return True
        else:
            print("OTP is invalid.")
    return False



  
auth = auth_setup()

if auth:

    # Initialize and configure camera
    camera = Picamera2()
    camera.configure(camera.create_preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)}))
    camera.start_preview()
    camera.start()

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, draw_rectangle)

    while True:
        frame = camera.capture_array()
        
        # Convert to grayscale and apply Gaussian blur for motion detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # Static background frame for detecting motion (simple implementation)
        if 'background' not in locals():
            background = gray.copy().astype("float")
            continue

        # Compute the absolute difference between the background and current frame
        cv2.accumulateWeighted(gray, background, 0.5)
        frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(background))
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]

        # Dilate the thresholded image to fill in holes and find contours
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Get the current ROI if available
        if rectangles:
            roi_start, roi_end = rectangles[-1]
            cv2.rectangle(frame, roi_start, roi_end, (0, 255, 0), 2)  # Draw the ROI

            # Process each contour
            for contour in contours:
                if cv2.contourArea(contour) < 500:  # Filter small contours
                    continue
                (x, y, w, h) = cv2.boundingRect(contour)
                motion_rect = ((x, y), (x + w, y + h))
                
                # Check if motion is inside the ROI
                if is_motion_in_rectangle(motion_rect, roi_start, roi_end):
                    # Draw the motion rectangle on the frame
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cv2.putText(frame, "Motion Detected", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                        
                    # Start recording if not already recording
                    if not recording:
                        recording = True
                        recording_start_time = time.time()
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f'motion_clip_{timestamp}.h264'
                        camera.pre_callback = apply_rectangles
                        camera.start_recording(encoder, filename)

        # Stop recording after 10 seconds
        if recording and time.time() - recording_start_time > 10:
            recording = False
            recording_start_time = None
            camera.stop_recording()
            #restart camera
            send_email("Motion Detected", "Hello, Please check your camera. Motion detected")
            camera.start()

        # Display the frame with the ROI and motion detection
        cv2.imshow(window_name, frame)
        # Exit on 'q' key
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    if video_writer is not None:
        video_writer.release()
    camera.close()
    cv2.destroyAllWindows()
else:
    print('User must be authorize to view camera')

