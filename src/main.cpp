// File: src/main.cpp  (PlatformIO project)
#include <Arduino.h>
#include <Adafruit_HX711.h>
#include <array>
#include <utility>
#include "PWMDriver.h"
#include "ESC.h"


// Kaelyn change these
float throttleCap = 0.40; // 0-1
float throttleStep = 0.001f; // %/10ms //0.015 for battery characterization, 0.001 for thrust characterization
float topTime = 0.5f; //sec    // 50+ sec for battery, 0.5 sec for thrust characterization

constexpr uint8_t PIN_ESC1 = 9;
constexpr uint8_t PIN_ESC2 = 10;
constexpr uint8_t PIN_BATTERY = 23;

constexpr uint8_t CH_ESC1 = 2;
constexpr uint8_t CH_ESC2 = 3;

constexpr uint16_t ADC_RESOLUTION = 12;
constexpr uint16_t ADC_MAX = (1u << ADC_RESOLUTION) - 1;
constexpr float ADC_REF_VOLTAGE = 3.3f;
constexpr float BATTERY_DIVIDER_RATIO = 25.2f / 2.8f;

PWMDriver pwm;
ESC esc1(pwm, CH_ESC1, 1000, 2000);
ESC esc2(pwm, CH_ESC2, 1000, 2000);

// Pin assignments (change to match your Teensy wiring)
const uint8_t DOUT1 = 28;   // HX711 #1 data
const uint8_t SCK1  = 27;   // HX711 #1 clock

const uint8_t DOUT2 = 38;   // HX711 #2 data
const uint8_t SCK2  = 37;   // HX711 #2 clock

Adafruit_HX711 scale1(DOUT1, SCK1);
Adafruit_HX711 scale2(DOUT2, SCK2);

float throttle = 0;
double loopTime = 0.0;
bool stopped = true;
bool characterize = false;
bool charRampDown = false;
bool heldTop = false;
uint32_t lastCharUpdateUs = 0;
int calibrationMode = 0;                // 0=normal, 1=high pwm, 2=low pwm


// CSV logging helper for averaged readings
void logReadingCsv(uint32_t tMs, uint8_t cell, float grams, int32_t raw, float scale, int32_t tare, float batteryVoltage) {
  Serial.print(F("READ_CSV,"));
  Serial.print(tMs);
  Serial.print(F(","));
  Serial.print(cell);
  Serial.print(F(","));
  Serial.print(grams, 3);
  Serial.print(F(","));
  Serial.print(raw);
  Serial.print(F(","));
  Serial.print(scale, 6);
  Serial.print(F(","));
  Serial.print(tare);
  Serial.print(F(","));
  Serial.print(throttle, 3);
  Serial.print(F(","));
  Serial.println(batteryVoltage, 3);
}


float readBatteryVoltage(uint8_t pin) {
  float raw = analogRead(pin);
  float measuredVoltage = ADC_REF_VOLTAGE * (raw / float(ADC_MAX));
  return measuredVoltage * BATTERY_DIVIDER_RATIO;
}

// Calibration values (computed at runtime in this example)
float scaleFactor1 = 1.0f; // raw counts per gram (you'll compute)
float scaleFactor2 = 1.0f;
float scaleFactor = 52.2337; // 3/21/26, with 2kg, 5kg, 7kg, 12 total calibrations
int32_t tare1 = 152367, tare2 = 37769; // 3/21/26 with 9 calibrations


// Parse a token that might be "kp=...", "ki=...", "kd=...", or single-char commands.
void parseToken(const String &token)
{
    
    if (token.startsWith("tff="))
    {
        String val = token.substring(3);
        float thPow = val.toFloat();
        if (thPow != 0.0 || val == "0" || val == "0.0")
        {
            throttle = thPow;
            Serial.print("tff= ");
            Serial.println(throttle);
        }
    }
    else if (token.equals("]"))
    {
        throttle += 0.005;
        Serial.print("tff= ");
        Serial.println(throttle);
    }
    else if (token.equals("["))
    {
        throttle -= 0.005;
        Serial.print("tff= ");
        Serial.println(throttle);
    }
    else if (token.equals("cal"))
        {
            calibrationMode += 1;
            if (calibrationMode > 2)
            {
                calibrationMode = 0;
            }
        }


}

