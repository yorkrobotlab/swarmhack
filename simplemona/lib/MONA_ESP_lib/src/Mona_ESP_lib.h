/*
  Mona_ESP_lib.h - Library of definitions and header file for the Mona ESP robot
  Created by Bart Garcia, November 2020.
  bart.garcia.nathan@gmail.com
  Released into the public domain.
*/

#ifndef Mona_ESP_lib_h
#define Mona_ESP_lib_h
#include "Arduino.h"
#include <Adafruit_MCP23008.h>
#include <Adafruit_NeoPixel.h>
#include "ADS7830.h"
#include <Wire.h>
#include <Adafruit_LSM9DS1.h>
#include <Adafruit_Sensor.h>  // not used but needed by LSM9DS1 lib

/* ----Pin Definitions for Mona ESP----*/
//Define IO Expander pins
#define exp_0                     0
#define exp_1                     1
#define exp_2                     2
#define exp_3                     3
#define exp_4                     4
#define exp_5                     5
#define exp_6                     6
#define exp_7                     7

//Define pins for the ADC
#define adc_0                     0
#define adc_1                     1
#define adc_2                     2
#define adc_3                     3
#define adc_4                     4
#define adc_5                     5
#define adc_6                     6
#define adc_7                     7

//Motor Control
//To move a motor the selected direction has to be set HIGH and the
//contrary direction low. Example: For right motor forward set:
// Mot_right_forward=HIGH and Mot_right_backward=LOW
#define Mot_right_forward         19
#define Mot_right_backward        21
#define Mot_left_forward          4
#define Mot_left_backward         18

//Motor Feedback
#define Mot_right_feedback	      39 //Pulses read from right motor encoder
#define Mot_right_feedback_2	    23 //Pulses read from right motor encoder
#define Mot_left_feedback	        35 //Pulses read from left motor encoder
#define Mot_left_feedback_2	      34  //Pulses read from left motor encoder

//IR Sensors
#define IR_enable_1			          exp_4	//Enable the IR in sensor 1 by setting to HIGH through IO Expander
#define IR1_sensor			          adc_7	//Left IR sensor
#define IR_enable_2			          exp_3	//Enable the IR in sensor 2 by setting to HIGH through IO Expander
#define IR2_sensor			          adc_6	//Left diagonal IR sensor
#define IR_enable_3			          exp_2	//Enable the IR in sensor 3 by setting to HIGH through IO Expander
#define IR3_sensor			          adc_5	//Front IR sensor
#define IR_enable_4			          exp_1	//Enable the IR in sensor 4 by setting to HIGH through IO Expander
#define IR4_sensor			          adc_4	//Right diagonal IR sensor
#define IR_enable_5			          exp_0	//Enable the IR in sensor 5 by setting to HIGH through IO Expander
#define IR5_sensor			          adc_0	//Right IR sensor

//On board LEDs
#define LED_RGB1				          22
#define LED_RGB2				          15

//Battery Voltage
#define Batt_Vol_pin		          36 //Analog read of the Battery Voltage

//I2C pins
#define SDA                       32
#define SCL                       33

//Break out pins
#define breakout_14               14
#define breakout_27               27
#define breakout_26               26
#define breakout_25               25
//I2C devices addresses
#define IO_EXP_address            0x20
#define ADC_address               0x48
#define LSM9DS1_mag_address       0x1E
#define LSM9DS1_accelgyro_address 0x6B

/* ----General Definitions for Mona ESP----*/
#define Mot_freq			            5000
#define Mot_res				            8
#define Mot_rig_for_pwm		        0
#define Mot_rig_bac_pwm		        1
#define Mot_lef_for_pwm		        2
#define Mot_lef_bac_pwm		        3

/* ----Library functions definitions for MonaV2 in C style----*/
//Mona Init function - setup pinModes
void Mona_ESP_init(void);
//Right Motor
void Right_mot_forward(int speed);
void Right_mot_backward(int speed);
void Right_mot_stop(void);
//Left Motor
void Left_mot_forward(int speed);
void Left_mot_backward(int speed);
void Left_mot_stop(void);
//Both motors
void Motors_forward(int speed);
void Motors_backward(int speed);
void Motors_spin_left(int speed);
void Motors_spin_right(int speed);
void Motors_stop(void);
//IR sensors
void Enable_IR(int IR_number);
void Disable_IR(int IR_number);
int Read_IR(int IR_number);
int Get_IR(int IR_number); // Enable, disable the IR, plus obtain measurement difference
bool Detect_object(int IR_number, int threshold);
//Battery Voltage
int Batt_Vol(void);
//LEDS control
void Set_LED(int Led_number, int Red, int Green, int Blue);
//IMU reading
void IMU_read_sensors(sensors_event_t *a, sensors_event_t *m, sensors_event_t *g, sensors_event_t *temp);

#endif
