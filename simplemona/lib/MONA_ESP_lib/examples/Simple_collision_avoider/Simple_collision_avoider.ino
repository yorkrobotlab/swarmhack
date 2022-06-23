/*
  Simple_collision_avoider.ino - Usage of the libraries Example
  Using the Mona_ESP library in C style.
  Created by Bart Garcia, December 2020.
  bart.garcia.nathan@gmail.com
  Released into the public domain.
*/
//Include the Mona_ESP library
#include <Wire.h>
#include "Mona_ESP_lib.h"


//Variables
bool IR_values[5] = {false, false, false, false, false};
//Threshold value used to determine a detection on the IR sensors.
//Reduce the value for a earlier detection, increase it if there
//false detections.
int threshold = 35;
//State Machine Variable
// 0 -move forward , 1 - forward obstacle , 2 - right proximity , 3 - left proximity
int state, old_state;

void setup()
{
	//Initialize the MonaV2 robot
	Mona_ESP_init();
  //Initialize variables
  state=0;
  old_state=0;
}


void loop(){
  //--------------Motors------------------------
  //Set motors movement based on the state machine value.
  if(state == 0){
    // Start moving Forward
    Motors_forward(150);
  }
  if(state == 1){
    //Spin to the left
    Motors_spin_left(100);
  }
    if(state == 2){
    //Spin to the left
    Motors_spin_left(100);
  }
    if(state == 3){
    //Spin to the right
    Motors_spin_right(100);
  }

  //--------------IR sensors------------------------
  //Decide future state:
	//Read IR values to determine maze walls
  IR_values[0] = Detect_object(1,threshold);
  IR_values[1] = Detect_object(2,threshold);
  IR_values[2] = Detect_object(3,threshold);
  IR_values[3] = Detect_object(4,threshold);
  IR_values[4] = Detect_object(5,threshold);

	//--------------State Machine------------------------
	//Use the retrieved IR values to set state
	//Check for frontal wall, which has priority
	if(IR_values[2] or IR_values[3] or IR_values[4]){
		state=1;
	}
	else if(IR_values[0]){ //Check for left proximity
		state=3;
	}
	else if(IR_values[4]){// Check for right proximity
		state=2;
	}
	else{ //If there are no proximities, move forward
		state=0;
	}

	delay(5);
}
