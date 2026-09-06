import cv2
import os
import numpy as np
import json
import time

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

# 3. Ask for User Info with Validation
while True:
    try:
        face_id_int = int(input('\n Enter user ID (MUST be a number, e.g. 1): '))
        face_id = str(face_id_int)
        break
    except ValueError:
        print("❌ Invalid input. Please enter a numerical ID.")

face_name = input(f' Enter name for ID {face_id}: ')

names_dict[face_id] = face_name
with open(names_file, 'w') as f:
    json.dump(names_dict, f)

# 4. Initialize Camera
cam = cv2.VideoCapture(0)
face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

print("\n [INFO] Initializing Face Capture. Look at the camera...")
print(" [TIP] Move your head slowly: Left, Right, Up, Down.")
time.sleep(2)

count = 0
while True:
    ret, img = cam.read()
    if not ret:
        print("❌ Camera disconnected.")
        break
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_detector.detectMultiScale(gray, 1.3, 5)

    for (x,y,w,h) in faces:
        cv2.rectangle(img, (x,y), (x+w,y+h), (255,0,0), 2)     
        count += 1

        # Save cropped face
        cv2.imwrite("dataset/User." + face_id + '.' + str(count) + ".jpg", gray[y:y+h,x:x+w])
        
        cv2.putText(img, f"Scan: {count}%", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
        cv2.imshow('image', img)
        
        # Slight delay to ensure different angles/lighting are captured
        time.sleep(0.05) 

    k = cv2.waitKey(1) & 0xff
    if k == ord('q'): 
        break
    elif count >= 100: 
         break

cam.release()
cv2.destroyAllWindows()

# --- TRAINING PHASE ---
print(f"\n [INFO] Training the brain for {face_name}...")

# Require opencv-contrib-python
try:
    recognizer = cv2.face.LBPHFaceRecognizer_create()
except AttributeError:
    print("❌ Error: cv2.face module missing. Run: pip install opencv-contrib-python")
    exit()

def getImagesAndLabels(path):
    imagePaths = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.jpg')]     
    faceSamples = []
    ids = []
    
    for imagePath in imagePaths:
        try:
            # Read directly as grayscale numpy array
            img_numpy = cv2.imread(imagePath, cv2.IMREAD_GRAYSCALE)
            if img_numpy is None:
                continue
                
            id = int(os.path.split(imagePath)[-1].split(".")[1])
            
            # Append the already-cropped image directly
            faceSamples.append(img_numpy)
            ids.append(id)
        except Exception as e:
            print(f"⚠️ Skipping corrupted file {imagePath}: {e}")
            
    return faceSamples, ids

faces, ids = getImagesAndLabels('dataset')

if len(faces) == 0:
    print("\n ❌ Training failed: No valid face images found in 'dataset/'.")
else:
    recognizer.train(faces, np.array(ids, dtype=np.int32))
    recognizer.write('trainer.yml') 
    print(f"\n ✅ Model trained with {len(faces)} images! S.A.N.D.Y. is ready for testing.")
