from flask import Flask, request, jsonify
import json
from geopy.distance import geodesic
import paho.mqtt.client as mqtt
import threading

# ================= FLASK APP =================
app = Flask(__name__)

# ================= LOAD RSU DATA =================
with open("rsu_data.json") as f:
    RSU_DATA = json.load(f)

# Distance threshold (meters)
RSU_RANGE = 1000   # increased for better detection

# ================= MQTT SETUP =================
mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print("✅ MQTT Connected with code:", rc)

mqtt_client.on_connect = on_connect

try:
    mqtt_client.connect("broker.hivemq.com", 1883, 60)
    mqtt_client.loop_start()
except Exception as e:
    print("❌ MQTT Connection Failed:", e)

# ================= HOME =================
@app.route("/")
def home():
    return "🚑 Emergency Route Backend Running"

# ================= MQTT ASYNC FUNCTION =================
def publish_mqtt_async(topic, message):

    def task():
        try:
            print(f"🚦 Publishing → {topic} : {message}")

            mqtt_client.publish(topic, message, retain=True)

            print(f"📡 MQTT SENT → {topic}")

        except Exception as e:
            print("❌ MQTT Error:", e)

    threading.Thread(target=task).start()

# ================= MAIN API =================
@app.route("/get_rsus", methods=["POST"])
def get_rsus():

    try:
        data = request.json
        route = data.get("route", [])

        print(f"📥 Received route points: {len(route)}")

        activated_rsus = []
        activated_ids = set()

        for rsu in RSU_DATA:

            rsu_point = (rsu["lat"], rsu["lon"])

            closest_point = None
            min_distance = float("inf")

            # 🔍 Find closest route point
            for point in route:
                route_point = (point["lat"], point["lng"])
                distance = geodesic(rsu_point, route_point).meters

                if distance < min_distance:
                    min_distance = distance
                    closest_point = point

            # ✅ Activate RSU if within range
            if min_distance <= RSU_RANGE and rsu["id"] not in activated_ids:

                direction = closest_point.get("direction", "STRAIGHT")

                rsu["direction"] = direction
                activated_rsus.append(rsu)
                activated_ids.add(rsu["id"])

                topic = f"rsu/{rsu['id']}/control"

                print(f"🚦 Activating RSU {rsu['id']} → {direction}")

                # 🔥 SEND MQTT (ASYNC - NO TIMEOUT)
                publish_mqtt_async(topic, direction)

        return jsonify({
            "rsus_on_route": activated_rsus,
            "total": len(activated_rsus)
        })

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500


# ================= RUN SERVER =================
if __name__ == "__main__":
    app.run()