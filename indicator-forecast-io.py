#!/usr/bin/env python3

from gi.repository import Gtk, GLib, cairo, GdkPixbuf
try:
    from gi.repository import Gio
except ImportError:
    pass
try:
    from gi.repository import AppIndicator3 as AppIndicator
except:
    from gi.repository import AppIndicator as AppIndicator
import datetime as dt
import forecast_io
from collections import namedtuple
from geopy import geocoders
import math

keyfile = open('api.key', 'r')
API_KEY = keyfile.readline().strip()
keyfile.close()

_SECONDS = 1000
_MINUTES = 60 * _SECONDS
_HOURS = 60 * _MINUTES

DEGREES = u'\N{DEGREE SIGN}'
UNITS = { 'si':
            { 'temperature': DEGREES+'C',
              'speed': 'm/s',
              'pressure': 'hPa',
              'precipAccum': 'cm',
              'precipRate': 'mm/hr',
              'dist': 'km'
            },
          'us':
            { 'temperature': DEGREES+'F',
              'speed': 'mph',
              'pressure': 'mbar',
              'precipAccum': 'in',
              'precipRate': 'in/hr',
              'dist': 'mi'
            }
        }

UNITS['ca'] = UNITS['si'].copy()
UNITS['ca']['speed'] = 'kph'

UNITS['uk'] = UNITS['si'].copy()
UNITS['uk']['speed'] = 'mph'

ICON_PATH = '/usr/share/icons/ubuntu-mono-dark/status/16/'
_icon_theme = Gtk.IconTheme.get_default()
ICONS = {'clear-day': _icon_theme.lookup_icon('weather-clear', 0, 0).get_filename(),
        'clear-night': _icon_theme.lookup_icon('stock_weather-night-clear', 0, 0).get_filename(),
        'rain': _icon_theme.lookup_icon('stock_weather-showers', 0, 0).get_filename(),
        'snow': _icon_theme.lookup_icon('stock_weather-snow', 0, 0).get_filename(),
        'sleet': _icon_theme.lookup_icon('weather-showers-scattered', 0, 0).get_filename(),
        'wind': _icon_theme.lookup_icon('stock_weather-fog', 0, 0).get_filename(),
        'fog': _icon_theme.lookup_icon('stock_weather-fog', 0, 0).get_filename(),
        'cloudy': _icon_theme.lookup_icon('stock_weather-cloudy', 0, 0).get_filename(),
        'partly-cloudy-day': _icon_theme.lookup_icon('stock_weather-few-clouds', 0, 0).get_filename(),
        'partly-cloudy-night': _icon_theme.lookup_icon('stock_weather-night-few-clouds', 0, 0).get_filename(),
        'alert': _icon_theme.lookup_icon('weather-severe-alert', 0, 0).get_filename(),
        'other': _icon_theme.lookup_icon('weather-severe-alert', 0, 0).get_filename()}

"""
class Settings:
    db = None
    BASE_KEY = 'apps.indicators.forecast-io'
    #DATE_KEY = 'target_date'

    def prepare_settings_store(self):
        # Example from indicator-weather
        try:
            self.db = Gio.Settings.new(self.BASE_KEY)
        except Exception as e:
            pass

class PrefsDialog:
    def __init__(self):#, callback):
        builder = Gtk.Builder()
        builder.add_from_file("/home/fourwood/src/indicator-countdown/settings.ui")
        self.window = builder.get_object("settings_window")

        self.callback = callback

        self._ok_btn = builder.get_object("ok_btn")
        self._ok_btn.connect('clicked', self.clicked_ok)
        self._cancel_btn = builder.get_object("cancel_btn")
        self._cancel_btn.connect('clicked', self.clicked_cancel)

        self._calendar = builder.get_object("calendar")
        self._time = builder.get_object("time_entry")
        self._am = builder.get_object("am_radio")
        self._pm = builder.get_object("pm_radio")

        self.builder = builder

    def clicked_ok(self, widget):
        time = self._time.get_text()
        date = self._calendar.get_date()
        is_am = (self._pm.get_active() and not self._am.get_active())
        self.callback(date, time, is_am)
        self.window.hide()

    def clicked_cancel(self, widget):
        self.window.hide()
"""

