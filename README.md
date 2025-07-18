Renamed ATLAS (Advanced Tactical Laboratory and Analysis System)

# ATLAS
See Project @ https://hackaday.io/project/203273-ai-field-analyzer

My version of a Tricorder, Rads, CO2, VOCs, pressure, temp, humidity, light, sound, and magnetic. Gives real feedback via onboard AI
A tough and practical handheld with sensors for radiation, CO₂, VOCs, temperature, humidity, light, sound, and magnetic fields.
What sets it apart? Built-in AI (Google Coral Mini) that actually tells you, in plain English, if it’s safe or not—like, “You have 10 minutes before you should leave.”
No more guessing with sensor numbers. (this alone is the issue that I see that separates a bunch of sensors from a real device that can save your life or detect a anomaly.)
It will feature a big battery, open hardware, and practical field use.

It gives real feedback in plain English, not just sensor numbers and will actually warn you when it’s time to leave. It will be feature a high capacity battery and open hardware for real-world fieldwork. No hype just practical science and anomaly logging you can use Build details and files on the project page. I was tied of the future coming to me, I'm pretty sure I can make it instead...

Currently the following code is just a start to both read the first two sensors and create the first low power warning mode. Normally low power mode will only warn medium status, if a rise is detected the AI Google coral mini board will be putt online and the Pico will communicate sensor data to it. The Coral will then use on the edge AI to give the best feedback possible on a dangerous situation or a detected anomaly.

Anomaly Detection That Thinks Outside the Box
The AI Field Analyzer isn’t just another data logger.
Sure, it reads environmental values like any pro instrument. But its real power is in the anomaly nets—layers of logic that scan not just for real-world hazards (radiation spikes, high VOCs, sudden motion), but also for the “what the hell was that?” events:

Impossible gravity shifts

Sudden time distortions

Chaotic compass readings

Non-physical acceleration

…or anything that just doesn’t fit the laws of boring old physics

Why?
Because sometimes, the most important thing isn’t catching what you expect—it’s flagging what you can’t explain. The AI Field Analyzer is built to raise a flag when the universe acts up—whether that’s a real hazard, interference, a hardware fluke, or, just maybe, something truly new.

Plain English, Not Just Numbers
Forget staring at raw sensor values and squinting at the graphs.
This device tells you what it means—in plain English, right there on the display or log.

“Radiation dangerously high—leave area within 5 minutes.”

“Gravity anomaly detected—check for interference or unknown effects.”

“Time distortion: sensor timing irregular, possible interference.”

“Motion detected: device has been moved or shaken.”

The goal is simple:

Actionable information. Not just numbers.
If something’s off, you’ll know—no PhD required.

Whether you’re a scientist, a hacker, or a field explorer, the AI Field Analyzer is your smart companion:
Flagging the expected, surfacing the impossible, and always telling you—in words, not just digits—what’s actually going on.
