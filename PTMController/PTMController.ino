int SER_Pin = 8;   //pin 14 on the 75HC595
int RCLK_Pin = 9;  //pin 12 on the 75HC595
int SRCLK_Pin = 10; //pin 11 on the 75HC595

#define TRUE 1
#define FALSE 0

#define SHUTTER_Pin 19 

//How many of the shift registers - change this
#define number_of_74hc595s 7 
#define number_of_LEDs 50 

//do not touch
#define numOfRegisterPins number_of_74hc595s * 8
#define TRUE 1
#define FALSE 0

boolean registers[numOfRegisterPins];
int time    = 100;
int incomingByte  = 0;
int is_shooting = FALSE;
#define A 11
#define B 12
#define C 13
#define D 14
#define E 15
#define F_SEG 16
#define G 17

// Pins driving common anodes
#define CA1 6
#define CA2 7

// Pins for A B C D E F G, in sequence
const int segs[7] = { A, B, C, D, E, F_SEG, G };
const byte numbers[10] = { 0b1000000, 0b1111001, 0b0100100, 0b0110000, 0b0011001, 0b0010010,
0b0000010, 0b1111000, 0b0000000, 0b0010000 };
const int LED_IDX[50] = { 35, 42,  8, 32, 29, 14, 39, 45, 36, 31, 
                          11,  2, 46, 15, 40, 10, 34, 26, 19,  3,
                          49, 37, 41,  7,  1, 50, 16,  6,  9, 38,  
                          27, 17,  4, 48, 18, 44, 12,  5, 30, 13,  
                          43, 47, 33, 28, 23, 24, 21, 20, 25, 22  };
                             
const int LED_IDX_REV[50] = { 25, 12, 20, 33, 38, 28, 24,  3, 29, 16, 
                              11, 37, 40,  6, 14, 27, 32, 35, 19, 48, 
                              47, 50, 45, 46, 49, 18, 31, 44,  5, 39, 
                              10,  4, 43, 17,  1,  9, 22, 30,  7, 15,
                              23,  2, 41, 36,  8, 13, 42, 34, 21, 26  };

#define CW 1
#define CCW -1
#define RISE 1
#define FALL -1
#define PIN_A 1
#define PIN_B 2

int val; 
int encoder0PinA = 2;
int encoder0PinB = 4;
int encoder0Pos = 0;
int encoder0PinALast = LOW;
int encoder0PinBLast = LOW;
int last_pin_action = RISE;
int last_active_pin = PIN_A;
int pinALast = LOW;
int pinBLast = LOW;
int n = LOW;
int buttonState = HIGH; 
int buttonStateLast = HIGH; 
int encoderSwitchPin = 5;
 
void setup(){
  pinMode(SER_Pin, OUTPUT);
  pinMode(RCLK_Pin, OUTPUT);
  pinMode(SRCLK_Pin, OUTPUT);
  pinMode(A, OUTPUT);
  pinMode(B, OUTPUT);
  pinMode(C, OUTPUT);
  pinMode(D, OUTPUT);
  pinMode(E, OUTPUT);
  pinMode(F_SEG, OUTPUT);
  pinMode(G, OUTPUT);
  pinMode(CA1, OUTPUT);
  pinMode(CA2, OUTPUT);
  pinMode(encoderSwitchPin,INPUT);
  pinMode(SHUTTER_Pin, OUTPUT);

  pinMode(encoder0PinA, INPUT); 
  digitalWrite(encoder0PinA, HIGH);       // turn on pull-up resistor
  pinMode(encoder0PinB, INPUT); 
  digitalWrite(encoder0PinB, HIGH);       // turn on pull-up resistor

  attachInterrupt(0, doEncoder, CHANGE);  // encoder pin on interrupt 0 - pin 2
  
  Serial.begin(9600); // Baud-rate
  //reset all register pins
  clearRegisters();
  writeRegisters();
  
  pinALast = digitalRead( encoder0PinA );
  pinBLast = digitalRead( encoder0PinB );
}               

