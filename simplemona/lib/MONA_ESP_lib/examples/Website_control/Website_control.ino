/*
  Website_control.ino - Usage of the libraries Example
  Control the Mona robot from a Website hosted in the Mona
  Created by Bart Garcia, January 2021.
  bart.garcia.nathan@gmail.com
  Released into the public domain.

  The code is largely based on WiFiAccessPoint.ino by
  Elochukwu Ifediora (fedy0)
*/

/*
//================HOW TO USE========================
After updating the program to the Mona-ESP
1 - Connect to the Mona_ESP acces point, you can use a computer or smart phone
2 - Open a browser and go to address 192.168.4.1
3 - Use the buttons in the website to control Mona_ESP
*/
//Include the Mona_ESP library
#include <Wire.h>
#include "Mona_ESP_lib.h"
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiAP.h>

//Define SSID and Password for the accespoint housted by Mona_ESP
const char* ssid     = "Mona_ESP";
const char* password = "monaisgreat";

WiFiServer server(80);
//Variables
bool IR_values[5] = {false, false, false, false, false};
//Threshold value used to determine a detection on the IR sensors.
//Reduce the value for a earlier detection, increase it if there
//false detections.
int threshold = 35;


void setup()
{
	//Initialize the MonaV2 robot
	Mona_ESP_init();
  //Turn on Blue light on LEDS to show initialization process
  Set_LED(1,0,0,20);
	Set_LED(2,0,0,20);
  //Initialize Serial for debugging
  Serial.begin(115200);
  //Create the access point
  Serial.println("Configuring access point...");
  // You can remove the password parameter if you want the AP to be open.
  WiFi.softAP(ssid);
  IPAddress myIP = WiFi.softAPIP();
  Serial.print("AP IP address: ");
  Serial.println(myIP);
  server.begin();
  Serial.println("Server started");
  //Initialization finished, turn off LEDs
  Set_LED(1,0,0,0);
	Set_LED(2,0,0,0);
}


void loop(){
  //Turn Leds Green to show that mona is ready to get commands
  Set_LED(1,0,10,0);
	Set_LED(2,0,10,0);
  WiFiClient client = server.available();   // listen for incoming clients
  if (client) {                             // if you get a client,
      Set_LED(1,0,0,20);                    //Turn on Blue to show command execution
  	  Set_LED(2,0,0,20);                    //Turn on Blue to show command execution
      Serial.println("New Client.");           // print a message out the serial port
      String currentLine = "";                // make a String to hold incoming data from the client
      while (client.connected()) {            // loop while the client's connected
        if (client.available()) {             // if there's bytes to read from the client,
          char c = client.read();             // read a byte, then
          Serial.write(c);                    // print it out the serial monitor
          if (c == '\n') {                    // if the byte is a newline character

            // if the current line is blank, you got two newline characters in a row.
            // that's the end of the client HTTP request, so send a response:
            if (currentLine.length() == 0) {
              // HTTP headers always start with a response code (e.g. HTTP/1.1 200 OK)
              // and a content-type so the client knows what's coming, then a blank line:
              client.println("HTTP/1.1 200 OK");
              client.println("Content-type:text/html");
              client.println();
              client.println("<html><body><h1>MONA-ESP </h1>");
               // the content of the HTTP response follows the header:
              client.print("<a href=\"/F\"> <button>Forward!</button></a><br>");
              client.print("<a href=\"/B\"> <button>Backward!</button></a><br>");
              client.print("<a href=\"/L\"> <button>Turn Left!</button></a><br>");
              client.print("<a href=\"/R\"> <button>Turn Right!</button></a><br>");
              client.println("</body></html>");


              // The HTTP response ends with another blank line:
              client.println();
              // break out of the while loop:
              break;
            } else {    // if you got a newline, then clear currentLine:
              currentLine = "";
            }
          } else if (c != '\r') {  // if you got anything else but a carriage return character,
            currentLine += c;      // add it to the end of the currentLine
          }

          // Check to see if the client request was "GET /H" or "GET /L":
          if (currentLine.endsWith("GET /F")) {
            Motors_forward(150);
            delay(1000);
            Motors_stop();
          }
          if (currentLine.endsWith("GET /B")) {
            Motors_backward(150);
            delay(1000);
            Motors_stop();
          }
          if (currentLine.endsWith("GET /R")) {
            Motors_spin_right(150);
            delay(1000);
            Motors_stop();
          }
          if (currentLine.endsWith("GET /L")) {
            Motors_spin_left(150);
            delay(1000);
            Motors_stop();
          }
        }
      }
      // close the connection:
      client.stop();
      Serial.println("Client Disconnected.");
    }
}
