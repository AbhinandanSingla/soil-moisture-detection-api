import io
import random
import base64
import json
from types import SimpleNamespace
import numpy as np
from keras.models import load_model
from PIL import Image
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy


red_model = load_model('model-redsoil-v2.h5')
black_model = load_model('model-redsoil-v2.h5')
alluvial_model = load_model('model-redsoil-v2.h5')

#Assume you received this JSON response
cropJsonData = '{"crops": [{ "name": "Rice", "days": 100, "maxmoisture": 80, "minmoisture":40 }, { "name": "Sunflower", "days": 100, "maxmoisture": 90, "minmoisture":60 }, { "name": "Tea", "days": 100, "maxmoisture": 60, "minmoisture":50 }, { "name": "Wheat", "days": 100, "maxmoisture": 70, "minmoisture":40 }]}'

# Parse JSON into an object with attributes corresponding to dict keys.
parsedCropsData = json.loads(cropJsonData, object_hook=lambda d: SimpleNamespace(**d))

def prepare_image(img):
    img = Image.open(io.BytesIO(img))
    img = img.resize((224, 224))
    img = np.array(img)
    img = img.reshape((-1,224,224,3))
    return img

def predict_result(img, soilType):
    if soilType == "red":
        return red_model.predict(img)
    if soilType == "black":
        return black_model.predict(img)
    if soilType == "alluvial":
        return alluvial_model.predict(img)

app = Flask(__name__)
app.config ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crops.sqlite3'

db = SQLAlchemy(app)

class crops(db.Model):
   id = db.Column('crop_id', db.Integer, primary_key = True)
   name = db.Column(db.String(100))
   days = db.Column(db.String(5))
   maxmoisture = db.Column(db.String(3))
   minmoisture = db.Column(db.String(3))


def __init__(self, name, days, maxmoisture, minmoisture):
   self.name = name
   self.days = days
   self.maxmoisture = maxmoisture
   self.minmoisture = minmoisture

def find_soil_type(latitude, longitude):
    pass

@app.route('/predict', methods=['POST'])
def infer_image():
    soil_type = request.args.get('soil_type')

    if 'file' not in request.files:
        return "Please try again. The Image doesn't exist"
    
    if not soil_type:
        return "Please try again. The soil type doesn't exist"

    file = request.files.get('file')

    if not file:
        return

    img_bytes = file.read()
    img = prepare_image(img_bytes)
    value = predict_result(img, soil_type)
    a = np.argmax(value)

    return {"moisture":str(a*10)}

@app.route('/eligible-crops', methods=['GET'])
def eligible_crops():
    eligibleCrops = []
    soilMoisture = request.args.get('soilMoisture')

    if not soilMoisture:
        return "Soil Moisture not found!"

    soilMoisture = int(soilMoisture)

    #print(crops.query.filter_by(maxmoisture < 90).all())

    for _crops in parsedCropsData.crops:
        if soilMoisture <=_crops.maxmoisture   and soilMoisture >= _crops.minmoisture:
            eligibleCrops.append({"name":_crops.name, "days": _crops.days, "maxmoisture": _crops.maxmoisture, "minmoisture": _crops.minmoisture})
    
    return jsonify(eligibleCrops)

@app.route('/location-soil-type', methods=['GET'])
def location_mapping():
    latitude = request.args.get('lat')
    longitude = request.args.get('lng')

    if latitude or longitude:
        return "Please try again! Wrong coordinates are passed!"

    soilType = find_soil_type(latitude, longitude)
    
    soilType = "Black"

    return jsonify({"soil-type": soilType})
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')