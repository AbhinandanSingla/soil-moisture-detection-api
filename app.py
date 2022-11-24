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

        result = {}

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
                result["forecast"] = "Slight rain"
                result["description"] = "Slight rain"
                soil_moisture += (totalprecip_mm/25)*100
            elif(totalprecip_mm>= 2.6 and totalprecip_mm<=7.8):
                result["forecast"] = "Medium rain"
                result["description"] = "Medium rain"
                soil_moisture += (totalprecip_mm/25)*100
            else:
                result["forecast"] = "Heavy rain"
                result["description"] = "Heavy rain"
                soil_moisture += (totalprecip_mm/25)*100 

        else:
            result["forecast"] = "Humid"
            result["description"] = "In humid climate the soil mositure is unlikely to change other than the uppper soil"

        result["moisture"] = soil_moisture
        return result

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] =\
        'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Crops(db.Model):
   id = db.Column(db.Integer, primary_key = True)
   name = db.Column(db.String(100))
   days = db.Column(db.String(5))
   soil_type = db.Column(db.String(10))
   maxmoisture = db.Column(db.String(3))
   minmoisture = db.Column(db.String(3))

def __init__(self, id, name, days, soil_type, maxmoisture, minmoisture):
        self.id = id
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
    lat = request.args.get('lat') or "48.8567"
    lng = request.args.get('lng') or "2.3508"


    api_url = "http://api.weatherapi.com/v1/forecast.json?key=b26d8ccc756143b7be9181317222311&q=" + lat + "," + lng + "&days=5"
    response = urllib.request.urlopen(api_url)
    data = response.read()
    dict = json.loads(data)

    moisture_list = []
    temp_moisture = current_moisture

    crops = Crops.query.all()

    for forecast in dict["forecast"]["forecastday"]:
        result = predict_future_moisture(soil_type, temp_moisture, forecast["day"]["avgtemp_c"], forecast["day"]["condition"]["text"], forecast["day"]["totalprecip_mm"])
        temp_moisture = result["moisture"]
        result["action"] = "You have to irrigate the plants!!"
        result["required_irrigation"] = True
        
        for crop in crops:
            if str(crop.name) == str(crop_name):
                if(crop.minmoisture >= temp_moisture):
                    result["action"] = "You have to irrigate the plants!!"
                    result["required_irrigation"] = True
                else:
                    result["action"]= "You dont have to irrigate the plants!!"
                    result["required_irrigation"] = False


        result["temp"] = forecast["day"]["avgtemp_c"]
        result["date"] = forecast["date"]
        result["precip"] = forecast["day"]["totalprecip_mm"]
        moisture_list.append(result)
        print(result)

    

    return(moisture_list)

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