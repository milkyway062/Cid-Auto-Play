import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))

import helpers
import detections

helpers.initialize()
print("tesseract path  :", detections._TESSERACT_PATH)
print("tesseract exists:", os.path.isfile(detections._TESSERACT_PATH))
print("OCR available   :", detections._OCR_AVAILABLE)
print("wave read       :", repr(detections._read_wave_number()))
