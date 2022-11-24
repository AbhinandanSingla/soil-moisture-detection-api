import io
import random
import base64
import os
import json
import pandas as pd
from types import SimpleNamespace
import urllib.request, json
import numpy as np
from keras.models import load_model
from PIL import Image
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from statistics import mean
from sqlalchemy import and_
import sqlite3
conn = sqlite3.connect('database.db')
c = conn.cursor()

basedir = os.path.abspath(os.path.dirname(__file__))

red_model = load_model('model-redsoil-v3.h5')
black_model = load_model('model-redsoil-v3.h5')
alluvial_model = load_model('model-redsoil-v3.h5')

cropsCSV = pd.read_csv('crops.csv')

# write the data to a sqlite table
cropsCSV.to_sql('crops', conn, if_exists='append', index = False)
print(cropsCSV)
#Assume you received this JSON response
#cropJsonData = '{"crops": [{ "name": "Rice", "days": 100, "maxmoisture": 80, "minmoisture":40 }, { "name": "Sunflower", "days": 100, "maxmoisture": 90, "minmoisture":60 }, { "name": "Tea", "days": 100, "maxmoisture": 60, "minmoisture":50 }, { "name": "Wheat", "days": 100, "maxmoisture": 70, "minmoisture":40 }]}'

# Parse JSON into an object with attributes corresponding to dict keys.
#parsedCropsData = json.loads(cropJsonData, object_hook=lambda d: SimpleNamespace(**d))

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

def predict_future_moisture(soil_type, current_moisture, average_temp_day, forecast, total_precip_day):

        soil_moisture = int(current_moisture)   
        soil = soil_type
        avgtemp_c = average_temp_day
        text = forecast # "clear"
        totalprecip_mm = int(total_precip_day)  # 5

        if("sunny" == text or "clear" in text):
            if avgtemp_c<=10:
                print("No Change in soil mositure")
            elif avgtemp_c <=15 and avgtemp_c >10:
                percent  = 0
                if(soil=='black'):
                    percent  = (56/500)*100

                elif(soil=='red'):
                    percent  = (106/500)*100

                else:
                    percent  = (126/500)*100
                soil_moisture -= percent
            else:
                percent  = 0
                if(soil=='black'):
                    percent  = (int)((12.6*10)/500)*100

                elif(soil=='red'):
                    percent  = (int)((13.6*10)/500)*100

                else:
                    percent  = (int)((14.6*10)/500)*100
                soil_moisture -= percent



        elif("rain" in text):
            if(totalprecip_mm >=0 and totalprecip_mm<=2.5):
                print("Slight rain")
                soil_moisture += (totalprecip_mm/25)*100
            elif(totalprecip_mm>= 2.6 and totalprecip_mm<=7.8):
                print("Medium rain")
                soil_moisture += (totalprecip_mm/25)*100
            else:
                print("Heavy Rain")
                soil_moisture += (totalprecip_mm/25)*100 

        else:
            print("Humid")
            print("In humid climate the soil mositure is unlikely to change other than the uppper soil")

        return soil_moisture

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] =\
        'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Crops(db.Model):
   name = db.Column(db.String(100), primary_key = True)
   days = db.Column(db.String(5))
   soil_type = db.Column(db.String(10))
   maxmoisture = db.Column(db.String(3))
   minmoisture = db.Column(db.String(3))

def __init__(self, name, days, soil_type, maxmoisture, minmoisture):
        self.name = name
        self.days = days
        self.soil_type = soil_type
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

@app.route('/predict-future-moisture', methods=['GET'])
def futute_weather_predict():
    soil_type = request.args.get('soil_type')
    current_moisture = request.args.get('moisture')
    crop_name = request.args.get('crop_name')

    api_url = "http://api.weatherapi.com/v1/forecast.json?key=b26d8ccc756143b7be9181317222311&q=48.8567,2.3508&days=10"
    response = urllib.request.urlopen(api_url)
    data = response.read()
    dict = json.loads(data)

    moisture_list = []
    temp_moisture = current_moisture
    for forecast in dict["forecast"]["forecastday"]:
        value = predict_future_moisture(soil_type, temp_moisture, forecast["day"]["avgtemp_c"], forecast["day"]["condition"]["text"], forecast["day"]["totalprecip_mm"])
        print(value)
        temp_moisture = value
        moisture_list.append(value)
        
    minimum_moisture = min(moisture_list)

    crops = Crops.query.all()
    crop_minmoisture = 0

    for crop in crops:
        if crop.name == crop_name and crop.soil_type == soil_type:
            crop_minmoisture = crop.minmoisture
            print(crop.minmoisture)
            print(crop_minmoisture)

            break


    if crop_minmoisture <= minimum_moisture:
        return jsonify({"result": "No need to irrigate the plants"})
    else:
        return jsonify({"result": "You have to irrigate the plants"})

@app.route('/eligible-crops', methods=['GET'])
def eligible_crops():
    eligibleCrops = []
    soilMoisture = request.args.get('soilMoisture')
    soilType = request.args.get('soil_type')

    if not soilMoisture:
        return "Soil Moisture not found!"

    soilMoisture = int(soilMoisture)
    crops = Crops.query.all()

    for _crops in crops:
        if (soilMoisture <=int(_crops.maxmoisture) and soilMoisture >= int(_crops.minmoisture)) and soilType == _crops.soil_type:
            eligibleCrops.append({"name":_crops.name, "soil_type": _crops.soil_type, "days": _crops.days, "maxmoisture": _crops.maxmoisture, "minmoisture": _crops.minmoisture})

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