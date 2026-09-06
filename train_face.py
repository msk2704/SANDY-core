import cv2
import os
import numpy as np
import json

# 1. Create dataset folder
if not os.path.exists('dataset'):
    os.makedirs('dataset')

# 2. Manage Names Database
names_file = 'names.json'
if os.path.exists(names_file):
    with open(names_file, 'r') as f:
        names_dict = json.load(f)
else:
    names_dict = {}

# 3. Ask for User Info
face_id = input('\n enter user id (must be a number, e.g. 1): ')
face_name = input(f' enter name for ID {face_id}: ')

# Save the link between ID (1) and Name (Sandy)
names_dict[face_id] = face_name
with open(names_file, 'w') as f:
    json.dump(names_dict, f)

# 4. Initialize Camera
cam = cv2.VideoCapture(0)
face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

print("\n [INFO] Initializing Face Capture. Look at the camera...")
print(" [TIP] Move your head slowly: Left, Right, Up, Down.")

count = 0
while(True):
    ret, img = cam.read()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_detector.detectMultiScale(gray, 1.3, 5)

    for (x,y,w,h) in faces:
        cv2.rectangle(img, (x,y), (x+w,y+h), (255,0,0), 2)     
        count += 1

        # Save image with the specific User ID
        cv2.imwrite("dataset/User." + str(face_id) + '.' + str(count) + ".jpg", gray[y:y+h,x:x+w])
        
        cv2.putText(img, f"Scan: {count}%", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
        cv2.imshow('image', img)

    k = cv2.waitKey(50) & 0xff
    if k == ord('q'): break
    elif count >= 100: # Take 100 photos
         break

cam.release()
cv2.destroyAllWindows()

# --- TRAINING PHASE ---
print(f"\n [INFO] Training the brain for {face_name}...")

recognizer = cv2.face.LBPHFaceRecognizer_create()

def getImagesAndLabels(path):
    imagePaths = [os.path.join(path,f) for f in os.listdir(path)]     
    faceSamples=[]
    ids = []
    
    for imagePath in imagePaths:
        try:
            PIL_img = cv2.imread(imagePath, cv2.IMREAD_GRAYSCALE)
            img_numpy = np.array(PIL_img,'uint8')
            id = int(os.path.split(imagePath)[-1].split(".")[1])
            faces = face_detector.detectMultiScale(img_numpy)
            for (x,y,w,h) in faces:
                faceSamples.append(img_numpy[y:y+h,x:x+w])
                ids.append(id)
        except:
            pass
    return faceSamples, ids

faces, ids = getImagesAndLabels('dataset')
recognizer.train(faces, np.array(ids))

# Save the model
recognizer.write('trainer.yml') 
print(f"\n [SUCCESS] Model trained! Now run 'test_security.py'.")