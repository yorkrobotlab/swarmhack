/*
  Mona_ESP_lib.cpp - Implementation of the library for Mona ESP robot
  Created by Bart Garcia, November 2020.
  bart.garcia.nathan@gmail.com
  Released into the public domain.
*/
#include "Mona_ESP_lib.h"
#include "Adafruit_MCP23008.h"
#include <Adafruit_NeoPixel.h>

/* ----Library functions implementation for Mona ESP in C style----*/
//Initialize global objects
Adafruit_MCP23008 IO_expander;  // GPIO Expander
ADS7830 ADC;
Adafruit_NeoPixel RGB1(1, LED_RGB1, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel RGB2(1, LED_RGB2, NEO_GRB + NEO_KHZ800);
Adafruit_LSM9DS1 IMU = Adafruit_LSM9DS1();

//Global variables
sensors_event_t IMU_a, IMU_m, IMU_g, IMU_temp;

//Mona Init function - setup pinModes
void Mona_ESP_init(void){
	//Set PinModes
	pinMode(Mot_right_forward, OUTPUT);		//Motor control outputs
	pinMode(Mot_right_backward, OUTPUT);	//Motor control outputs
	pinMode(Mot_left_forward, OUTPUT);		//Motor control outputs
	pinMode(Mot_left_backward, OUTPUT);		//Motor control outputs
	pinMode(Mot_right_feedback, INPUT);		//Motor feedback inputs
	pinMode(Mot_right_feedback_2, INPUT);	//Motor feedback inputs
	pinMode(Mot_left_feedback, INPUT);		//Motor feedback inputs
	pinMode(Mot_left_feedback_2, INPUT);	//Motor feedback inputs
	pinMode(LED_RGB1, OUTPUT);						//WS2812b led pin
	pinMode(LED_RGB2, OUTPUT);						//WS2812b led pin

	//Setup PWM channels for motors
	ledcSetup(Mot_rig_for_pwm,Mot_freq,Mot_res);
	ledcAttachPin(Mot_right_forward, Mot_rig_for_pwm);//PWM settings MRF

	ledcSetup(Mot_rig_bac_pwm,Mot_freq,Mot_res);
	ledcAttachPin(Mot_right_backward, Mot_rig_bac_pwm);//PWM settings MRB

	ledcSetup(Mot_lef_for_pwm,Mot_freq,Mot_res);
	ledcAttachPin(Mot_left_forward, Mot_lef_for_pwm);//PWM settings MLF

	ledcSetup(Mot_lef_bac_pwm,Mot_freq,Mot_res);
	ledcAttachPin(Mot_left_backward, Mot_lef_bac_pwm);//PWM settings MLB
	//Turn off the Motor
	ledcWrite(Mot_rig_for_pwm, 0);
	ledcWrite(Mot_rig_bac_pwm, 0);
	ledcWrite(Mot_lef_for_pwm, 0);
	ledcWrite(Mot_lef_bac_pwm, 0);

	//Initialize I2C pins
	Wire.begin(SDA,SCL);  // I2C pins in the board
	// //Initialize I2C devices-----------------------------------------
	// //Initialize GPIO Expander
	IO_expander.begin(); // use default address 0
	IO_expander.pinMode(IR_enable_5, OUTPUT);
	IO_expander.pinMode(IR_enable_4, OUTPUT);
	IO_expander.pinMode(IR_enable_3, OUTPUT);
	IO_expander.pinMode(IR_enable_2, OUTPUT);
	IO_expander.pinMode(IR_enable_1, OUTPUT);
	IO_expander.pinMode(exp_5, INPUT);
	IO_expander.pinMode(exp_6, INPUT);
	IO_expander.pinMode(exp_7, INPUT);
	//Turn off all outputs
	IO_expander.digitalWrite(IR_enable_5, LOW);
	IO_expander.digitalWrite(IR_enable_4, LOW);
	IO_expander.digitalWrite(IR_enable_3, LOW);
	IO_expander.digitalWrite(IR_enable_2, LOW);
	IO_expander.digitalWrite(IR_enable_1, LOW);
	//Initialise ADC ADS7830
	ADC.getAddr_ADS7830(ADS7830_DEFAULT_ADDRESS); // 0x48
	ADC.setSDMode(SDMODE_SINGLE);    // Single-Ended Inputs
	ADC.setPDMode(PDIROFF_ADON); // Internal Reference OFF and A/D Converter ON
	//TODO: Add a check for the ADS, to ensure its working?

	//Initialize IMU and set up
	if (!IMU.begin())
	{
		//TODO: add only if debuging messages are enabled?
		Serial.println("Unable to initialize the LSM9DS1");
	}
	IMU.setupAccel(IMU.LSM9DS1_ACCELRANGE_2G);
	IMU.setupMag(IMU.LSM9DS1_MAGGAIN_4GAUSS);
	IMU.setupGyro(IMU.LSM9DS1_GYROSCALE_245DPS);

	//Set internal ADC attenuation to meassure Battery Voltate
	analogSetAttenuation(ADC_0db);// Sets the input attenuation for ALL ADC inputs
	//With ADC_0db ADC can measure up to approx. 800 mV

	//Initialize WS2812B LED driver constructor
	RGB1.begin();
	RGB1.clear(); // Set all rgb leds colors to 'off'
	RGB1.show();
	RGB2.begin();
	RGB2.clear(); // Set all rgb leds colors to 'off'
	RGB2.show();
}

//Right Motor
void Right_mot_forward(int speed){
	if(speed>255){
		speed = 255; //Limit max speed to the 8 bit resolution
	}
	ledcWrite(Mot_rig_for_pwm, speed);
	ledcWrite(Mot_rig_bac_pwm, 0);
}

void Right_mot_backward(int speed){
	if(speed>255){
		speed = 255; //Limit max speed to the 8 bit resolution
	}
	ledcWrite(Mot_rig_for_pwm, 0);
	ledcWrite(Mot_rig_bac_pwm, speed);
}

void Right_mot_stop(void){
	ledcWrite(Mot_rig_for_pwm, 0);
	ledcWrite(Mot_rig_bac_pwm, 0);
}
//Left Motor
void Left_mot_forward(int speed){
	if(speed>255){
		speed = 255; //Limit max speed to the 8 bit resolution
	}
	ledcWrite(Mot_lef_for_pwm, speed);
	ledcWrite(Mot_lef_bac_pwm, 0);
}

void Left_mot_backward(int speed){
	if(speed>255){
		speed = 255; //Limit max speed to the 8 bit resolution
	}
	ledcWrite(Mot_lef_for_pwm, 0);
	ledcWrite(Mot_lef_bac_pwm, speed);
}
void Left_mot_stop(void){
	ledcWrite(Mot_lef_for_pwm, 0);
	ledcWrite(Mot_lef_bac_pwm, 0);
}

//Both motors
void Motors_forward(int speed){
	Right_mot_forward(speed);
	Left_mot_forward(speed);
}

void Motors_backward(int speed){
	Right_mot_backward(speed);
	Left_mot_backward(speed);
}

void Motors_spin_left(int speed){
	Right_mot_forward(speed);
	Left_mot_backward(speed);
}

void Motors_spin_right(int speed){
	Right_mot_backward(speed);
	Left_mot_forward(speed);
}

void Motors_stop(void){
	Right_mot_stop();
	Left_mot_stop();
}

//IR sensors
void Enable_IR(int IR_number){
	if (IR_number>= 1 && IR_number<6){ //Ensure the IR number is within range
		if(IR_number==1){
			IO_expander.digitalWrite(IR_enable_1,HIGH);
		}
		if(IR_number==2){
			IO_expander.digitalWrite(IR_enable_2,HIGH);
		}
		if(IR_number==3){
			IO_expander.digitalWrite(IR_enable_3,HIGH);
		}
		if(IR_number==4){
			IO_expander.digitalWrite(IR_enable_4,HIGH);
		}
		if(IR_number==5){
			IO_expander.digitalWrite(IR_enable_5,HIGH);
		}
	}
}

void Disable_IR(int IR_number){
	if (IR_number>= 1 && IR_number<6){ //Ensure the IR number is within range
		if(IR_number==1){
			IO_expander.digitalWrite(IR_enable_1,LOW);
		}
		if(IR_number==2){
			IO_expander.digitalWrite(IR_enable_2,LOW);
		}
		if(IR_number==3){
			IO_expander.digitalWrite(IR_enable_3,LOW);
		}
		if(IR_number==4){
			IO_expander.digitalWrite(IR_enable_4,LOW);
		}
		if(IR_number==5){
			IO_expander.digitalWrite(IR_enable_5,LOW);
		}
	}
}

int Read_IR(int IR_number){
	if (IR_number>= 1 && IR_number<6){ //Ensure the IR number is within range
		if(IR_number==1){
			return ADC.Measure_SingleEnded(IR1_sensor); //Return value for IR1_sensor
		}
		if(IR_number==2){
			return ADC.Measure_SingleEnded(IR2_sensor);//Return value for IR2_sensor
		}
		if(IR_number==3){
			return ADC.Measure_SingleEnded(IR3_sensor);//Return value for IR3_sensor
		}
		if(IR_number==4){
			return ADC.Measure_SingleEnded(IR4_sensor);//Return value for IR4_sensor
		}
		if(IR_number==5){
			return ADC.Measure_SingleEnded(IR5_sensor);//Return value for IR5_sensor
		}
	}
	else {
		return 0; // Return a 0 as an error
	}
}

int Get_IR(int IR_number){
	uint8_t dark_val, light_val;
	if (IR_number>= 1 && IR_number<6){//Ensure the IR number is within range
		//Read dark value
		dark_val = Read_IR(IR_number);
		//Enable IR
		Enable_IR(IR_number);
		delay(1); //Give time for IR led to get to full brigthness
		//Read light value
		light_val = Read_IR(IR_number);
		//Disable IR
		Disable_IR(IR_number);
		return (uint8_t)abs(dark_val-light_val);
	}
	else {
		return 0; // Return a 0 as an error
	}
}

//Detect object, return true if there is an object detected in the selected IR
//Pass the IR to test and the threshold value to be used to the function
bool Detect_object(int IR_number, int threshold){
	uint8_t IR_val;
	if (IR_number>= 1 && IR_number<6){//Ensure the IR number is within range
		//Get IR measurement
		IR_val = Get_IR(IR_number);
		if(IR_val> threshold){
			return true;
		}
		else {
			return false;
		}
	}
	else {
		return false; // Return a 0 as an error
	}
}

//Battery Voltage
int Batt_Vol(void){
	//Monas battery voltage goes from 4.2V when full to 3V when depleted. Under 3.3V
	//The on board regulator will stop working. So working range is 4.2-3.3V
	//On boards resistors convert this voltage to 0.869-0.630V. Using 0dB attenuation
	//the range in values from the ADC is 3550-2750.
	int bat_percentage_available=0;
	int adc = analogRead(Batt_Vol_pin);
	bat_percentage_available = (adc-2750)/8; // Substract 3295 offset and conver to percentage
	//NOTE: when the USB cable is connected the read value will be USB voltage
	//And not the percentage of battery available
	if (bat_percentage_available > 100){
		bat_percentage_available = 100;
	}
	if (bat_percentage_available < 0){
		bat_percentage_available = 0;
	}
	return bat_percentage_available;
}

//LEDS control
void Set_LED(int Led_number, int Red, int Green, int Blue){
	double color=0;
	color = (Red << 16) | (Green <<  8) | Blue;
	if(Led_number==1){
		RGB1.fill(color,0,1);
		RGB1.show();
	}
	if(Led_number==2){
		RGB2.fill(color,0,1);
		RGB2.show();
	}
}

// Read sensors
void IMU_read_sensors(sensors_event_t *a, sensors_event_t *m, sensors_event_t *g, sensors_event_t *temp){
	IMU.read();  //trigger a read in all the sensors
	IMU.getEvent(a, m, g, temp);

}
