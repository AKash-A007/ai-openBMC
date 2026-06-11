#goal is to mock the BMC for testing purposes

# DIMM failure
DIMM_FAILURE = { 
    "sensor":"DIMM_B2",
    "event":"Memory ECC Correctable Error",
    "severity":"WARNING"
                }
# CPU OVERHEAT
CPU_OVERHEAT = { 
    "sensor":"CPU1",
    "event":"CPU Over Temperature",
    "severity":"CRITICAL"
        }
# PSU failure
PSU_FAILURE = { 
    "sensor":"PSU1",
    "event":"Power Supply Failure",
    "severity":"CRITICAL"
    }

# A function to generate SEL log based on the senerio

def generate_sel_log(senerio):
    if senerio == "dimm_failure":
        return dict(DIMM_FAILURE)
    elif senerio == "cpu_overheat":
        return dict(CPU_OVERHEAT)
    elif senerio == "psu_failure":
        return dict(PSU_FAILURE)
    else:
        return None
    