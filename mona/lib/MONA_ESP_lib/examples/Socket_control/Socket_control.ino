/*
  Socket_control.ino -
  Control the Mona ESP through the network using sockets.
  Created by Bart Garcia, January 2021.
  bart.garcia.nathan@gmail.com
  Released into the public domain.
===========================================================
	To use:
	-In this code modify  line 26 and 27, set the ssid and password of
	the network that will be used to control Mona_ESP.
	-Compile and upload the code to Mona_ESP.
	-Open a serial terminal (For example the arduino serial Monitor)
	and check what is the IP given to Mona_ESP
	-Modify in the file 'Control_client.py' the host value, enter
	the IP read from the terminal in the previous step. Save the file
	-Run with python the file 'Control_client.py'
	-Enjoy controlling Mona_ESP through the network.
*/
//Include the Mona_ESP library
#include "Mona_ESP_lib.h"
#include <Wire.h>
#include <WiFi.h>

//Enter the SSID and password of the WiFi you are going
//to use to communicate through
const char* ssid = "NetworkForMonaESP";
const char* password =  "WeLoveMONA123";
//A server is started using port 80
WiFiServer wifiServer(80);

void setup() {
  //Initialize the MonaV2 robot
	Mona_ESP_init();
	//Turn LEDs to show that the Wifi connection is not ready
	Set_LED(1,20,0,0);
	Set_LED(2,20,0,0);
  //Initialize serial port
  Serial.begin(115200);
  //Connect to the WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print("Connecting to WiFi ");
    Serial.print(ssid);
    Serial.println("....");
  }
  Serial.println("Connected to the WiFi network");
  //Print the IP of the Mona_ESP, which is information
  //needed communicate throught the sockets.
  Serial.println(WiFi.localIP());
  //Start the server as a host
  wifiServer.begin();
	//Blink Leds in green to show end of booting/connecting
	Set_LED(1,0,20,0);
	Set_LED(2,0,20,0);
	delay(500);
	Set_LED(1,0,0,0);
	Set_LED(2,0,0,0);
	delay(500);
	Set_LED(1,0,20,0);
	Set_LED(2,0,20,0);
	delay(500);
	Set_LED(1,0,0,0);
	Set_LED(2,0,0,0);
}


void loop() {
  //Create a client object
  WiFiClient client = wifiServer.available();
  //Wait for a client to connect to the socket open in the Mona_ESP
  if (client) {
    while (client.connected()) {
      //Read data sent by the client
      while (client.available()>0) {
        char c = client.read();
        //Decode and execute the obtained message
        if(c=='F'){
          Motors_forward(150);
          delay(1000);
          Motors_stop();
        }
        if(c=='B'){
          Motors_backward(150);
          delay(1000);
          Motors_stop();
        }
        if(c=='R'){
          Motors_spin_right(150);
          delay(500);
          Motors_stop();
        }
        if(c=='L'){
          Motors_spin_left(150);
          delay(500);
          Motors_stop();
        }
      }
    }
    //Client disconnects after sending the data.
    client.stop();
    Serial.println("Client disconnected");
  }
}