// Function to process incoming serial commands
void processSerialCommands()
{   
    if (Serial.available() > 0)
    {
        String input = Serial.readStringUntil('\n');
        input.trim();
        // Any line from the host counts as a heartbeat (including "hb")
        if (input.length() == 0)
        {
            // calibrationMode += 1;
            // if (calibrationMode > 2)
            // {
            //     calibrationMode = 0;
            // }
            // Serial.println(calibrationMode);
            stopped = !stopped;
            if (stopped) {
                Serial.println(F("[fly] Stopped"));
            } else {
                // starting characterization ramp when resuming
                characterize = true;
                charRampDown = false;
                heldTop = false;
                throttle = 0.0f;
                lastCharUpdateUs = micros();
                Serial.println(F("[char] Starting throttle ramp to 0.40 then back to 0"));
            }
            return;
        }

        int startIndex = 0;
        while (true)
        {
            int spaceIndex = input.indexOf(' ', startIndex);
            String token;
            if (spaceIndex == -1)
            {
                token = input.substring(startIndex);
                token.trim();
                if (token.length() > 0)
                {
                    parseToken(token);
                }
                break;
            }
            else
            {
                token = input.substring(startIndex, spaceIndex);
                token.trim();
                if (token.length() > 0)
                {
                    parseToken(token);
                }
                startIndex = spaceIndex + 1;
            }
        }
    }
}


void calibration()
{
    switch (calibrationMode)
    {
    case 1:
        // high pwm for ESC calibration
        esc1.setMicroseconds(2000);
        esc2.setMicroseconds(2000);
        break;
    case 2:
        // low pwm for ESC calibration
        esc1.setMicroseconds(1000);
        esc2.setMicroseconds(1000);
        break;
    default:
        calibrationMode = 0;
        break;
    }
}

// Utility: read averaged raw value (blocking)
int32_t readAvg(Adafruit_HX711 &hx, uint8_t samples = 1) {
  int64_t sum = 0;
  for (uint8_t i = 0; i < samples; ++i) {
    int32_t reading = hx.readChannelRaw();
    sum += reading;   // blocking read for stability
    delay(1);
  }
  
  return (int32_t)(sum / samples);
}

// Utility: read averaged raw value (blocking)
std::pair<int32_t,int32_t> readAvgBoth(Adafruit_HX711 &hx1, Adafruit_HX711 &hx2, uint16_t samples = 1) {
  int64_t sum1 = 0;
  int64_t sum2 = 0;
  for (uint16_t i = 0; i < samples; ++i) {
    int32_t r1 = hx1.readChannelRaw();   // blocking read for stability
    int32_t r2 = hx2.readChannelRaw();

    sum1 += r1;
    sum2 += r2;
    delay(1);
  }
  return std::make_pair((int32_t)(sum1 / samples), (int32_t)(sum2 / samples));
}


// Calibrate both HX711 channels in one pass so the operator only has to set/clear weight once.
void calibrateBothScales(
    Adafruit_HX711 &hx1, Adafruit_HX711 &hx2,
    float &scaleFactor1, float &scaleFactor2,
    int32_t &tareRaw1, int32_t &tareRaw2,
    float knownMass1, float knownMass2) {

  // 1) Capture tare on both channels simultaneously
//   Serial.println(F("Clear both scales (no weight). Waiting 4s..."));
//   delay(4000);

  auto tare = readAvgBoth(hx1, hx2, 300);
  tareRaw1 = tare.first;
  tareRaw2 = tare.second;
  Serial.print(F("Tare1 raw = ")); Serial.println(tareRaw1);
  Serial.print(F("Tare2 raw = ")); Serial.println(tareRaw2);

//   // 2) Ask for known masses on each scale (they can be identical)
//   Serial.print(F("Place known masses (g) - scale1: "));
//   Serial.print(knownMass1);
//   Serial.print(F("  scale2: "));
//   Serial.println(knownMass2);
//   delay(12000); // give user time

//   auto withMass = readAvgBoth(hx1, hx2, 1000);
//   Serial.print(F("Raw1 with mass = ")); Serial.println(withMass.first);
//   Serial.print(F("Raw2 with mass = ")); Serial.println(withMass.second);

//   int32_t delta1 = withMass.first - tareRaw1;
//   int32_t delta2 = withMass.second - tareRaw2;

//   if (delta1 <= 0) {
//     Serial.println(F("Scale1 calibration error: non-positive delta. Check wiring/sensor."));
//     scaleFactor1 = 1.0f;
//   } else {
//     scaleFactor1 = float(delta1) / knownMass1; // counts per gram
//     Serial.print(F("Scale1 scaleFactor (counts/g): "));
//     Serial.println(scaleFactor1, 6);
//   }

//   if (delta2 <= 0) {
//     Serial.println(F("Scale2 calibration error: non-positive delta. Check wiring/sensor."));
//     scaleFactor2 = 1.0f;
//   } else {
//     scaleFactor2 = float(delta2) / knownMass2; // counts per gram
//     Serial.print(F("Scale2 scaleFactor (counts/g): "));
//     Serial.println(scaleFactor2, 6);
//   }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) { delay(10); } // wait for serial connection (Teensy

      // PWM driver for servos/ESCx
    pwm.begin(50.0f);

    // Attach logical channels to Teensy pins
    pwm.attach(CH_ESC1, PIN_ESC1, 1000);
    pwm.attach(CH_ESC2, PIN_ESC2, 1000);

    // // Arm ESCs at minimum
    esc1.arm(1000, 1000);
    esc2.arm(1000, 1000);
    esc1.setMicroseconds(1000);
    esc2.setMicroseconds(1000);


  Serial.println(F("Starting HX711 dual-example (Teensy + Adafruit HX711)"));

  analogReadResolution(ADC_RESOLUTION);
  pinMode(PIN_BATTERY, INPUT);

  // Initialize both HX711s
  scale1.begin();
  scale2.begin();

  // optional: check ready
  bool scale1Busy = scale1.isBusy();
  bool scale2Busy = scale2.isBusy();
  while ( scale1Busy || scale2Busy) {
    scale1Busy = scale1.isBusy();
    scale2Busy = scale2.isBusy();
    if (scale1Busy) Serial.println(F("Scale 1 is busy..."));
    if (scale2Busy) Serial.println(F("Scale 2 is busy..."));
    delay(10);
  }

  // Calibration process for both scales:
  // Replace these with the known mass you will use for calibration (grams)
  const float knownMass1 = 7000.0f; // e.g. 500 g calibration weight
  const float knownMass2 = 7000.0f;

  // CSV headers (printed once so the host can split streams)
  Serial.println(F("READ_CSV,time_ms,loadcell,grams,raw,scale,tare,throttle,battery_voltage"));

  Serial.println(F("Calibrating both scales together:"));
  calibrateBothScales(scale1, scale2, scaleFactor1, scaleFactor2, tare1, tare2, knownMass1, knownMass2);

  Serial.println(F("\nCalibration complete. Readings follow..."));
 
}



