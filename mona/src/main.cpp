
#include <Wire.h>
#include "Mona_ESP_lib.h"
#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <ESPAsyncWebServer.h>
#include "AsyncJson.h"
#include "ArduinoJson.h"
#include <map>

/*
 * Create a file called credentials.h with the following two lines
 *  #define WIFI_SSID "yourssid"
 *  #define WIFI_PASSWORD "yourpassword"
 */
#include "credentials.h"

struct colour {
	int red;
	int green;
	int blue;
};

std::map<String, colour> colours = {
	{ "off", {0, 0, 0} },
	{ "black", {0, 0, 0} },
	{ "red", {20, 0, 0} },
	{ "green", {0, 20, 0} },
	{ "yellow", {10, 10, 0} },
	{ "blue", {0, 0, 20} },
	{ "magenta", {10, 0, 10} },
	{ "cyan", {0, 10, 10} },
	{ "white", {10, 10, 10} }
};

AsyncWebServer server(80);
AsyncWebSocket ws("/");

void sendState(bool allState);
void handleWebSocketMessage(void *arg, uint8_t *data, size_t len);
void onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len);
int getID();

// Settings

char identifier[10]; //Will be populated with a string like "mona-3"


void setup() {
	Mona_ESP_init();

	//LEDs to red during initialisation
	Set_LED(1,20,0,0);
	Set_LED(2,20,0,0);

	Serial.begin(115200);

	// Determine our ID
	sprintf(identifier, "mona-%d", getID());
	Serial.print("MONA ID: ");
	Serial.print(getID());
	Serial.print(", identifier: ");
	Serial.println(identifier);

	WiFi.begin(WIFI_SSID, WIFI_PASSWORD); //These should be defined in credentials.h
	int connect_timeout = 28; //~7 seconds
	while (WiFi.status() != WL_CONNECTED && connect_timeout > 0) {
		delay(250);
		Serial.print(".");
		connect_timeout--;
	}
	if (WiFi.status() == WL_CONNECTED) {
		//If we managed to connect to wifi, start up mDNS 
		Serial.print("IP: ");
		Serial.println(WiFi.localIP());
		if (!MDNS.begin(identifier)) {
			Serial.println("Error setting up mDNS.");
		}
	} else {
		//Otherwise, create our own access point
		Serial.print("Could not connect to existing network. Starting access point ");
		Serial.print(identifier);
		Serial.println("...");
		WiFi.softAP(identifier);
		Serial.print("IP: ");
		Serial.println(WiFi.softAPIP());
	}
	Serial.print("MAC address: ");
	Serial.println(WiFi.macAddress());

	//Initialise and start websocket server
	ws.onEvent(onEvent);
	server.addHandler(&ws);
	server.begin();

	//LEDs to green
	Set_LED(1,0,20,0);
	Set_LED(2,0,20,0);

	esp_log_level_set("*", ESP_LOG_WARN);
}

void loop(){
	//In the normal mode where the Mona is simply responding to websocket instructions, nothing is required in loop()
}


void onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len) {
	switch (type) {
	case WS_EVT_CONNECT:
		Serial.printf("WebSocket client #%u connected from %s\n", client->id(), client->remoteIP().toString().c_str());
		//LEDs to off
		Set_LED(1,0,0,0);
		Set_LED(2,0,0,0);
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

// Process an incoming websocket message
void handleWebSocketMessage(void *arg, uint8_t *data, size_t len) {
	StaticJsonDocument<500> reply;
	bool sendReply = false;

	AwsFrameInfo *info = (AwsFrameInfo*)arg;
	if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT) {
		StaticJsonDocument<300> json;
		DeserializationError err = deserializeJson(json, data);
		if (err) {
			Serial.print(F("deserializeJson() failed with code "));
			Serial.println(err.c_str());
			return;
		}

		if(json.containsKey("check_awake")) {
			reply["awake"] = true;
			sendReply = true;
		}

		if(json.containsKey("get_ir")) {
			JsonArray irlevels = reply.createNestedArray("ir");
			for(auto i = 0; i < 5; i++) irlevels.add(Get_IR(i+1));
			sendReply = true;
		}

		if(json.containsKey("get_battery")) {
			JsonObject battery = reply.createNestedObject("battery");
			battery["voltage"] = analogRead(Batt_Vol_pin) / 1000.0; // ADC value is in mV
			battery["percentage"] = Batt_Vol();
			sendReply = true;
		}

		if(sendReply) {
			String response;
			serializeJson(reply, response);
			ws.textAll(response);
		}

		if (json.containsKey("set_leds_colour")) {
			String col = json["set_leds_colour"];
			auto it = colours.find(col);
			if (it != colours.end()) {
				colour c = it->second;
				for(int i = 0; i < 2; i++) {
					Set_LED(i+1, c.red, c.green, c.blue);
				}
			}
		}

		if(json.containsKey("set_motor_speeds")) {
			auto mot = json["set_motor_speeds"];
			if(mot.containsKey("left") && mot.containsKey("right")) {
				int left_in = mot["left"];
				int right_in = mot["right"];
				int left_clamped = max(min(left_in, 100), -100);
                int right_clamped = max(min(right_in, 100), -100);
				int left_scaled = left_clamped * 1.3f;
                int right_scaled = right_clamped * 1.3f;
				if (left_scaled > 0) {
					Left_mot_forward(left_scaled);
				}
				else if (left_scaled < 0) {
					Left_mot_backward(-left_scaled);
				}
				else {
					Left_mot_stop();
				}
				if (right_scaled > 0) {
					Right_mot_forward(right_scaled);
				}
				else if (right_scaled < 0) {
					Right_mot_backward(-right_scaled);
				}
				else {
					Right_mot_stop();
				}
			}
		}
	}
}


// Get the ID of this robot
int getID() {
	String mac = WiFi.macAddress();
	return mac.charAt(15) + mac.charAt(16);
}
