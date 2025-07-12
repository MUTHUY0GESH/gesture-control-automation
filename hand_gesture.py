import cv2
import numpy as np
import mediapipe as mp
import math
import time
from collections import deque
import pyautogui

import serial
# Create your views here.
ser=serial.Serial('com4',baudrate='9600',timeout=3)

# Initialize MediaPipe
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

global fcnt
fcnt=0

def send_command(command):
    global fcnt
    fcnt+=1
    if(fcnt>30):
        fcnt=0
        print("Sending command:", command)
        ser.write(command.encode())


# Helper functions
def fingers_up(hand_landmarks):
    finger_tips = [4, 8, 12, 16, 20]
    finger_states = []
    lm = hand_landmarks.landmark
    finger_states.append(lm[4].x < lm[3].x)  # Thumb (right hand logic)
    for tip in finger_tips[1:]:
        finger_states.append(lm[tip].y < lm[tip - 2].y)
    return finger_states

def get_finger_name(index):
    return ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky'][index]

# Swipe tracking
x_history = deque(maxlen=10)
swipe_cooldown = 0

cap = cv2.VideoCapture(0)

while True:
    success, img = cap.read()
    if not success:
        break
    img = cv2.flip(img, 1)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    result = hands.process(img_rgb)
    h, w, _ = img.shape

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            lm_list = hand_landmarks.landmark
            mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            finger_states = fingers_up(hand_landmarks)
            up_fingers = [get_finger_name(i) for i, up in enumerate(finger_states) if up]
            cv2.putText(img, f"Fingers Up: {', '.join(up_fingers)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

            # Accurate swipe detection logic
            if finger_states[1] and finger_states[2] and not any(finger_states[i] for i in [0, 3, 4]):
                x1 = int(lm_list[8].x * w)
                x2 = int(lm_list[12].x * w)
                dist = abs(x1 - x2)

                if dist < 50:  # Close distance between index and middle tips
                    mid_x = (x1 + x2) // 2
                    x_history.append(mid_x)

                    if len(x_history) >= 10 and swipe_cooldown <= 0:
                        dx = x_history[-1] - x_history[0]

                        if dx > 100:
                            cv2.putText(img, "Swipe Right", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
                            swipe_cooldown = 30
                            print("Swipe Right Detected")
                            pyautogui.press('right')

                            x_history.clear()
                        elif dx < -100:
                            cv2.putText(img, "Swipe Left", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                            swipe_cooldown = 30
                            print("Swipe Left Detected")
                            pyautogui.press('left')

                            x_history.clear()
                else:
                    x_history.clear()
            
            # Volume control (Thumb & Index up only)
            elif finger_states[0] and finger_states[1] and not any(finger_states[i] for i in [2, 3, 4]):
                x1, y1 = int(lm_list[4].x * w), int(lm_list[4].y * h)
                x2, y2 = int(lm_list[8].x * w), int(lm_list[8].y * h)
                length = math.hypot(x2 - x1, y2 - y1)
                
                # Map length to 0-255 range
                speed = int(np.interp(length, [30, 200], [0, 255]))
                command = f"#{speed}\n"
                print("Fan Speed Command:", command)
                send_command(command)
                # time.sleep(0.2)  # prevent rapid firing

                # Optional UI feedback
                cv2.putText(img, f"Fan Speed: {speed}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                # vol = np.interp(length, [30, 200], [min_vol, max_vol])
                # volume_ctrl.SetMasterVolumeLevel(vol, None)

                cv2.circle(img, (x1, y1), 10, (255, 0, 0), -1)
                cv2.circle(img, (x2, y2), 10, (255, 0, 0), -1)
                cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 3)

            else:
                # Count fingers up for home automation
                num_fingers_up = sum(finger_states)
                if 1 <= num_fingers_up <= 4:
                    command = f"*{num_fingers_up}\n"
                    # print("Home Automation Command:", command)
                    send_command(command)
                    # time.sleep(0.5)  # delay to prevent spamming

                x_history.clear()

            if swipe_cooldown > 0:
                swipe_cooldown -= 1

    cv2.imshow("Gesture Control", img)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
