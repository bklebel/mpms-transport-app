"""Hacked-together script for 4-point resistance measurements.

WARNING: This is a first test, it's not correct (but it's close). In particular,
a voltage source (lock-in internal oscillator) and series resistor are used
instead of a current source.

This is designed to be used for 4-point resistance measurements in the MPMS,
using the following protocol:
    1. Hook up your sample to the lock-in as you would expect.
        - Use Ch1 for Vxx and Ch2 for Vxy.
        - Use the lock-in Osc Out for the "current" source with a resistor in 
          series with the sample.
    2. Run this script.
    3. Start whatever temperature or field sweeps you want using MultiVu.
    4. Stop the script using TODO:[some key or command] to save the data.

Script usage:
    python script-name.py [args]
        [args] can be:
            -f=filename
"""

# import time as t
# import numpy as np
import pandas as pd
import visa as v
from visa import VisaIOError
import matplotlib.pyplot as plt
import matplotlib.gridspec as gs
import os as os
import os.path as op
import datetime

# Config variables
# NOTE: Instrument setup is not (yet) implemented. Use the front panel.
lockin_tc = 1  # see manual, page 6-14
lockin_sens = 19  # see manual, page 6-11
lockin_freq = 1234.567
lockin_amp = 1  # amplitude in μV


# Set up instruments
lockin = v.ResourceManager().open_resource('GPIB0::12::INSTR')
# TODO: lockin.write('') # set up config variables ...


df = pd.DataFrame(dict(time=[], src=[], ch1r=[],
                       ch2r=[], temp=[], rho=[],
                       field=[], resistivity=[],))

datafile_write = 'cu-RvsT-2.csv'
datafile_MPMS = 'data.dc.dat'

SAMPLE_DIMENSIONS = dict(cs1=1e3, cs2=1e3, length=1e3)

if op.exists(datafile_MPMS):
    if input("MPMS data file already exists. Delete? [y/N]: ") == 'y':
        os.remove(datafile_MPMS)


class Dontmeasure(Exception):
    pass


def geomfactor(cs1, cs2, length):
    '''convert units (including sample geometries) so that [Ohm] becomes [Ohm m]

    cs1 and cs2 are the sides making up the cross-section:
        Area of cross section: A = cs1 * cs2

    length is the length of the path the current takes, as in:

    R = \rho * Length / A
    \rho = R * A / Length

    all units to be given in [mm]

    for other units ([Ohm cm]), the unit conversion
        needs to be applied 'inversly'
        [Ohm m] to [Ohm cm] has a factor of 1e2

    returns: factor to be applied to the resistance
    '''
    # area in mm^2
    Amm2 = cs1 * cs2
    # area in m^2
    Am2 = Amm2 * 1e-6
    # length in m
    le = length * 1e-3
    fac = Am2 / le
    return fac


def getMPMS_data(datafile, n_lines):
    try:
        with open(datafile) as f:
            file = f.readlines()
            n = len(file)
            if n <= n_lines:
                plt.pause(0.2)
                raise Dontmeasure
            else:
                n_lines = n
        line = file[-1].split(',')
        tem = float(line[3])
        H = float(line[2])
        return tem, H, n_lines
    except OSError:
        plt.pause(0.2)
        raise Dontmeasure


def measure_resistivity(lockin, shunt_resistance):
    src = float(lockin.query('OA.').split()[0])
    ch1r = float(lockin.query('MAG1.').split()[0])
    ch2r = float(lockin.query('MAG2.').split()[0])
    current = src / (shunt_resistance + 50 + 12)  # 50 ohm internal resistiance
    rho = ch1r / current
    return src, ch1r, ch2r, rho


fig = plt.figure()
grid = gs.GridSpec(3, 2, figure=fig)
ax1 = fig.add_subplot(grid[0, :])
ax1.set_xlabel("T (K)")
ax1.set_ylabel(r"$\rho$ ($\Omega$ m)")
line0, = ax1.plot(df['resistivity'], df['temp'], 'k.-')
ax2 = fig.add_subplot(grid[1, :])
ax2.set_xlabel("T (K)")
ax2.set_ylabel("V (V)")
line1, = ax2.plot(df['ch1r'], df['temp'], 'r.-', label='Ch. 1')
line2, = ax2.plot(df['ch2r'], df['temp'], 'b.-', label='Ch. 2')
ax2.legend()
ax3 = fig.add_subplot(grid[2, 0])
ax3.set_xlabel("time")
ax3.set_ylabel("T (K)")
line3, = ax3.plot_date(df['temp'], df['time'], 'k.-')
ax4 = fig.add_subplot(grid[2, 1])
ax4.set_xlabel("time")
ax4.set_ylabel("H (Oe)")
line4, = ax4.plot_date(df['field'], df['time'], 'k.-')
plt.tight_layout()

print("Start of loop message. Press 'CTRL + C' to stop measuring")
n_lines = 0
while True:
    try:
        try:
            tem, H, n_lines = getMPMS_data(datafile_MPMS, n_lines)

            src_now, ch1r_now, ch2r_now, rho_now = measure_resistivity(
                lockin, shunt_resistance=1e4)

            df = df.append(dict(src=src_now, ch1r=ch1r_now,
                                ch2r=ch2r_now, temp=tem,
                                resistance=rho_now, time=datetime.datetime.now(),
                                field=H,
                                resistivity=rho_now * geomfactor(**SAMPLE_DIMENSIONS),
                                ), ignore_index=True)
            with open(datafile_write, 'a') as f:
                df.tail(1).to_csv(f, header=f.tell() == 0)

            print(df.tail(1))
        except Dontmeasure:
            continue
        except VisaIOError:
            pass
        except ValueError:
            pass

        # update plot
        for line in [line1, line2, line0]:
            line.set_xdata(df['temp'])
        for line in [line3, line4]:
            line.set_xdata(df['time'])

        line1.set_ydata(df['ch1r'])
        line2.set_ydata(df['ch2r'])
        line0.set_ydata(df['resistivity'])
        line3.set_ydata(df['temp'])
        line4.set_ydata(df['field'])

        for a in [ax1, ax2, ax3, ax4]:
            a.relim()
            a.autoscale_view()

        # fig.canvas.draw()
        # fig.canvas.flush_events()
        plt.draw()
        plt.pause(1)
        # t.sleep(delay)
    except KeyboardInterrupt:
        break
