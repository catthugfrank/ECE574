import cv2
from picamera2 import Picamera2

# Variables to store the rectangle coordinates
drawing = False
start_point = (0, 0)
end_point = (0, 0)  # Initialize end_point
rectangles = []  # List to store rectangles

# Mouse callback function
def draw_rectangle(event, x, y, flags, param):
    global start_point, end_point, drawing

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_point = (x, y)
        end_point = (x, y)  # Initialize end_point when drawing starts

    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            end_point = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        end_point = (x, y)
        # Store the rectangle coordinates
        rectangles.append((start_point, end_point))

# Initialize the camera
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration())
picam2.start()

# Create a VideoWriter object
fourcc = cv2.VideoWriter_fourcc(*'XVID')
out = cv2.VideoWriter('output.avi', fourcc, 20.0, (640, 480))

# Create a window and set the mouse callback
cv2.namedWindow('Frame')
cv2.setMouseCallback('Frame', draw_rectangle)

# Start capturing frames
try:
    while True:
        # Capture a frame
        frame = picam2.capture_array()

        # Draw all rectangles on the frame
        for rect in rectangles:
            cv2.rectangle(frame, rect[0], rect[1], (255, 0, 0), 2)

        # Draw the currently active rectangle (if any)
        if drawing:
            cv2.rectangle(frame, start_point, end_point, (255, 0, 0), 2)

        # Write the frame to the video file
        out.write(frame)

        # Display the frame
        cv2.imshow('Frame', frame)

        # Break the loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    # Release everything if job is finished
    picam2.stop()
    out.release()
    cv2.destroyAllWindows()
