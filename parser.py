# need to parse event 

#sample input 
# x = {
#   "sensor":"DIMM_B2",
#   "event":"Memory ECC Error"
# }

from datetime import datetime

def parse_event(event):
    if "ECC" in event:
        return {
            "category": "MEMORY",
            "event_type": "ECC_ERROR"
        }

    elif "CPU Over Temperature" in event:
        return {
            "category": "CPU",
            "event_type": "OVERHEAT"
        }

    elif "Power Supply Failure" in event:
        return {
            "category": "PSU",
            "event_type": "FAILURE"
        }

    return None

def parse_log(log):

    sensor = log.get("sensor")
    event = log.get("event")
    severity = log.get("severity")

    parsed = parse_event(event)

    if parsed:
        return {
            "sensor": sensor,
            "category": parsed["category"],
            "event_type": parsed["event_type"],
            "severity": severity
        }

    return None

# print(parse_log(x))