class ForecastInd:
    def __init__(self):
        self.UPDATE_INTERVAL = 15 * _MINUTES
        self.ind = AppIndicator.Indicator.new("forecast-io-indicator",
                "forecast-io-indicator",
                AppIndicator.IndicatorCategory.OTHER);
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)

        g = geocoders.GoogleV3()
        #self.location = "6114 SW 39th St, Topeka, KS 66610"
        #self.location = "215 29th St, Boulder, CO 80305"
        self.location = "643 E Johnson St, Madison, WI 53703"
        self.place, (self.latitude, self.longitude) = g.geocode(self.location)
        #self.latitude = 38.996269
        #self.longitude = -95.76602

        self.has_alerts = False

        #self.settings = Settings()
        #self.settings.prepare_settings_store()
        #self.target_date = self.settings.get_value("target_date")
        #self.target_time = self.settings.get_value("target_time")
        self.update()

    def _get_forecast(self):
        return forecast_io.get_forecast(API_KEY, self.latitude, self.longitude)

    def _prefs(self, widget):
        #if ((not hasattr(self, 'prefs_wind')) or (not self.prefs_wind.get_visible())):
        #    self.prefs_wind = PrefsDialog()
        #    self.prefs_wind.show()
        #self.prefs_window = PrefsDialog(self.prefs_callback)
        #self.prefs_window.window.show()
        pass

    def _prefs_callback(self, date, time, is_pm):
        pass

    def _get_wind_direction(self, bearing):
        if bearing < 22.5:
            direction = 'N'
        elif bearing < 67.5:
            direction = 'NE'
        elif bearing < 112.5:
            direction = 'E'
        elif bearing < 157.5:
            direction = 'SE'
        elif bearing < 202.5:
            direction = 'S'
        elif bearing < 247.5:
            direction = 'SW'
        elif bearing < 292.5:
            direction = 'W'
        elif bearing < 337.5:
            direction = 'NW'
        else:
            direction = 'N'

        return direction

    def _calc_heat_index(self, T, H):
        if T < 80:
            index = T
        else:
            c = [0, -42.379, 2.04901523, 10.14333127, -0.22475541,
                    -6.83783e-3, -5.481717e-2, 1.22874e-3,
                    8.5282e-4, -1.99e-6]
            index = c[1] + c[2] * T + c[3] * H + c[4] * T * H + \
                    c[5] * T**2 + c[6] * H**2 + c[7] * T**2 * H + \
                    c[8] * T * H**2 + c[9] * T**2 * H**2

            adjustment = 0
            if H < 13:
                adjustment = -(13-H)/4 * math.sqrt((17-abs(T-95.))/17.)
            elif (H > 85) and (T >= 80) and (T <= 87):
                adjustment = ((H-85)/10) * ((87-T)/5)
            index += adjustment

        return index

    def _add_menu_item(self, label, text, unit, callback=None):
        pass

    def _make_precip_image(self):
        probability = []
        intensity = []
        time = []
        data = self.forecast.minutely.data
        time0 = data[0].time

        for point in data:
            probability.append(point.precipProbability)
            intensity.append(point.precipIntensity)
            delta = point.time - time0
            time.append(delta.seconds / 60)

        image = Gtk.Image()

        return image

    def _activate_alert(self, widget, uri):
        Gtk.show_uri(None, uri, 0)

    def _activate_refresh(self, widget):
        self.update()

    def _build_menu(self):
        self.menu = Gtk.Menu()

        cur = self.forecast.currently
        self.has_alerts = hasattr(self.forecast, 'alerts')

        #TODO: Do this all in a loop of some kind.

        label = "Condition: {0}".format(cur.summary)
        summary = Gtk.MenuItem(label)
        summary.show()
        self.menu.append(summary)

        unit = UNITS[self.units]['temperature']
        T = round(cur.temperature)
        label = 'Temperature: {0}{1}'.format(T, unit)
        temp = Gtk.MenuItem(label)
        #temp.connect("activate", foo)
        temp.show()
        self.menu.append(temp)

        label_string = '{0}{1}'.format(T, unit)
        self.ind.set_label(label_string, '')

        H = round(100*cur.humidity)
        label = 'Humidity: {0}%'.format(H)
        humidity = Gtk.MenuItem(label)
        #humidity.connect("activate", foo)
        humidity.show()
        self.menu.append(humidity)

        index = round(self._calc_heat_index(T, H))
        if index > T:
            unit = UNITS[self.units]['temperature']
            label = 'Heat index: {0}{1}'.format(index, unit)
            heat_index = Gtk.MenuItem(label)
            #heat_index.connect("activate", foo)
            heat_index.show()
            self.menu.append(heat_index)

        unit = UNITS[self.units]['temperature']
        label = 'Dew point: {0}{1}'.format(round(cur.dewPoint), unit)
        dew = Gtk.MenuItem(label)
        #dew.connect("activate", foo)
        dew.show()
        self.menu.append(dew)

        unit = UNITS[self.units]['speed']
        if hasattr(cur, 'windBearing'):
            bearing = cur.windBearing
            windDir = self._get_wind_direction(bearing)
            label = 'Wind: {0} {1} {2}'.format(round(cur.windSpeed), unit, windDir)
        else:
            label = 'Wind: {0} {1}'.format(round(cur.windSpeed), unit)
        wind = Gtk.MenuItem(label)
        #wind.connect("activate", foo)
        wind.show()
        self.menu.append(wind)

        unit = UNITS[self.units]['dist']
        label = 'Visibility: {0} {1}'.format(round(cur.visibility), unit)
        vis = Gtk.MenuItem(label)
        #vis.connect("activate", foo)
        vis.show()
        self.menu.append(vis)

        hms_format = '%I:%M:%S %p'
        today = self.forecast.daily.data[0]

        sunrise_time = today.sunriseTime.strftime('%I:%M:%S %p')
        sunrise_time = sunrise_time.lstrip('0')
        label = 'Sunrise: {0}'.format(sunrise_time)
        sunrise = Gtk.MenuItem(label)
        #sunrise.connect("activate", foo)
        sunrise.show()
        self.menu.append(sunrise)

        sunset_time = today.sunsetTime.strftime('%I:%M:%S %p')
        sunset_time = sunset_time.lstrip('0')
        label = 'Sunset: {0}'.format(sunset_time)
        sunset = Gtk.MenuItem(label)
        #sunset.connect("activate", foo)
        sunset.show()
        self.menu.append(sunset)

        if self.has_alerts:
            separator = Gtk.SeparatorMenuItem()
            separator.show()
            self.menu.append(separator)

            # Add an alert item to the menu if you have them.
            alert_menu = Gtk.Menu()
            alert_item = Gtk.MenuItem("Alerts")
            alert_item.set_submenu(alert_menu)
            alert_item.show()
            self.menu.append(alert_item)
            for alert in self.forecast.alerts:
                label = alert.title
                item = Gtk.MenuItem(label, use_underline=True)
                item.connect("activate",
                        self._activate_alert, alert.URI)
                item.show()
                alert_menu.append(item)
            alert_menu.show()

        separator = Gtk.SeparatorMenuItem()
        separator.show()
        self.menu.append(separator)

        """
        precip_menu = Gtk.Menu()
        label = "Precipitation"
        precip = Gtk.MenuItem(label)
        #precip.connect("activate", foo)
        precip.set_submenu(precip_menu)
        precip.show()
        self.menu.append(precip)

        img = Gtk.Image()
        img.set_from_file('/home/fourwood/src/indicator-forecast-io/test.png')
        image = self._make_precip_image()
        test = Gtk.ImageMenuItem(label='\n')
        test.set_image(img)
        test.set_always_show_image(True)
        test.show()
        precip_menu.append(test)

        separator = Gtk.SeparatorMenuItem()
        separator.show()
        self.menu.append(separator)
        """

        pref = Gtk.MenuItem("Preferences")
        #pref.connect("activate", self.prefs_box)
        pref.show()
        self.menu.append(pref)

        refresh = Gtk.MenuItem("Refresh")
        refresh.connect("activate", self._activate_refresh)
        refresh.show()
        self.menu.append(refresh)

        quit = Gtk.MenuItem("Quit")
        quit.connect("activate", self.destroy)
        quit.show()
        self.menu.append(quit)
        
        if hasattr(self.forecast, 'alerts'):
            self.icon = 'alert'
        elif cur.icon in ICONS:
            self.icon = cur.icon
        else:
            self.icon = 'other'
        self.ind.set_icon(ICONS[self.icon])

        self.ind.set_menu(self.menu)

    def destroy(self, widget):
        Gtk.main_quit()

    def update(self):
        # Only the framework for handling errors... should do better
        try:
            self.forecast = self._get_forecast()
            self.units = self.forecast.flags.units
            self._build_menu()
            return True
        except Exception as error:
            raise error
            #return False

    def main(self):
        self.timer = GLib.timeout_add(self.UPDATE_INTERVAL,
                self.update)
        Gtk.main()


if __name__ == "__main__":
    indicator = ForecastInd()
    indicator.main()
