import io
import random
import json
from types import SimpleNamespace
import numpy as np
from keras.models import load_model
from PIL import Image
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy


model = load_model('model.h5')

#Assume you received this JSON response
cropJsonData = '{"crops": [{ "name": "Rice", "days": 100, "maxmoisture": 80, "minmoisture":40 }, { "name": "Sunflower", "days": 100, "maxmoisture": 90, "minmoisture":60 }, { "name": "Tea", "days": 100, "maxmoisture": 60, "minmoisture":50 }, { "name": "Wheat", "days": 100, "maxmoisture": 70, "minmoisture":40 }]}'

# Parse JSON into an object with attributes corresponding to dict keys.
parsedCropsData = json.loads(cropJsonData, object_hook=lambda d: SimpleNamespace(**d))
print(parsedCropsData.crops[0].name, parsedCropsData.crops[0].days)

def prepare_image(img):
    img = Image.open(io.BytesIO(img))
    img = img.resize((224, 224))
    img = np.array(img)
    img = np.expand_dims(img, 0)
    return img


def predict_result(img):
    return model.predict(img)


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
    #img = prepare_image(img_bytes)

    #return jsonify(prediction=predict_result(img))
    return {"moisture":str(100*random.random())}

@app.route('/eligible-crops', methods=['GET'])
def index():
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
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')