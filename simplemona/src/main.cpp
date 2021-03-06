
#include <Wire.h>
#include "Mona_ESP_lib.h"
#include <Arduino.h>
#include <WiFi.h>
#include <ESPmDNS.h>
#include <ESPAsyncWebServer.h>
#include "AsyncJson.h"
#include "ArduinoJson.h"

/*
 * Create a file called credentials.h with the following two lines
 *  #define WIFI_SSID "yourssid"
 *  #define WIFI_PASSWORD "yourpassword"
 */
#include "credentials.h"

AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

void sendState(bool allState);
void handleWebSocketMessage(void *arg, uint8_t *data, size_t len);
void onEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len);
int getID();

// Settings

// Mapping of MAC address to ID
#define NUM_MAPPINGS 10

typedef struct {
	String mac;
	uint8_t id;
} mapping_t;

mapping_t mappings[NUM_MAPPINGS] = {
	{"8C:CE:4E:BB:4C:08", 31},
	{"8C:CE:4E:BB:4C:00", 32},
	{"0C:DC:7E:51:CA:74", 33},
	{"C4:4F:33:54:24:B5", 34},
	{"8C:CE:4E:BB:4B:DC", 35},
	{"8C:CE:4E:BB:4B:D0", 36},
	{"0C:DC:7E:51:CA:3C", 37},
	{"8C:CE:4E:BB:4B:E4", 38},
	{"C4:4F:33:53:FA:0D", 39},
	{"8C:CE:4E:BB:4C:A0", 40}
};

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
		Serial.print("\nConnected to ");
		Serial.print(WIFI_SSID);
		Serial.print(", IP: ");
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
	server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
		request->send(200, "text/plain", "Hello, world");
	});
	server.begin();

	//LEDs to team colour
	if(getID() % 2) {
		Set_LED(1,0,0,255);
		Set_LED(2,0,0,255);
	} else {
		Set_LED(1,255,0,0);
		Set_LED(2,255,0,0);
	}

	esp_log_level_set("*", ESP_LOG_WARN);
}

void loop(){
	
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

// Process an incoming websocket message
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

		if(json.containsKey("set_leds_colour")) {
			JsonArray col = json["set_leds_colour"];
			if(col.size() >= 3) {
				for(int i = 0; i < 2; i++) {
					Set_LED(i+1, col[0], col[1], col[2]);
				}
			}
		}
		
		if(json.containsKey("set_motor_speeds")) {
			auto mot = json["set_motor_speeds"];
			if(mot.containsKey("left")) {
				int val = mot["left"];
				if(val > 0) Left_mot_forward(val);
				if(val < 0) Left_mot_backward(abs(val));
				if(val == 0) Left_mot_stop();
			}
			if(mot.containsKey("right")) {
				int val = mot["right"];
				if(val > 0) Right_mot_forward(val);
				if(val < 0) Right_mot_backward(abs(val));
				if(val == 0) Right_mot_stop();
			}
		}
	}
}


// Get the ID of this robot based on looking our MAC address up in the "mappings" table
int getID() {
	String mac = WiFi.macAddress();
	for(auto i = 0; i < NUM_MAPPINGS; i++) {
		if(mac == mappings[i].mac) return mappings[i].id;
	}
	return mac.charAt(15) + mac.charAt(16);
}