void doEncoder() {
  /* If pinA and pinB are both high or both low, it is spinning
   * forward. If they're different, it's going backward.
   *
   * For more information on speeding up this process, see
   * [Reference/PortManipulation], specifically the PIND register.
   */
   if( is_shooting ) { return; }
  if (digitalRead(encoder0PinA) == digitalRead(encoder0PinB)) {
    encoder0Pos++;
  } else {
    encoder0Pos--;
  }
  if( encoder0Pos == 51 ) encoder0Pos = 00;
  if( encoder0Pos == -1 ) encoder0Pos = 50;

  if( encoder0Pos > 00 && encoder0Pos < 51 ){ 
    clearRegisters();
    setRegisterPin(encoder0Pos-1,HIGH);
    writeRegisters();
  } else if( encoder0Pos == 00 ) {
    clearRegisters();
    writeRegisters();
    
  }

  Serial.println (encoder0Pos, DEC);
  Serial.println (LED_IDX[encoder0Pos-1], DEC);
}

//set all register pins to LOW
void clearRegisters(){
  for(int i = numOfRegisterPins - 1; i >=  0; i--){
     registers[i] = LOW;
  }
} 


//Set and display registers
//Only call AFTER all values are set how you would like (slow otherwise)
void writeRegisters(){

  digitalWrite(RCLK_Pin, LOW);

  for(int i = numOfRegisterPins - 1; i >=  0; i--){
    digitalWrite(SRCLK_Pin, LOW);

    int val = registers[i];

    digitalWrite(SER_Pin, val);
    digitalWrite(SRCLK_Pin, HIGH);

  }
  digitalWrite(RCLK_Pin, HIGH);

}

//set an individual pin HIGH or LOW
void setRegisterPin(int index, int value){
  registers[LED_IDX[index]-1] = value;
}


void loop(){

  if (Serial.available() > 0) {
    // Reading incoming bytes :
    incomingByte = Serial.read();
    switch (incomingByte) {
      case 's':
        Serial.print("shoot\n");

        shootAll();
        for (int i = 0; i < 36; i++) { // Little trick to empty the buffer, not nice :/
          Serial.read();
        }
        break;
      default:; // Usefull for burst mode, this variables sets the time the shoot will last
        //lightDigit2(numbers[encoder0Pos]);
        //time = incomingByte*100;
    }
  }
  displayDigit( encoder0Pos, 20 );


  buttonState = digitalRead(encoderSwitchPin);    
  if( buttonState == LOW  and buttonStateLast == HIGH ) {
    is_shooting = TRUE;
    Serial.print("button pushed\n");
    Serial.print(encoder0Pos);
    Serial.print("\n");
    if( encoder0Pos == 0 ) {
      shootAll();
      Serial.print("shootAll\n");
    } else {
      Serial.print("shoot " );
      Serial.print( encoder0Pos);
        Serial.print("\n");
      shoot( encoder0Pos-1 );
    }
    is_shooting = FALSE;
  } else {
    ;//Serial.print("button high\n");
  }
  buttonStateLast = buttonState;
}
#define TOP_LIGHT 50
void ambientLightOn() {
  clearRegisters();
  setRegisterPin(TOP_LIGHT-1,HIGH);
  writeRegisters();
}
void ambientLightOff() {
  clearRegisters();
  writeRegisters();
}


void shootAll() {
          for( int i = 0; i < number_of_LEDs ; i++ ) {
            shoot( i);
        }
}
void shoot( int idx ) {
          clearRegisters();
          setRegisterPin(idx,HIGH);
          writeRegisters();
          displayDigit(idx+1, 2000);
          digitalWrite(SHUTTER_Pin, HIGH); // Focus..
          displayDigit(idx+1, 3000);
          digitalWrite(SHUTTER_Pin, LOW);
          displayDigit(idx+1, 1000);
        /*clearRegisters();
        writeRegisters();*/
  
}
void displayDigit(int idx, int delay_millis ){
          int dig1, dig2;
          dig1 = int( float(idx) / 10.0 );
          dig2 = idx - dig1 * 10;
          //Serial.print(dig1);
          //Serial.print(dig2);
          unsigned long startTime = millis();
      for (unsigned long elapsed=0; elapsed < delay_millis; elapsed = millis() - startTime) {
        lightDigit1(numbers[dig1]);
        delay(5);
        lightDigit2(numbers[dig2]);
        delay(5);
      }
}

void lightDigit1(byte number) {
  digitalWrite(CA1, LOW);
  digitalWrite(CA2, HIGH);
  lightSegments(number);
}

void lightDigit2(byte number) {
  digitalWrite(CA1, HIGH);
  digitalWrite(CA2, LOW);
  lightSegments(number);
}

void lightSegments(byte number) {
  for (int i = 0; i < 7; i++) {
    int bit = bitRead(number, i);
    digitalWrite(segs[i], bit);
  }
}