void loop() {
    double loopStart = micros();
    processSerialCommands();
    if (calibrationMode)
        {
            calibration();
            throttle = 0;
            delay(1);
            return;
        }


    // Characterization: ramp throttle slowly from 0 -> 0.4 once when restarted
    if (characterize && !stopped) {
    uint32_t nowUs = micros();
    if (charRampDown && !heldTop && nowUs - lastCharUpdateUs >= 1000000 * topTime){ // 0.5 seconds at max throttle for battery comparison
        heldTop = true;
        lastCharUpdateUs = nowUs;

    }
    if (nowUs - lastCharUpdateUs >= 20000) { // update every 20ms
        if (!charRampDown) {
            lastCharUpdateUs = nowUs;
            throttle += throttleStep;
            if (throttle >= throttleCap) {
                throttle = throttleCap;
                charRampDown = true;
                Serial.println(F("[char] At 0.40, ramping down"));
            }
        } else if (heldTop) {
            lastCharUpdateUs = nowUs;
            throttle -= throttleStep;
            if (throttle <= 0.0f) {
                throttle = 0.0f;
                characterize = false;
                stopped = true; // end sequence by stopping
                Serial.println(F("[char] Ramp complete; stopping"));
            }
        }
    }
    }

    if (stopped)
    {
        esc1.setMicroseconds(1000);
        esc2.setMicroseconds(1000);
        
        throttle = 0;
        characterize = false;
        charRampDown = false;
        delay(50);

        return;
    }

    esc1.setThrottle01(throttle);
    esc1.update();
      
    esc2.setThrottle01(throttle);
    esc2.update();

    // Read averages
    std::pair<int32_t,int32_t> raw = readAvgBoth(scale1,scale2, 1);
    int32_t raw1 = raw.first;
    int32_t raw2 = raw.second;
    // int32_t raw1 = 0;
    // int32_t raw2 = 0;


    int32_t rawTared = 0;
    int32_t rawTared2 = 0;

    rawTared = raw1 - (int32_t)(tare1); // simple tare application
    rawTared2 = raw2 - (int32_t)(tare2);

    float grams1 = (float)rawTared / scaleFactor;
    float grams2 = (float)rawTared2 / scaleFactor;
    float batteryVoltage = readBatteryVoltage(PIN_BATTERY);

    uint32_t nowMs = millis();
    logReadingCsv(nowMs, 1, grams1, raw1, scaleFactor, tare1, batteryVoltage);
    logReadingCsv(nowMs, 2, grams2, raw2, scaleFactor, tare2, batteryVoltage);
    logReadingCsv(nowMs, 3, (grams1 + grams2) / 2.0, 0.0f, scaleFactor, 0, batteryVoltage);
    // Simple approximate grams computed from the calibration factors using last tare = read - (knownMass * scaleFactor)
    // (This is a demonstration — keep a persistent tare for accuracy.)
    double loopdt = (micros() - loopStart) * 1e-6; // seconds
    double targetPeriod = 1.0 / 80;
    double remaining = targetPeriod - loopdt;
    if (remaining > 0)
        delayMicroseconds(static_cast<uint32_t>(remaining * 1e6));

    loopTime = micros();

}
