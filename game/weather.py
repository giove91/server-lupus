#!/usr/bin/python
# coding=utf8

from datetime import datetime, timedelta
from game.utils import get_now

from urllib.request import urlopen
import xml.etree.ElementTree as ET

class Weather:

    dtformat = '%Y-%m-%d %H:%M:%S'
    update_interval = timedelta(minutes=10)

    def __init__(self, stored_weather):
        if stored_weather is None:
            self.last_update = None

            #self.temperature = None
            #self.wind_direction = None
            #self.wind_speed = None
            self.description = None

        else:
            self.last_update = datetime.strptime( stored_weather['last_update'], self.dtformat )
            self.description = stored_weather['description']


    def stored(self):
        # Returns the dictionary to be stored in session
        res = {}
        res['last_update'] = self.last_update.strftime(self.dtformat)
        res['description'] = self.description

        return res

    def is_uptodate(self):
        # True if the weather was update recently
        now = datetime.strptime( get_now().strftime(self.dtformat), self.dtformat )
        return self.last_update is not None and now - self.last_update < self.update_interval


    def get_data(self):
        # Returns False if an actual update was performed
        if self.is_uptodate():
            return True

        # Fetching weather data from openweathermap.org
        url = 'http://api.openweathermap.org/data/2.5/weather?q=Pisa&mode=xml&APPID=a7956a78c44d8f1d55ce58ad08e0e2b3'
        # TODO: When publishing the code, make this configurable
        try:
            data = urllib2.urlopen(url, timeout = 3)
            rawdata = data.read()
            root = ET.fromstring(rawdata)
            self.description = int( root.find('weather').get('number') )
            #self.temperature = float( root.find('temperature').get('value') )
            #self.wind_direction = root.find('wind').find('direction').get('code')
            #self.wind_speed = float( root.find('wind').find('speed').get('value') )
            #self.sunrise = root.find('city').find('sun').get('rise')
            #self.sunset = root.find('city').find('sun').get('set')

        except Exception:
            self.description = None

        self.last_update = get_now()
        return False

    def weather_type(self):
        # see http://bugs.openweathermap.org/projects/api/wiki/Weather_Condition_Codes
        if self.description is None:
            return 'unknown'
        elif 300 <= self.description <= 321 or 500 == self.description:
            return 'light rain'
        elif 200 <= self.description <= 232 or 501 <= self.description <= 531:
            return 'heavy rain'
        elif 803 <= self.description <= 804 or 701 <= self.description <= 741:
            # 7** sarebbero nebbia o affini
            return 'cloudy'
        elif 800 <= self.description <= 802:
            return 'clear'
        else:
            return 'unknown'
    type = property(weather_type)

    def adjective(self):
        if self.type == 'light rain':
            return u'umid'
        elif self.type == 'heavy rain':
            return u'piovos'
        elif self.type == 'cloudy':
            return u'nuvolos'
        elif self.type == 'clear':
            return u'seren'
        else:
            return u'nuov'
    adjective = property(adjective)

