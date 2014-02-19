from django import template

register = template.Library()


# Template filter to access a dictionary by key name
def key(d, key_name):
    return d[key_name]
key = register.filter('key', key)
