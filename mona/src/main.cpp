
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

//Current system mode
// 0 = normal. reacts only to websocket commands
// 1 = reacts to websocket commands but also use IR to avoid frontal collisions
uint8_t mode = 0;

// How many loops between running the autoavoid code (when in autoavoid mode)
#define AUTOAVOIDCOUNT 10

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

	static int avoiderstate = 0;
	static bool irvals[5];
	static int autoavoidcount = AUTOAVOIDCOUNT;

	switch(mode) {
		case 0:
			break;
		case 1:
			//autoavoider
			autoavoidcount--;
			if(autoavoidcount <= 0) {
				for(auto i = 1; i < 4; i++) irvals[i] = Detect_object(i+1, 35);
				//Ir leds 2/3/4 are in front
				if(irvals[1] || irvals[2] || irvals[3]) {
					Motors_stop();
				}
				autoavoidcount = AUTOAVOIDCOUNT;
			}
			break;
		case 2:
			//avoider
			switch(avoiderstate) {
				case 0: Motors_forward(150); break;
				case 1: Motors_spin_left(100); break;
				case 2: Motors_spin_right(100); break;
			}

			for(auto i = 0; i < 5; i++) irvals[i] = Detect_object(i+1, 35);
			if(irvals[1] || irvals[2] || irvals[3]) avoiderstate = 1;
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
			reply["reply"] = true;
			sendReply = true;
		}

		if(json.containsKey("get_ir_reflected")) {
			JsonArray irlevels = reply.createNestedArray("ir_reflected");
			for(auto i = 0; i < 5; i++) irlevels.add(Get_IR(i+1));
			sendReply = true;
		}

		if(json.containsKey("get_ir_ambient")) {
			JsonArray irlevels = reply.createNestedArray("ir_ambient");
			for(auto i = 0; i < 5; i++) irlevels.add(Read_IR(i+1));
			sendReply = true;
		}

		if(json.containsKey("get_battery")) {
			JsonObject battery = reply.createNestedObject("battery");
			battery["percentage"] = Batt_Vol();
			battery["voltage"] = analogRead(Batt_Vol_pin);
			battery["charging"] = "unsupported";
			sendReply = true;
		}

		if(sendReply) {
			String response;
			serializeJson(reply, response);
			ws.textAll(response);
		}

		if(json.containsKey("set_outer_leds")) {
			JsonArray leds = json["set_outer_leds"];
			if(leds.size() >= 2) {
				for(int i = 0; i < 2; i++) {
					JsonArray led = leds[i];
					if(led.size() >= 3) {
						Set_LED(i+1, led[0], led[1], led[2]);
					}
				}
			}
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

		if(json.containsKey("set_mode")) mode = json["set_mode"];
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



//Old interface 
//-------------
		/*if(json.containsKey("get-state")) sendState(true);
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
		}*/
// Send the state of the IR sensors over the websocket as JSON
// If allState is true, also send the IMU data
/*void sendState(bool allState) {
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
}*/

