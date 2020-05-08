# LogMice
Simple Python script to log movements of multiple mice present as Linux char-devices.


## Publishing movements via MQTT
MQTT can be configured to publish movements in defined intervalls.
Messages are formatted in *JSON* and contain accumulated data for every mouse which moved.
