
# S.A.N.D.Y. 
**Smart Assistant for Networked Devices & You**

## Overview
S.A.N.D.Y. is a bilingual AI smart home assistant built as a school project to help elderly individuals manage their daily routines and secure their homes. The system bridges cloud-based LLM processing with local microcontrollers and computer vision, allowing users to control appliances through accessible, multilingual conversations while actively monitoring the home for physical security threats.

## Key Features
* **Bilingual Conversational Interface:** Designed for accessibility, allowing elderly users to interact naturally with the system in English and Hindi(currently working on adding Tamil as third language) using the xAI Grok API.
* **Intruder Detection (Facial Recognition):** Incorporates a local computer vision model that scans video inputs from my webcam to identify known individuals. If an unrecognized face or potential intruder is detected, the system flags the security threat to protect vulnerable residents from theft.
* **ESP8266 Smart Home Control:** The software interfaces directly with an ESP8266 microcontroller running custom C++ code to execute physical automations, such as toggling lights and managing appliances.

## Tech Stack
* **Core Logic & API Routing:** Python
* **Conversational AI Engine:** xAI API (Grok)
* **Computer Vision:** Python facial recognition libraries (e.g., OpenCV)
* **Hardware & IoT:** ESP8266 Microcontroller, C++

## Active Development
This project is an ongoing exploration of bridging high-level AI cloud APIs with low-level local hardware execution and security monitoring. 

## License
[MIT License](LICENSE)
