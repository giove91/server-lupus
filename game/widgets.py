from django import forms
from django.contrib.admin.widgets import AdminSplitDateTime, AdminDateWidget, AdminTimeWidget
class MultiSelect(forms.SelectMultiple):
    class Media:
        css = {
            'screen': ('multiselect/css/multi-select.css',)
        }
        js = ('multiselect/js/jquery.multi-select.js', )


class CustomSplitDateTime(AdminSplitDateTime):
    supports_microseconds = True
    def __init__(self, date_format=None, time_format=None, attrs=None):
        widgets = (
            AdminDateWidget(format=date_format),
            AdminTimeWidget(format=time_format)
        )
        # Note that we're calling MultiWidget, not SplitDateTimeWidget, because
        # we want to define widgets.
        forms.MultiWidget.__init__(self, widgets, attrs)
