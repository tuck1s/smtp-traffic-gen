#!/usr/bin/env python3

import random, datetime, zoneinfo, math

# -----------------------------------------------------------------------------
# Traffic model
# -----------------------------------------------------------------------------
class Traffic:
    def __init__(self):
        # typical triggered email busy hour curve (from 00:00 to 23:00 each day)
        triggered_volume_per_hour = [6, 4, 3, 3, 3, 2, 2, 4, 5, 10, 19, 27, 29, 28, 28, 26, 25, 24, 22, 19, 16, 14, 11, 8]
        # normalise, so that the sum of all the hourly volume would be ~ 1.0
        total = sum(triggered_volume_per_hour)
        self.normalised_triggered_volume_per_hour = [v / total for v in triggered_volume_per_hour]
        # set a window for random variability
        variability = 0.3
        self.high_v = 1 + variability
        self.low_v = 1 - variability

    def volume_this_minute(self, t: datetime.datetime, daily_vol: float):
        c = t.astimezone(zoneinfo.ZoneInfo('America/New_York'))
        # interpolate the volume between the value for this hour and the next hour (wrapping around)
        this_hour_vol = self.normalised_triggered_volume_per_hour[c.hour]
        next_hour_vol = self.normalised_triggered_volume_per_hour[(c.hour + 1) % 24]
        assert (c.minute >= 0) and (c.minute <=59)
        next_hour_fraction = c.minute / 60
        this_hour_fraction = 1 - next_hour_fraction
        this_minute_vol = daily_vol * (this_hour_vol * this_hour_fraction + next_hour_vol * next_hour_fraction) / 60
        # Add random 'dither' to ensure we sometimes send somethiing, even on low daily volume targets
        vary = random.uniform(self.low_v, self.high_v)
        this = int(math.floor(this_minute_vol * vary) + random.random())
        return this
