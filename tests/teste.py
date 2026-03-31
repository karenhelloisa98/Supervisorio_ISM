import nidaqmx

CHANNEL = "cDAQ1Mod1/ai13"

def current_to_psi(mA):
    return (mA - 4.0) * 10000.0 / 16.0

with nidaqmx.Task() as task:
    task.ai_channels.add_ai_current_chan(CHANNEL)

    while True:
        value_a = task.read()
        value_ma = value_a * 1000
        value_psi = current_to_psi(value_ma)

        print(f"{value_ma:.3f} mA  |  {value_psi:.2f} psi")