from django import template

register = template.Library()


# Template filter to access a dictionary by key name
def key(d, key_name):
    return d[key_name]
key = register.filter('key', key)

@register.filter
def join_by_attr(the_list, attr_name, separator=', '):
    return separator.join(str(getattr(i, attr_name)) for i in the_list)

@register.filter
def order_by_name(the_list, attr=None):
    if attr is not None:
        key = lambda x: (x[attr].user.last_name, x[attr].user.first_name)
    else:
        key = lambda x: (x.user.last_name, x.user.first_name)
    return sorted(the_list, key=key)
