#!/usr/bin/env python3

import random, datetime, zoneinfo, math

# -----------------------------------------------------------------------------
# Traffic model
# -----------------------------------------------------------------------------
class Traffic:
    def __init__(self):
        # typical triggered email busy hour curve (from 00:00 to 23:00 each day)
        triggered_volume_per_hour = [6, 4, 3, 2, 1, 0.2, 0.2, 4, 5, 10, 19, 27, 29, 28, 28, 26, 25, 24, 22, 19, 16, 14, 11, 8]
        # normalise, so that the sum of all the hourly volume would be ~ 1.0
        total = sum(triggered_volume_per_hour)
        self.normalised_triggered_volume_per_hour = [v / total for v in triggered_volume_per_hour]
        # set a window for random variability


    def volume_this_minute(self, t: datetime.datetime, daily_vol: float):
        c = t.astimezone(zoneinfo.ZoneInfo('America/New_York'))
        # interpolate the volume between the value for this hour and the next hour (wrapping around)
        this_hour_vol = self.normalised_triggered_volume_per_hour[c.hour]
        next_hour_vol = self.normalised_triggered_volume_per_hour[(c.hour + 1) % 24]
        assert (c.minute >= 0) and (c.minute <=59)
        next_hour_fraction = c.minute / 60
        this_hour_fraction = 1 - next_hour_fraction
        this_minute_vol = daily_vol * (this_hour_vol * this_hour_fraction + next_hour_vol * next_hour_fraction) / 60
        # Add random 'dither' to ensure we sometimes send something, even on low daily volume targets
        vary = self.pseudorandom(c.day, c.hour, c.minute)
        this = int(math.floor(this_minute_vol * vary) + random.random())
        return this
    
    # Choose a pseudo-random value between low_v and high_v that's fairly consistent over an M minute interval
    def pseudorandom(self, day, hour, minute):
        coarse_variability = 0.3
        fine_variability = 0.05
        M = 7
        seed = minute//M + hour + day
        random.seed(seed)
        vary = random.uniform(1-coarse_variability, 1+coarse_variability)
        random.seed()
        vary += random.uniform(-fine_variability, fine_variability)
        return vary

# -----------------------------------------------------------------------------
# Main code - for testing
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    traffic_model = Traffic()
    t = datetime.datetime(2023, 7, 18, 0, 0, 0, 0, zoneinfo.ZoneInfo('America/New_York'))
    actuals = []
    for i in range(0, 60*24):
        vol = traffic_model.volume_this_minute(t, 100000)
        t += datetime.timedelta(minutes=1)
        actuals.append(vol)
    import statistics
    print(f'Sum = {sum(actuals)}, mean = {statistics.mean(actuals):.3f}, std dev = {statistics.stdev(actuals):.3f}')