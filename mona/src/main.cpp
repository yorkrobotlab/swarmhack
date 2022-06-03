
#include <Wire.h>
#include "Mona_ESP_lib.h"
#include <Arduino.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include "AsyncJson.h"
#include "ArduinoJson.h"

#include "credentials.h"

const char* ssid = "Mona_ESP";
AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

void sendState(bool allState);
void handleWebSocketMessage(void *arg, uint8_t *data, size_t len);
void onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len);

uint8_t mode = 0;

void setup() {
	Mona_ESP_init();

	Set_LED(1,20,0,0);
	Set_LED(2,20,0,0);

	Serial.begin(115200);

	WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
	int connect_timeout = 28; //7 seconds
	while (WiFi.status() != WL_CONNECTED && connect_timeout > 0) {
		delay(250);
		Serial.print(".");
		connect_timeout--;
	}
	if (WiFi.status() == WL_CONNECTED) {
		Serial.println(WiFi.localIP());
		Serial.println("Wifi started");
	} else {
		Serial.println("Configuring access point...");
		WiFi.softAP(ssid);
		IPAddress myIP = WiFi.softAPIP();
		Serial.print("AP IP address: ");
		Serial.println(myIP);
	}

	ws.onEvent(onEvent);
	server.addHandler(&ws);
	server.begin();

	Set_LED(1,0,20,0);
	Set_LED(2,0,20,0);
}

void loop(){
	static int avoiderstate = 0;
	static bool irvals[5];

	switch(mode) {
		case 0:
			//w00t
			break;
		case 1:
			//avoider
			switch(avoiderstate) {
				case 0: Motors_forward(150); break;
				case 1: Motors_spin_left(100); break;
				case 2: Motors_spin_right(100); break;
			}

			for(auto i = 0; i < 5; i++) irvals[i] = Detect_object(i+1, 35);
			if(irvals[2] || irvals[3] || irvals[4]) avoiderstate = 1;
			else if(irvals[0]) avoiderstate = 2;
			else if(irvals[4]) avoiderstate = 1;
			else avoiderstate = 0;
			delay(5);
			break;
	}
}


void onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len) {
	switch (type) {
	case WS_EVT_CONNECT:
		Serial.printf("WebSocket client #%u connected from %s\n", client->id(), client->remoteIP().toString().c_str());
		break;
	case WS_EVT_DISCONNECT:
		Serial.printf("WebSocket client #%u disconnected\n", client->id());
		break;
	case WS_EVT_DATA:
		handleWebSocketMessage(arg, data, len);
		break;
	case WS_EVT_PONG:
	case WS_EVT_ERROR:
		break;
	}
}

void handleWebSocketMessage(void *arg, uint8_t *data, size_t len) {
	AwsFrameInfo *info = (AwsFrameInfo*)arg;
	if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT) {
		StaticJsonDocument<300> json;
		DeserializationError err = deserializeJson(json, data);
		if (err) {
			Serial.print(F("deserializeJson() failed with code "));
			Serial.println(err.c_str());
			return;
		}
		if(json.containsKey("get-state")) sendState(true);
		if(json.containsKey("get-ir")) sendState(false);
		if(json.containsKey("set-state")) {
			auto set = json["set-state"];
			if(set.containsKey("left_motor")) {
				int val = set["left_motor"];
				if(val > 0) Left_mot_forward(val);
				if(val < 0) Left_mot_backward(abs(val));
			}
			if(set.containsKey("right_motor")) {
				int val = set["right_motor"];
				if(val > 0) Right_mot_forward(val);
				if(val < 0) Right_mot_backward(abs(val));
			}
			if(set.containsKey("left_motor_forward")) Left_mot_forward(set["left_motor_forward"]);
			if(set.containsKey("left_motor_backward")) Left_mot_backward(set["left_motor_backward"]);
			if(set.containsKey("right_motor_forward")) Right_mot_forward(set["right_motor_forward"]);
			if(set.containsKey("right_motor_backward")) Right_mot_backward(set["right_motor_forward"]);
			if(set.containsKey("left_motor_stop")) Left_mot_stop();
			if(set.containsKey("right_motor_stop")) Right_mot_stop();
			if(set.containsKey("led")) {
				auto led = set["led"];
				if(led.containsKey("num") && led.containsKey("r") && led.containsKey("g") && led.containsKey("b")) {
					Set_LED(led["num"], led["r"], led["g"], led["b"]);
				}
			}
		}
		if(json.containsKey("set-mode")) mode = json["set-mode"];
	}
}

void sendState(bool allState) {
	StaticJsonDocument<600> data;

	JsonArray irlevels = data.createNestedArray("ir");
	for(auto i = 0; i < 5; i++) {
		irlevels.add(Get_IR(i));
	}
	if(allState) {
		data["battery_voltage"] = Batt_Vol();

		sensors_event_t accel, mag, gyro, temp;
		IMU_read_sensors(&accel, &mag, &gyro, &temp);

		data["accel.heading"] = accel.acceleration.heading;
		data["accel.pitch"] = accel.acceleration.pitch;
		data["accel.roll"] = accel.acceleration.roll;

		data["mag.heading"] = mag.magnetic.heading;
		data["mag.pitch"] = mag.magnetic.pitch;
		data["mag.roll"] = mag.magnetic.roll;

		data["gyro.heading"] = gyro.gyro.heading;
		data["gyro.pitch"] = gyro.gyro.pitch;
		data["gyro.roll"] = gyro.gyro.roll;

		data["temp"] = temp.temperature;
	}
	String response;
	serializeJson(data, response);
	ws.textAll(response);
}
