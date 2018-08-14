from django import template

register = template.Library()


# Template filter to access a dictionary by key name
def key(d, key_name):
    return d[key_name]
key = register.filter('key', key)

@register.filter
def join_by_attr(the_list, attr_name, separator=', '):
    return separator.join(str(getattr(i, attr_name)) for i in the_list)
