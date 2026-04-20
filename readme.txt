Battery Voltage Measurement
reference the diagram i sent you in dms before, you need to create the voltage divider circuit
- Use open space at the end of the breadboard
- Youtube video that goes w the diagram https://www.youtube.com/watch?v=L321aqTvrLQ
- You need 3.3 volt as the maximum to go into the teensy *pin 23*
- have your power and ground wires start at the V-IN of the buck converters


Big motor:
one yellow in pin 9
one yellow in pin 10
black wire to ground rail (blue)

Connect to teensy
- Mirco usb

Sending code to teensy
- press the dropdown at the top, then click upload

Starting code
- press the plug looking button to start serial
- After it finishes calibration, press enter in the terminal to run
- Press enter to manually stop if needed

After test, run this to make a new readings.csv
.\.venv\Scripts\python.exe .\scripts\log_to_csv.py logs/device-monitor-260414-204114.log

Then, run this to make a new readings_plot.html
.\.venv\Scripts\python.exe .\scripts\plot_readings_fixed.py

drag and drop the html file into a browser to look at graphs
If you want to keep the data, rename the log file and readings.csv to a useful NAME


